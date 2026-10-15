from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import CustomUser
from apps.contents.models import Content
from apps.quizzes.models import Option, Question, Quiz
from apps.tenancy.models import Membership, Organizacao


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
        for method, payload in (("put", {
            "title": "x", "description": "x", "category": "design"}),
            ("patch", {"title": "x"}), ("delete", None)):
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
            {"questions": [{"question": "q", "options": ["a", "b"], "correctAnswer": 0}]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Quiz.objects.filter(content=self.content).exists())

    def test_owner_can_create_manual_quiz(self):
        self.client.force_authenticate(self.owner)
        man = reverse("quiz-manual-create", args=[self.content.id])
        r = self.client.post(
            man,
            {"questions": [{"question": "q", "options": ["a", "b"], "correctAnswer": 0}]},
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
            {"answers": [{"question_id": str(question.id), "selected_option_id": str(option.id)}]},
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
