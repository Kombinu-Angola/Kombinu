"""C-K4: `cadeira` exposta e gravável em conteúdos, quizzes e trilhas."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import CustomUser
from apps.contents.models import Cadeira, Content
from apps.quizzes.models import Quiz
from apps.tenancy.models import Membership, Organizacao
from apps.trilhas.models import Trilha

QUESTIONS = [{"question": "2 + 2?", "options": ["3", "4"], "correctAnswer": 1}]


def make_user(email, user_type="learner"):
    return CustomUser.objects.create_user(
        username=email, email=email, password="pass12345", user_type=user_type
    )


class CadeiraSerializersBase(APITestCase):
    def setUp(self):
        self.direito = Cadeira.objects.create(
            nome="Direito Constitucional", curso="Direito"
        )
        self.calculo = Cadeira.objects.create(nome="Cálculo I", curso="Engenharia")
        self.criador = make_user("criador@test.com", "creator")
        self.outro = make_user("outro@test.com", "creator")
        self.client.force_authenticate(self.criador)

    def expected(self, cadeira):
        return {"id": cadeira.pk, "nome": cadeira.nome, "curso": cadeira.curso}

    def create_content(self, **extra):
        data = {"title": "Aula", "description": "d", "category": "tecnologia"}
        data.update(extra)
        return self.client.post(reverse("content-list"), data, format="json")


class ContentCadeiraTests(CadeiraSerializersBase):
    def test_create_reads_back_nested_cadeira(self):
        r = self.create_content(cadeira=self.direito.pk)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["cadeira"], self.expected(self.direito))
        detail = self.client.get(reverse("content-detail", args=[r.data["id"]]))
        self.assertEqual(detail.data["cadeira"], self.expected(self.direito))
        listing = self.client.get(reverse("content-list"))
        self.assertEqual(
            listing.data["results"][0]["cadeira"], self.expected(self.direito)
        )

    def test_without_cadeira_is_null(self):
        r = self.create_content()
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertIsNone(r.data["cadeira"])

    def test_edit_changes_and_clears_cadeira(self):
        content_id = self.create_content(cadeira=self.direito.pk).data["id"]
        url = reverse("content-detail", args=[content_id])
        r = self.client.patch(url, {"cadeira": self.calculo.pk}, format="json")
        self.assertEqual(r.data["cadeira"], self.expected(self.calculo))
        r = self.client.patch(url, {"cadeira": None}, format="json")
        self.assertIsNone(r.data["cadeira"])
        self.assertIsNone(Content.objects.get(pk=content_id).cadeira)

    def test_invalid_cadeira_is_400_in_portuguese(self):
        r = self.create_content(cadeira=999999)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(r.data["cadeira"][0]), "Cadeira não encontrada.")
        r = self.create_content(cadeira="direito")
        self.assertEqual(str(r.data["cadeira"][0]), "Indica a cadeira pelo id.")

    def test_only_the_owner_edits_cadeira(self):
        content_id = self.create_content(cadeira=self.direito.pk).data["id"]
        self.client.force_authenticate(self.outro)
        r = self.client.patch(
            reverse("content-detail", args=[content_id]),
            {"cadeira": self.calculo.pk},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Content.objects.get(pk=content_id).cadeira, self.direito)

    def test_list_query_count_does_not_grow_with_cadeira(self):
        for i in range(3):
            Content.objects.create(
                title=f"C{i}",
                description="d",
                creator=self.criador,
                category="tecnologia",
                cadeira=self.direito if i % 2 else self.calculo,
            )
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(reverse("content-list"))
        self.assertEqual(len(ctx), 2)


class QuizCadeiraTests(CadeiraSerializersBase):
    def setUp(self):
        super().setUp()
        self.content = Content.objects.create(
            title="Aula", description="d", creator=self.criador, category="tecnologia"
        )
        self.url = reverse("quiz-manual-create", args=[self.content.pk])

    def test_manual_creation_accepts_cadeira_and_detail_shows_it(self):
        r = self.client.post(
            self.url,
            {"questions": QUESTIONS, "cadeira": self.direito.pk},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        detail = self.client.get(reverse("quiz-detail", args=[r.data["quiz_id"]]))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["cadeira"], self.expected(self.direito))

    def test_manual_creation_without_or_with_null_cadeira(self):
        r = self.client.post(
            self.url, {"questions": QUESTIONS, "cadeira": None}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        detail = self.client.get(reverse("quiz-detail", args=[r.data["quiz_id"]]))
        self.assertIsNone(detail.data["cadeira"])

    def test_manual_creation_with_invalid_cadeira_creates_nothing(self):
        r = self.client.post(
            self.url, {"questions": QUESTIONS, "cadeira": 999999}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(r.data["cadeira"][0]), "Cadeira não encontrada.")
        self.assertFalse(Quiz.objects.filter(content=self.content).exists())

    def test_other_creator_still_cannot_create_the_quiz(self):
        self.client.force_authenticate(self.outro)
        r = self.client.post(
            self.url,
            {"questions": QUESTIONS, "cadeira": self.direito.pk},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class TrilhaCadeiraTests(CadeiraSerializersBase):
    def create_trilha(self, **extra):
        data = {"title": "Trilha", "subject": "Direito"}
        data.update(extra)
        return self.client.post(reverse("trilha-list"), data, format="json")

    def test_create_and_read_cadeira(self):
        r = self.create_trilha(cadeira=self.direito.pk)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["cadeira"], self.expected(self.direito))
        detail = self.client.get(reverse("trilha-detail", args=[r.data["id"]]))
        self.assertEqual(detail.data["cadeira"], self.expected(self.direito))
        listing = self.client.get(reverse("trilha-list"))
        self.assertEqual(
            listing.data["results"][0]["cadeira"], self.expected(self.direito)
        )
        # O `subject` em texto mantém-se.
        self.assertEqual(r.data["subject"], "Direito")

    def test_patch_changes_and_clears_cadeira(self):
        trilha_id = self.create_trilha().data["id"]
        url = reverse("trilha-detail", args=[trilha_id])
        r = self.client.patch(url, {"cadeira": self.calculo.pk}, format="json")
        self.assertEqual(r.data["cadeira"], self.expected(self.calculo))
        r = self.client.patch(url, {"cadeira": None}, format="json")
        self.assertIsNone(r.data["cadeira"])

    def test_invalid_cadeira_is_400(self):
        r = self.create_trilha(cadeira=999999)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(r.data["cadeira"][0]), "Cadeira não encontrada.")
        self.assertFalse(Trilha.objects.exists())

    def test_only_the_author_edits_cadeira(self):
        trilha_id = self.create_trilha(cadeira=self.direito.pk).data["id"]
        Trilha.objects.filter(pk=trilha_id).update(is_published=True)
        self.client.force_authenticate(self.outro)
        r = self.client.patch(
            reverse("trilha-detail", args=[trilha_id]),
            {"cadeira": self.calculo.pk},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Trilha.objects.get(pk=trilha_id).cadeira, self.direito)


class CadeiraIsolationTests(CadeiraSerializersBase):
    def test_same_cadeira_in_another_school_is_not_listed(self):
        escola_a = Organizacao.objects.create(name="Escola A", slug="escola-a")
        escola_b = Organizacao.objects.create(name="Escola B", slug="escola-b")
        prof_a = make_user("prof-a@test.com")
        prof_b = make_user("prof-b@test.com")
        Membership.objects.create(user=prof_a, organizacao=escola_a, role="teacher")
        Membership.objects.create(user=prof_b, organizacao=escola_b, role="teacher")

        self.client.force_authenticate(prof_b)
        r = self.client.post(
            reverse("content-list"),
            {
                "title": "Aula da escola B",
                "description": "d",
                "category": "tecnologia",
                "cadeira": self.direito.pk,
            },
            format="json",
            HTTP_X_WORKSPACE=str(escola_b.pk),
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["organizacao"], escola_b.pk)

        self.client.force_authenticate(prof_a)
        for extra in ({"HTTP_X_WORKSPACE": str(escola_a.pk)}, {}):
            listing = self.client.get(
                reverse("content-list"), {"cadeira": self.direito.pk}, **extra
            )
            self.assertEqual(listing.status_code, status.HTTP_200_OK)
            self.assertEqual(listing.data["results"], [])
