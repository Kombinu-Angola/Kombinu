from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import CustomUser
from apps.contents.models import Content
from apps.quizzes.models import Option, Question, Quiz
from apps.tenancy.codes import ORG_CODE_ALPHABET, ORG_CODE_LENGTH
from apps.tenancy.models import Membership, Organizacao, ProvisionamentoLote


def make_user(email, user_type="learner"):
    return CustomUser.objects.create_user(
        username=email, email=email, password="pass12345", user_type=user_type
    )


def make_content(creator, title="Conteúdo", organizacao=None):
    return Content.objects.create(
        title=title,
        description="d",
        creator=creator,
        category="tecnologia",
        organizacao=organizacao,
    )


def make_quiz(content, organizacao=None):
    quiz = Quiz.objects.create(
        title=f"Quiz: {content.title}", content=content, organizacao=organizacao
    )
    question = Question.objects.create(quiz=quiz, question_text="2+2?")
    Option.objects.create(question=question, text="4", is_correct=True)
    Option.objects.create(question=question, text="5", is_correct=False)
    return quiz


class ContentOwnershipTests(APITestCase):
    """R7: só o criador altera/apaga o seu conteúdo."""

    def setUp(self):
        self.owner = make_user("owner@test.com", "creator")
        self.other = make_user("other@test.com", "creator")
        self.learner = make_user("learner@test.com")
        self.content = make_content(self.owner)
        self.detail = reverse("content-detail", args=[self.content.id])

    def test_owner_can_update_and_delete(self):
        self.client.force_authenticate(self.owner)
        r = self.client.patch(self.detail, {"title": "Novo"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        r = self.client.delete(self.detail)
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)

    def test_other_creator_cannot_update_or_delete(self):
        self.client.force_authenticate(self.other)
        for method, payload in (
            ("put", {"title": "x", "description": "x", "category": "design"}),
            ("patch", {"title": "x"}),
            ("delete", None),
        ):
            r = getattr(self.client, method)(self.detail, payload, format="json")
            self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN, method)
        self.content.refresh_from_db()
        self.assertEqual(self.content.title, "Conteúdo")

    def test_learner_cannot_update_or_delete(self):
        self.client.force_authenticate(self.learner)
        self.assertEqual(
            self.client.delete(self.detail).status_code, status.HTTP_403_FORBIDDEN
        )
        self.assertTrue(Content.objects.filter(pk=self.content.pk).exists())

    def test_others_can_still_read(self):
        self.client.force_authenticate(self.learner)
        self.assertEqual(self.client.get(self.detail).status_code, status.HTTP_200_OK)

    def test_other_creator_cannot_generate_or_create_quiz(self):
        self.client.force_authenticate(self.other)
        gen = reverse("quiz-generate", args=[self.content.id])
        man = reverse("quiz-manual-create", args=[self.content.id])
        r = self.client.post(gen, {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        r = self.client.post(
            man,
            {
                "questions": [
                    {"question": "q", "options": ["a", "b"], "correctAnswer": 0}
                ]
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Quiz.objects.filter(content=self.content).exists())

    def test_owner_can_create_manual_quiz(self):
        self.client.force_authenticate(self.owner)
        man = reverse("quiz-manual-create", args=[self.content.id])
        r = self.client.post(
            man,
            {
                "questions": [
                    {"question": "q", "options": ["a", "b"], "correctAnswer": 0}
                ]
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)


class ProtectHistoryTests(APITestCase):
    """R5: apagar não destrói o histórico dos alunos."""

    def setUp(self):
        self.owner = make_user("prot-owner@test.com", "creator")
        self.learner = make_user("prot-learner@test.com")
        self.content = make_content(self.owner)
        self.quiz = make_quiz(self.content)

    def _submit(self):
        question = self.quiz.questions.get()
        option = question.options.get(is_correct=True)
        self.client.force_authenticate(self.learner)
        return self.client.post(
            reverse("quiz-submit", args=[self.quiz.id]),
            {
                "answers": [
                    {
                        "question_id": str(question.id),
                        "selected_option_id": str(option.id),
                    }
                ]
            },
            format="json",
        )

    def test_content_with_submissions_cannot_be_deleted(self):
        from apps.quizzes.models import QuizSubmission

        self.assertEqual(self._submit().status_code, status.HTTP_200_OK)
        self.client.force_authenticate(self.owner)
        r = self.client.delete(reverse("content-detail", args=[self.content.id]))
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(Content.objects.filter(pk=self.content.pk).exists())
        self.assertEqual(QuizSubmission.objects.count(), 1)

    def test_creator_with_content_cannot_be_deleted(self):
        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            self.owner.delete()

    def test_content_without_submissions_can_be_deleted(self):
        self.client.force_authenticate(self.owner)
        r = self.client.delete(reverse("content-detail", args=[self.content.id]))
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)


class AuthInstitucionalModelosTests(TestCase):
    """Campos da auth institucional (D2, D5–D7) e auditoria do lote."""

    def setUp(self):
        self.org_a = Organizacao.objects.create(name="Escola A", slug="escola-a")
        self.org_b = Organizacao.objects.create(name="Escola B", slug="escola-b")

    def test_organization_gets_short_unambiguous_code(self):
        for org in (self.org_a, self.org_b):
            self.assertEqual(len(org.code), ORG_CODE_LENGTH)
            self.assertTrue(set(org.code) <= set(ORG_CODE_ALPHABET))
        self.assertNotEqual(self.org_a.code, self.org_b.code)

    def test_code_is_kept_on_save_and_normalized_when_given(self):
        original = self.org_a.code
        self.org_a.name = "Escola A renomeada"
        self.org_a.save()
        self.org_a.refresh_from_db()
        self.assertEqual(self.org_a.code, original)

        org = Organizacao.objects.create(name="C", slug="escola-c", code=" ab c23 ")
        self.assertEqual(org.code, "ABC23")

    def test_code_is_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Organizacao.objects.create(name="Dup", slug="dup", code=self.org_a.code)

    def test_student_code_is_normalized_and_unique_per_organization(self):
        u1, u2, u3 = (make_user(f"s{i}@test.com") for i in range(3))
        m1 = Membership.objects.create(
            user=u1, organizacao=self.org_a, student_code=" 2024 - 0001 "
        )
        self.assertEqual(m1.student_code, "2024-0001")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Membership.objects.create(
                user=u2, organizacao=self.org_a, student_code="2024-0001"
            )
        # O mesmo número noutra escola é outra pessoa.
        Membership.objects.create(
            user=u2, organizacao=self.org_b, student_code="2024-0001"
        )

    def test_memberships_without_student_code_do_not_collide(self):
        u1, u2 = make_user("a@test.com"), make_user("b@test.com")
        m1 = Membership.objects.create(
            user=u1, organizacao=self.org_a, student_code="  "
        )
        m2 = Membership.objects.create(user=u2, organizacao=self.org_a)
        self.assertIsNone(m1.student_code)
        self.assertIsNone(m2.student_code)

    def test_user_auth_flags_default_off(self):
        user = make_user("novo@test.com")
        self.assertFalse(user.must_change_password)
        self.assertIsNone(user.password_changed_at)
        self.assertIsNone(user.temp_password_expires_at)

    def test_organization_with_provisioning_audit_cannot_be_deleted(self):
        admin = make_user("admin@test.com")
        ProvisionamentoLote.objects.create(
            organizacao=self.org_a, created_by=admin, accounts_created=3
        )
        with self.assertRaises(ProtectedError):
            self.org_a.delete()


class XWorkspaceSchemaTests(TestCase):
    """O OpenAPI documenta o header `X-Workspace` onde o scoping se aplica."""

    @classmethod
    def setUpTestData(cls):
        from drf_spectacular.generators import SchemaGenerator

        cls.schema = SchemaGenerator().get_schema(request=None, public=True)

    def _headers(self, path, method):
        op = self.schema["paths"][path][method]
        return [p["name"] for p in op.get("parameters", []) if p["in"] == "header"]

    def test_scoped_endpoints_document_x_workspace(self):
        for path, method in (
            ("/api/contents/", "get"),
            ("/api/rankings/global/", "get"),
            ("/api/quizzes/{quiz_id}/submit/", "post"),
            ("/api/trilhas/", "get"),
            ("/api/enquetes/", "get"),
            ("/api/dashboard/learner/stats/", "get"),
        ):
            self.assertIn("X-Workspace", self._headers(path, method), path)

    def test_auth_endpoints_do_not(self):
        for path in ("/api/auth/login/", "/api/auth/register/"):
            self.assertNotIn("X-Workspace", self._headers(path, "post"), path)
