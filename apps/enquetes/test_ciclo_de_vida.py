"""B2: ciclo de vida das Enquetes (rascunho -> activa -> encerrada)."""

from django.urls import reverse
from rest_framework import status

from apps.enquetes.models import Enquete, EnqueteExibicao, EnqueteVoto
from apps.enquetes.tests import EnqueteBase, make_user
from apps.tenancy.models import Membership


class CicloBase(EnqueteBase):
    def setUp(self):
        super().setUp()
        self.student = self.students[0]
        self.other_teacher = make_user("prof2@test.com", "creator")
        Membership.objects.create(
            user=self.other_teacher, organizacao=self.org, role="teacher"
        )
        self.foreign_teacher = make_user("prof-b@test.com", "creator")
        Membership.objects.create(
            user=self.foreign_teacher, organizacao=self.other_org, role="teacher"
        )
        self.foreign_hdr = {"HTTP_X_WORKSPACE": str(self.other_org.id)}

    def post(self, name, enquete, user=None, hdr=None):
        self.client.force_authenticate(user or self.teacher)
        return self.client.post(
            reverse(name, args=[enquete["id"]]), **(self.hdr if hdr is None else hdr)
        )

    def state(self, enquete):
        return Enquete.objects.get(pk=enquete["id"]).state

    def listed_ids(self, user):
        self.client.force_authenticate(user)
        r = self.client.get(reverse("enquete-list"), **self.hdr)
        return [e["id"] for e in r.data["results"]]


class TransitionTests(CicloBase):
    def test_new_enquete_is_draft(self):
        data = self.create_enquete(publish=False)
        self.assertEqual(data["state"], "rascunho")
        self.assertEqual(self.state(data), "rascunho")

    def test_publish_then_close(self):
        data = self.create_enquete(publish=False)
        r = self.post("enquete-publish", data)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data["state"], "activa")

        r = self.post("enquete-close", data)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data["state"], "encerrada")
        self.assertIsNotNone(r.data["closedAt"])

    def test_invalid_transitions_are_409(self):
        data = self.create_enquete(publish=False)
        self.assertEqual(self.post("enquete-close", data).status_code, 409)
        self.post("enquete-publish", data)
        self.assertEqual(self.post("enquete-publish", data).status_code, 409)
        self.post("enquete-close", data)
        self.assertEqual(self.post("enquete-close", data).status_code, 409)
        self.assertEqual(self.post("enquete-publish", data).status_code, 409)
        self.assertEqual(self.state(data), "encerrada")

    def test_only_creator_transitions(self):
        data = self.create_enquete()
        for user in (self.other_teacher, self.student):
            self.assertEqual(
                self.post("enquete-close", data, user=user).status_code,
                status.HTTP_403_FORBIDDEN,
            )
        self.assertEqual(self.state(data), "activa")

    def test_others_draft_cannot_be_published_by_others(self):
        data = self.create_enquete(publish=False)
        r = self.post("enquete-publish", data, user=self.other_teacher)
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.state(data), "rascunho")


class VotingStateTests(CicloBase):
    def test_cannot_vote_on_draft_even_as_creator(self):
        data = self.create_enquete(publish=False)
        r = self.vote(self.teacher, data, 0)
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(EnqueteVoto.objects.exists())

    def test_student_vote_on_draft_is_404(self):
        data = self.create_enquete(publish=False)
        r = self.vote(self.student, data, 0)
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(EnqueteVoto.objects.exists())

    def test_cannot_vote_on_closed(self):
        data = self.create_enquete()
        self.post("enquete-close", data)
        r = self.vote(self.student, data, 0)
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(EnqueteVoto.objects.exists())


class VisibilityTests(CicloBase):
    def test_list_shows_published_and_closed_hides_others_drafts(self):
        draft_ = self.create_enquete(publish=False)
        published = self.create_enquete()
        closed = self.create_enquete()
        self.post("enquete-close", closed)

        student_view = self.listed_ids(self.student)
        self.assertNotIn(draft_["id"], student_view)
        self.assertIn(published["id"], student_view)
        self.assertIn(closed["id"], student_view)

        self.assertNotIn(draft_["id"], self.listed_ids(self.other_teacher))
        self.assertIn(draft_["id"], self.listed_ids(self.teacher))

    def test_others_draft_is_404_on_detail_shown_and_dismiss(self):
        """Correcção: antes, outro membro abria e marcava rascunhos alheios."""
        data = self.create_enquete(publish=False)
        self.client.force_authenticate(self.student)
        detail = self.client.get(
            reverse("enquete-detail", args=[data["id"]]), **self.hdr
        )
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)
        for name in ("enquete-shown", "enquete-dismiss"):
            r = self.post(name, data, user=self.other_teacher)
            self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND, name)
        results = self.client.get(
            reverse("enquete-results", args=[data["id"]]), **self.hdr
        )
        self.assertEqual(results.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(EnqueteExibicao.objects.exists())

    def test_creator_sees_own_draft(self):
        data = self.create_enquete(publish=False)
        self.client.force_authenticate(self.teacher)
        r = self.client.get(reverse("enquete-detail", args=[data["id"]]), **self.hdr)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["state"], "rascunho")

    def test_closed_detail_visible_to_students(self):
        data = self.create_enquete()
        self.post("enquete-close", data)
        self.client.force_authenticate(self.student)
        r = self.client.get(reverse("enquete-detail", args=[data["id"]]), **self.hdr)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["state"], "encerrada")


class IsolationTests(CicloBase):
    def test_other_school_cannot_transition(self):
        data = self.create_enquete(publish=False)
        for hdr in (self.foreign_hdr, {}):
            for name in ("enquete-publish", "enquete-close"):
                r = self.post(name, data, user=self.foreign_teacher, hdr=hdr)
                self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND, name)
        r = self.post("enquete-publish", data, user=self.foreign_teacher)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.state(data), "rascunho")

    def test_creator_cannot_transition_from_other_context(self):
        data = self.create_enquete(publish=False)
        r = self.post("enquete-publish", data, hdr={})
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.state(data), "rascunho")
