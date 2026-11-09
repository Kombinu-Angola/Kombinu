"""B3: notificações por workspace (Ponto Cego 3)."""

from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import CustomUser
from apps.notificacoes import services
from apps.notificacoes.models import Notificacao
from apps.tenancy.models import Membership, Organizacao


def make_user(email, user_type="learner"):
    return CustomUser.objects.create_user(
        username=email, email=email, password="pass12345", user_type=user_type
    )


def notif(user, organizacao, key, **extra):
    return Notificacao.objects.create(
        user=user,
        organizacao=organizacao,
        category="conteudo",
        title=f"T {key}",
        source_key=key,
        **extra,
    )


class NotificacaoBase(APITestCase):
    def setUp(self):
        self.org_a = Organizacao.objects.create(name="Escola A", slug="escola-a")
        self.org_b = Organizacao.objects.create(name="Escola B", slug="escola-b")
        self.user = make_user("aluno@test.com")
        self.other = make_user("outro@test.com")
        for u in (self.user, self.other):
            Membership.objects.create(user=u, organizacao=self.org_a, role="student")
        Membership.objects.create(
            user=self.user, organizacao=self.org_b, role="student"
        )
        self.hdr_a = {"HTTP_X_WORKSPACE": str(self.org_a.id)}
        self.hdr_b = {"HTTP_X_WORKSPACE": str(self.org_b.id)}

        self.n_a = notif(self.user, self.org_a, "a1")
        self.n_a2 = notif(
            self.user, self.org_a, "a2", target_type="trilha", target_id=self.org_a.id
        )
        self.n_b = notif(self.user, self.org_b, "b1")
        self.n_m = notif(self.user, None, "m1")
        self.n_other = notif(self.other, self.org_a, "o1")
        self.client.force_authenticate(self.user)

    def ids(self, hdr, **params):
        r = self.client.get(reverse("notification-list"), params, **hdr)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        return {item["id"] for item in r.data["results"]}

    def count(self, hdr):
        r = self.client.get(reverse("notification-unread-count"), **hdr)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        return r.data["count"]


class ListIsolationTests(NotificacaoBase):
    def test_list_only_own_in_active_context(self):
        self.assertEqual(self.ids(self.hdr_a), {str(self.n_a.pk), str(self.n_a2.pk)})
        self.assertEqual(self.ids(self.hdr_b), {str(self.n_b.pk)})
        self.assertEqual(self.ids({}), {str(self.n_m.pk)})

    def test_shape_matches_app_notification(self):
        r = self.client.get(reverse("notification-list"), **self.hdr_a)
        item = next(i for i in r.data["results"] if i["id"] == str(self.n_a2.pk))
        self.assertEqual(
            set(item),
            {"id", "category", "tone", "title", "body", "at", "read", "target"},
        )
        self.assertFalse(item["read"])
        self.assertEqual(item["target"], {"kind": "trilha", "id": str(self.org_a.id)})
        plain = next(i for i in r.data["results"] if i["id"] == str(self.n_a.pk))
        self.assertIsNone(plain["target"])

    def test_unread_filter(self):
        Notificacao.objects.filter(pk=self.n_a.pk).update(read_at=self.n_a.created_at)
        self.assertEqual(self.ids(self.hdr_a, unread="true"), {str(self.n_a2.pk)})

    def test_workspace_without_membership_is_403(self):
        outsider = make_user("fora@test.com")
        self.client.force_authenticate(outsider)
        r = self.client.get(reverse("notification-list"), **self.hdr_a)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        r = self.client.get(reverse("notification-unread-count"), **self.hdr_a)
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)


class UnreadCountTests(NotificacaoBase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_count_per_context(self):
        self.assertEqual(self.count(self.hdr_a), 2)
        self.assertEqual(self.count(self.hdr_b), 1)
        self.assertEqual(self.count({}), 1)

    @patch("apps.notificacoes.views.UnreadCountRateThrottle.rate", "2/min", create=True)
    def test_unread_count_is_throttled(self):
        url = reverse("notification-unread-count")
        for _ in range(2):
            self.assertEqual(self.client.get(url, **self.hdr_a).status_code, 200)
        self.assertEqual(
            self.client.get(url, **self.hdr_a).status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )


class ReadTests(NotificacaoBase):
    def read(self, n, hdr):
        return self.client.post(reverse("notification-read", args=[n.pk]), **hdr)

    def test_mark_read_is_idempotent(self):
        self.assertEqual(self.read(self.n_a, self.hdr_a).status_code, 204)
        self.n_a.refresh_from_db()
        first = self.n_a.read_at
        self.assertIsNotNone(first)
        self.assertEqual(self.read(self.n_a, self.hdr_a).status_code, 204)
        self.n_a.refresh_from_db()
        self.assertEqual(self.n_a.read_at, first)
        self.assertEqual(self.count(self.hdr_a), 1)

    def test_cannot_read_other_users_notification(self):
        r = self.read(self.n_other, self.hdr_a)
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        self.n_other.refresh_from_db()
        self.assertIsNone(self.n_other.read_at)

    def test_cannot_read_notification_from_other_context(self):
        for n, hdr in ((self.n_b, self.hdr_a), (self.n_a, self.hdr_b), (self.n_a, {})):
            self.assertEqual(self.read(n, hdr).status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Notificacao.objects.filter(read_at__isnull=False).exists())

    def test_read_all_only_in_active_context(self):
        r = self.client.post(reverse("notification-read-all"), **self.hdr_a)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data, {"updated": 2})
        unread = set(
            Notificacao.objects.filter(read_at__isnull=True).values_list(
                "pk", flat=True
            )
        )
        self.assertEqual(unread, {self.n_b.pk, self.n_m.pk, self.n_other.pk})


class GenerationTests(APITestCase):
    def setUp(self):
        self.org = Organizacao.objects.create(name="Escola", slug="escola")
        self.org_b = Organizacao.objects.create(name="Outra", slug="outra")
        self.teacher = make_user("prof@test.com", "creator")
        self.s1 = make_user("s1@test.com")
        self.s2 = make_user("s2@test.com")
        self.inactive = make_user("inactivo@test.com")
        self.other_teacher = make_user("prof2@test.com", "creator")
        self.foreign = make_user("b@test.com")
        Membership.objects.create(
            user=self.teacher, organizacao=self.org, role="teacher"
        )
        Membership.objects.create(
            user=self.other_teacher, organizacao=self.org, role="teacher"
        )
        for s in (self.s1, self.s2):
            Membership.objects.create(user=s, organizacao=self.org, role="student")
        Membership.objects.create(
            user=self.inactive, organizacao=self.org, role="student", is_active=False
        )
        Membership.objects.create(
            user=self.foreign, organizacao=self.org_b, role="student"
        )

    def recipients(self, key):
        return set(
            Notificacao.objects.filter(source_key=key).values_list("user_id", flat=True)
        )

    def trilha(self, organizacao):
        return SimpleNamespace(
            pk=self.org.id,
            organizacao=organizacao,
            creator=self.teacher,
            title="Redes I",
            headline="",
            subject="Redes",
        )

    def test_trilha_published_reaches_active_students_of_same_school(self):
        services.notify_trilha_published(self.trilha(self.org))
        key = f"trilha_publicada:{self.org.id}"
        self.assertEqual(self.recipients(key), {self.s1.pk, self.s2.pk})
        self.assertTrue(
            all(
                n.organizacao_id == self.org.id
                for n in Notificacao.objects.filter(source_key=key)
            )
        )

    def test_enquete_published_reaches_all_active_members_except_creator(self):
        enquete = SimpleNamespace(
            pk=self.org_b.id, organizacao=self.org, creator=self.teacher, question="?"
        )
        services.notify_enquete_published(enquete)
        self.assertEqual(
            self.recipients(f"enquete_publicada:{self.org_b.id}"),
            {self.s1.pk, self.s2.pk, self.other_teacher.pk},
        )

    def test_generation_is_idempotent(self):
        services.notify_trilha_published(self.trilha(self.org))
        services.notify_trilha_published(self.trilha(self.org))
        self.assertEqual(Notificacao.objects.count(), 2)

    def test_marketplace_does_not_broadcast(self):
        self.assertEqual(services.notify_trilha_published(self.trilha(None)), 0)
        self.assertFalse(Notificacao.objects.exists())


class TrilhaPublishIntegrationTests(APITestCase):
    """Publicar uma trilha pela API notifica os alunos da escola, uma vez."""

    def test_publish_notifies_school_students_once(self):
        from apps.contents.models import Content
        from apps.trilhas.models import Trilha, TrilhaItem

        org = Organizacao.objects.create(name="Escola", slug="escola")
        org_b = Organizacao.objects.create(name="Outra", slug="outra")
        teacher = make_user("prof@test.com", "creator")
        student = make_user("s@test.com")
        foreign = make_user("f@test.com")
        Membership.objects.create(user=teacher, organizacao=org, role="teacher")
        Membership.objects.create(user=student, organizacao=org, role="student")
        Membership.objects.create(user=foreign, organizacao=org_b, role="student")
        content = Content.objects.create(
            title="C",
            description="d",
            creator=teacher,
            category="tecnologia",
            organizacao=org,
        )
        trilha = Trilha.objects.create(
            organizacao=org, creator=teacher, title="Redes I", subject="Redes"
        )
        TrilhaItem.objects.create(
            trilha=trilha, order=1, kind="conteudo", content=content
        )

        self.client.force_authenticate(teacher)
        hdr = {"HTTP_X_WORKSPACE": str(org.id)}
        url = reverse("trilha-publish", args=[trilha.pk])
        self.assertEqual(self.client.post(url, **hdr).status_code, 200)
        self.assertEqual(self.client.post(url, **hdr).status_code, 200)

        notes = list(Notificacao.objects.all())
        self.assertEqual([n.user_id for n in notes], [student.pk])
        self.assertEqual(notes[0].organizacao_id, org.id)
        self.assertEqual(
            (notes[0].target_type, notes[0].target_id), ("trilha", trilha.pk)
        )

        self.client.force_authenticate(student)
        r = self.client.get(reverse("notification-unread-count"), **hdr)
        self.assertEqual(r.data["count"], 1)


class EnquetePublishIntegrationTests(APITestCase):
    """Publicar uma enquete pela API notifica os membros da escola, excepto o criador."""

    def test_publish_notifies_members(self):
        from apps.enquetes.models import Enquete

        org = Organizacao.objects.create(name="Escola", slug="escola")
        teacher = make_user("prof@test.com", "creator")
        colleague = make_user("prof2@test.com", "creator")
        student = make_user("s@test.com")
        Membership.objects.create(user=teacher, organizacao=org, role="teacher")
        Membership.objects.create(user=colleague, organizacao=org, role="teacher")
        Membership.objects.create(user=student, organizacao=org, role="student")
        enquete = Enquete.objects.create(
            organizacao=org,
            creator=teacher,
            kind="binaria",
            question="Gostaste?",
            decision="d",
            trigger="fim-modulo",
            sample_target=5,
        )
        self.client.force_authenticate(teacher)
        hdr = {"HTTP_X_WORKSPACE": str(org.id)}
        r = self.client.post(reverse("enquete-publish", args=[enquete.pk]), **hdr)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(
            set(Notificacao.objects.values_list("user_id", flat=True)),
            {colleague.pk, student.pk},
        )
        n = Notificacao.objects.get(user=student)
        self.assertEqual((n.target_type, n.target_id), ("enquete", enquete.pk))
        self.assertEqual(n.organizacao_id, org.id)
