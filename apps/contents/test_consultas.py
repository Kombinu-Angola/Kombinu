"""A listagem e o detalhe de conteúdos têm um número de consultas constante."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import CustomUser
from apps.contents.models import Content
from apps.quizzes.models import Quiz
from apps.tenancy.models import Membership, Organizacao


class ContentQueryCountTests(APITestCase):
    def setUp(self):
        self.org = Organizacao.objects.create(name="Escola A", slug="escola-a")
        self.user = CustomUser.objects.create_user(
            username="leitor@escola.ao",
            email="leitor@escola.ao",
            password="x",
            user_type="learner",
        )
        Membership.objects.create(user=self.user, organizacao=self.org)
        self.client.force_authenticate(self.user)
        self.n = 0

    def add_contents(self, count, organizacao=None):
        for _ in range(count):
            self.n += 1
            # Cada conteúdo com o seu autor, e metade com quiz: é o pior caso
            # para o N+1 (`creator` e a relação inversa `quiz`).
            creator = CustomUser.objects.create_user(
                username=f"autor{self.n}@escola.ao",
                email=f"autor{self.n}@escola.ao",
                password="x",
                first_name="Autor",
                last_name=str(self.n),
                user_type="creator",
            )
            content = Content.objects.create(
                title=f"Conteúdo {self.n}",
                description="d",
                creator=creator,
                category="tecnologia",
                organizacao=organizacao,
            )
            if self.n % 2:
                Quiz.objects.create(
                    title=f"Quiz {self.n}", content=content, organizacao=organizacao
                )

    def count_list(self, **extra):
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get(reverse("content-list"), **extra)
        self.assertEqual(r.status_code, 200)
        return len(ctx), r.data

    def test_marketplace_list_is_constant(self):
        self.add_contents(4)
        small, data = self.count_list()
        self.assertEqual(len(data["results"]), 4)
        self.add_contents(16)
        large, data = self.count_list()
        self.assertEqual(len(data["results"]), 20)
        self.assertEqual(small, large)
        # COUNT da paginação + a página (com `creator` e `quiz` no JOIN).
        self.assertEqual(large, 2)

    def test_workspace_list_is_constant(self):
        hdr = {"HTTP_X_WORKSPACE": str(self.org.pk)}
        self.add_contents(4, self.org)
        small, _ = self.count_list(**hdr)
        self.add_contents(16, self.org)
        large, data = self.count_list(**hdr)
        self.assertEqual(len(data["results"]), 20)
        self.assertEqual(small, large)
        # + a validação da Membership do X-Workspace.
        self.assertEqual(large, 3)

    def test_has_quiz_filter_is_constant(self):
        self.add_contents(4)
        small, _ = self.count_list(QUERY_STRING="has_quiz=true")
        self.add_contents(16)
        large, data = self.count_list(QUERY_STRING="has_quiz=false")
        self.assertEqual(small, large)
        self.assertTrue(all(not row["has_quiz"] for row in data["results"]))

    def test_contract_is_unchanged(self):
        self.add_contents(2)
        _, data = self.count_list()
        by_title = {row["title"]: row for row in data["results"]}
        with_quiz = Content.objects.get(title="Conteúdo 1")
        without_quiz = Content.objects.get(title="Conteúdo 2")
        self.assertTrue(by_title["Conteúdo 1"]["has_quiz"])
        self.assertEqual(by_title["Conteúdo 1"]["quiz_id"], str(with_quiz.quiz.id))
        self.assertFalse(by_title["Conteúdo 2"]["has_quiz"])
        self.assertIsNone(by_title["Conteúdo 2"]["quiz_id"])
        self.assertEqual(
            by_title["Conteúdo 2"]["creator"],
            {"id": without_quiz.creator_id, "name": "Autor 2"},
        )

    def test_detail_query_count(self):
        self.add_contents(2)
        for content in Content.objects.all():
            with CaptureQueriesContext(connection) as ctx:
                r = self.client.get(reverse("content-detail", args=[content.pk]))
            self.assertEqual(r.status_code, 200)
            self.assertEqual(len(ctx), 1, [q["sql"] for q in ctx])
