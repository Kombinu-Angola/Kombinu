from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import CustomUser
from apps.enquetes.models import Enquete, EnqueteExibicao, EnqueteVoto
from apps.enquetes.services import ENQUETE_VOTE_XP
from apps.rankings.models import XPEvent
from apps.tenancy.models import Membership, Organizacao


def make_user(email, user_type="learner"):
    return CustomUser.objects.create_user(
        username=email, email=email, password="pass12345", user_type=user_type
    )


def draft(**overrides):
    body = {
        "decision": "Manter o horário de exames?",
        "kind": "escolha",
        "question": "Qual formato preferes?",
        "options": ["Presencial", "Online", "Misto"],
        "faculty": "Engenharia",
        "subject": "Redes",
        "trigger": "fim-simulado",
        "sampleTarget": 100,
        "segmentSize": 300,
    }
    body.update(overrides)
    return body


class EnqueteBase(APITestCase):
    def setUp(self):
        self.org = Organizacao.objects.create(name="Uni A", slug="uni-a")
        self.other_org = Organizacao.objects.create(name="Uni B", slug="uni-b")
        self.teacher = make_user("prof@test.com", "creator")
        Membership.objects.create(user=self.teacher, organizacao=self.org, role="teacher")
        self.students = []
        for i, year in enumerate(["1º ano", "1º ano", "2º ano", "2º ano", "2º ano"]):
            u = make_user(f"aluno{i}@test.com")
            Membership.objects.create(
                user=u, organizacao=self.org, role="student", academic_year=year
            )
            self.students.append(u)
        self.hdr = {"HTTP_X_WORKSPACE": str(self.org.id)}

    def create_enquete(self, **overrides):
        self.client.force_authenticate(self.teacher)
        r = self.client.post(
            reverse("enquete-list"), draft(**overrides), format="json", **self.hdr
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        return r.data

    def vote(self, user, enquete, option_index, **extra):
        self.client.force_authenticate(user)
        opt = enquete["options"][option_index]["id"]
        return self.client.post(
            reverse("enquete-vote", args=[enquete["id"]]),
            {"optionId": opt},
            format="json",
            **(extra or self.hdr),
        )


class EnqueteCreateTests(EnqueteBase):
    def test_create_matches_survey_draft_shape(self):
        data = self.create_enquete()
        self.assertEqual(data["kind"], "escolha")
        self.assertEqual(data["trigger"], "fim-simulado")
        self.assertEqual(data["sampleTarget"], 100)
        self.assertEqual(data["segmentSize"], 300)
        self.assertEqual(data["state"], "activa")
        self.assertEqual(
            [o["label"] for o in data["options"]], ["Presencial", "Online", "Misto"]
        )
        e = Enquete.objects.get(pk=data["id"])
        self.assertEqual(e.organizacao_id, self.org.id)
        self.assertEqual(e.creator_id, self.teacher.pk)

    def test_escala_options_get_numeric_values(self):
        data = self.create_enquete(kind="escala", options=["1", "2", "3", "4", "5"])
        self.assertEqual([o["value"] for o in data["options"]], [1, 2, 3, 4, 5])

    def test_binaria_requires_exactly_two_options(self):
        self.client.force_authenticate(self.teacher)
        r = self.client.post(
            reverse("enquete-list"),
            draft(kind="binaria", options=["Sim", "Não", "Talvez"]),
            format="json",
            **self.hdr,
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        r = self.client.post(
            reverse("enquete-list"),
            draft(kind="binaria", options=["Sim", "Não"]),
            format="json",
            **self.hdr,
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_invalid_drafts_rejected(self):
        self.client.force_authenticate(self.teacher)
        for bad in (
            {"options": ["só uma"]},
            {"options": ["a", "A"]},
            {"trigger": "agora"},
            {"sampleTarget": 0},
            {"kind": "aberta"},
        ):
            r = self.client.post(
                reverse("enquete-list"), draft(**bad), format="json", **self.hdr
            )
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, bad)

    def test_student_cannot_create(self):
        self.client.force_authenticate(self.students[0])
        r = self.client.post(
            reverse("enquete-list"), draft(), format="json", **self.hdr
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_voter_view_hides_decision(self):
        data = self.create_enquete()
        self.client.force_authenticate(self.students[0])
        r = self.client.get(reverse("enquete-detail", args=[data["id"]]), **self.hdr)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertNotIn("decision", r.data)
        self.assertFalse(r.data["hasVoted"])
        self.assertNotIn("decision", str(r.data))


class EnqueteVoteTests(EnqueteBase):
    def test_vote_counts_and_awards_xp_once(self):
        e = self.create_enquete()
        r = self.vote(self.students[0], e, 0)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["xpEarned"], ENQUETE_VOTE_XP)
        self.assertEqual(EnqueteVoto.objects.filter(enquete_id=e["id"]).count(), 1)
        xp = XPEvent.objects.get(user=self.students[0])
        self.assertEqual((xp.amount, xp.source_type), (5, "enquete_voto"))
        self.assertEqual(xp.organizacao_id, self.org.id)

    def test_second_vote_by_same_user_fails(self):
        e = self.create_enquete()
        self.assertEqual(self.vote(self.students[0], e, 0).status_code, 201)
        r = self.vote(self.students[0], e, 1)  # mesmo utilizador, outra opção
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(EnqueteVoto.objects.filter(enquete_id=e["id"]).count(), 1)
        self.assertEqual(XPEvent.objects.filter(user=self.students[0]).count(), 1)

    def test_option_from_another_enquete_rejected(self):
        e1 = self.create_enquete()
        e2 = self.create_enquete(question="Outra?")
        self.client.force_authenticate(self.students[0])
        r = self.client.post(
            reverse("enquete-vote", args=[e1["id"]]),
            {"optionId": e2["options"][0]["id"]},
            format="json",
            **self.hdr,
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(EnqueteVoto.objects.exists())

    def test_closes_when_sample_target_reached(self):
        e = self.create_enquete(sampleTarget=2)
        self.assertEqual(self.vote(self.students[0], e, 0).status_code, 201)
        self.assertEqual(self.vote(self.students[1], e, 1).status_code, 201)
        enquete = Enquete.objects.get(pk=e["id"])
        self.assertEqual(enquete.state, "encerrada")
        self.assertIsNotNone(enquete.closed_at)
        r = self.vote(self.students[2], e, 0)
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(EnqueteVoto.objects.count(), 2)

    def test_vote_stamps_year_snapshot(self):
        e = self.create_enquete()
        self.vote(self.students[2], e, 0)
        self.assertEqual(EnqueteVoto.objects.get().year_snapshot, "2º ano")

    def test_has_voted_flag(self):
        e = self.create_enquete()
        self.vote(self.students[0], e, 0)
        self.client.force_authenticate(self.students[0])
        r = self.client.get(reverse("enquete-detail", args=[e["id"]]), **self.hdr)
        self.assertTrue(r.data["hasVoted"])


class EnqueteResultsTests(EnqueteBase):
    """Contagem de votos e agregação (SLA §8.4, D10: percentagens 0–100)."""

    def _results(self, e):
        self.client.force_authenticate(self.teacher)
        r = self.client.get(reverse("enquete-results", args=[e["id"]]), **self.hdr)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        return r.data

    def test_vote_counting_distribution_and_by_year(self):
        e = self.create_enquete()
        # 1º ano: s0->Presencial, s1->Online ; 2º ano: s2,s3->Online, s4->Misto
        for student, idx in zip(self.students, [0, 1, 1, 1, 2]):
            self.assertEqual(self.vote(student, e, idx).status_code, 201)
        res = self._results(e)

        self.assertEqual(res["answers"], 5)
        self.assertEqual(
            res["distribution"],
            [
                {"label": "Presencial", "value": 20.0},
                {"label": "Online", "value": 60.0},
                {"label": "Misto", "value": 20.0},
            ],
        )
        self.assertAlmostEqual(sum(d["value"] for d in res["distribution"]), 100.0)

        by_year = {y["year"]: y for y in res["byYear"]}
        self.assertEqual(by_year["1º ano"]["answers"], 2)
        # empate no 1º ano: desempata pela ordem das opções (Presencial)
        self.assertEqual(by_year["1º ano"]["topChoice"], "Presencial")
        self.assertEqual(by_year["1º ano"]["share"], 50.0)
        self.assertEqual(by_year["2º ano"]["answers"], 3)
        self.assertEqual(by_year["2º ano"]["topChoice"], "Online")
        self.assertEqual(by_year["2º ano"]["share"], 66.7)

    def test_shown_and_dismissed_counts(self):
        e = self.create_enquete()
        url = lambda name: reverse(name, args=[e["id"]])  # noqa: E731
        self.client.force_authenticate(self.students[0])
        self.assertEqual(self.client.post(url("enquete-shown"), **self.hdr).status_code, 204)
        self.client.force_authenticate(self.students[1])
        self.assertEqual(self.client.post(url("enquete-dismiss"), **self.hdr).status_code, 204)
        self.vote(self.students[2], e, 0)

        res = self._results(e)
        self.assertEqual(res["shown"], 3)
        self.assertEqual(res["dismissed"], 1)
        self.assertEqual(res["answers"], 1)

    def test_dismiss_after_vote_does_not_override(self):
        e = self.create_enquete()
        self.vote(self.students[0], e, 0)
        self.client.force_authenticate(self.students[0])
        self.client.post(reverse("enquete-dismiss", args=[e["id"]]), **self.hdr)
        self.assertEqual(EnqueteExibicao.objects.get().outcome, "respondida")

    def test_empty_results_have_zero_percentages(self):
        e = self.create_enquete()
        res = self._results(e)
        self.assertEqual(res["answers"], 0)
        self.assertEqual([d["value"] for d in res["distribution"]], [0, 0, 0])
        self.assertEqual(res["byYear"], [])
        self.assertIsNone(res["closedAt"])

    def test_result_shape_matches_survey_result(self):
        e = self.create_enquete(sampleTarget=1)
        self.vote(self.students[0], e, 0)
        res = self._results(e)
        self.assertEqual(
            set(res),
            {"question", "decision", "subject", "closedAt", "answers", "dismissed",
             "shown", "distribution", "byYear"},
        )
        self.assertIsInstance(res["closedAt"], str)
        self.assertEqual(set(res["byYear"][0]), {"year", "answers", "topChoice", "share"})

    def test_results_only_for_creator_and_expose_no_identity(self):
        e = self.create_enquete()
        self.vote(self.students[0], e, 0)
        self.client.force_authenticate(self.students[0])
        r = self.client.get(reverse("enquete-results", args=[e["id"]]), **self.hdr)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

        res = self._results(e)
        blob = str(res)
        self.assertNotIn("@", blob)
        self.assertNotIn("user", blob.lower())


class EnqueteIsolationTests(EnqueteBase):
    def test_enquete_not_visible_from_other_context(self):
        e = self.create_enquete()
        outsider = make_user("fora@test.com")
        Membership.objects.create(user=outsider, organizacao=self.other_org)
        self.client.force_authenticate(outsider)
        url = reverse("enquete-detail", args=[e["id"]])

        r = self.client.get(url, HTTP_X_WORKSPACE=str(self.other_org.id))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        r = self.client.get(url)  # marketplace
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        r = self.client.get(url, HTTP_X_WORKSPACE=str(self.org.id))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

        r = self.vote(outsider, e, 0, HTTP_X_WORKSPACE=str(self.other_org.id))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(EnqueteVoto.objects.exists())

    def test_list_is_scoped(self):
        self.create_enquete()
        self.client.force_authenticate(self.students[0])
        r = self.client.get(reverse("enquete-list"), **self.hdr)
        self.assertEqual(len(r.data["results"]), 1)
        r = self.client.get(reverse("enquete-list"))  # marketplace
        self.assertEqual(r.data["results"], [])
