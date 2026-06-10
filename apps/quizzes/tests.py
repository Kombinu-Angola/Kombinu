from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from unittest.mock import patch, MagicMock
from apps.accounts.models import CustomUser
from apps.contents.models import Content
from apps.quizzes.models import Quiz, Question, Option, QuizSubmission, QuizAnswer


class QuizModelTest(TestCase):
    def setUp(self):
        self.creator = CustomUser.objects.create_user(
            username="creator@example.com",
            email="creator@example.com",
            password="creatorpass123",
            user_type="creator"
        )
        self.content = Content.objects.create(
            title="Test Content",
            description="Test description",
            creator=self.creator,
            category="tecnologia"
        )
        self.quiz = Quiz.objects.create(
            title="Test Quiz",
            content=self.content
        )

    def test_quiz_creation(self):
        """Testa se o quiz foi criado corretamente"""
        self.assertEqual(self.quiz.title, "Test Quiz")
        self.assertEqual(self.quiz.content, self.content)

    def test_content_has_quiz_after_creation(self):
        """Testa se o conteúdo reconhece que tem um quiz"""
        self.assertTrue(self.content.has_quiz)
        self.assertEqual(self.content.quiz_id, self.quiz.id)

    def test_one_to_one_relationship(self):
        """Testa que um conteúdo pode ter apenas um quiz"""
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Quiz.objects.create(
                title="Another Quiz",
                content=self.content  # Mesmo conteúdo
            )


class QuestionAndOptionModelTest(TestCase):
    def setUp(self):
        creator = CustomUser.objects.create_user(
            username="creator@example.com",
            email="creator@example.com",
            password="creatorpass123",
            user_type="creator"
        )
        content = Content.objects.create(
            title="Test Content",
            description="Test description",
            creator=creator,
            category="tecnologia"
        )
        self.quiz = Quiz.objects.create(title="Test Quiz", content=content)
        self.question = Question.objects.create(
            quiz=self.quiz,
            question_text="What is 2+2?"
        )
        self.correct_option = Option.objects.create(
            question=self.question,
            text="4",
            is_correct=True
        )
        self.wrong_option = Option.objects.create(
            question=self.question,
            text="5",
            is_correct=False
        )

    def test_question_creation(self):
        """Testa se a questão foi criada corretamente"""
        self.assertEqual(self.question.question_text, "What is 2+2?")
        self.assertEqual(self.question.quiz, self.quiz)

    def test_options_creation(self):
        """Testa se as opções foram criadas corretamente"""
        self.assertTrue(self.correct_option.is_correct)
        self.assertFalse(self.wrong_option.is_correct)

    def test_question_has_multiple_options(self):
        """Testa se a questão tem múltiplas opções"""
        self.assertEqual(self.question.options.count(), 2)

    def test_question_belongs_to_quiz(self):
        """Testa que a questão pertence ao quiz"""
        self.assertIn(self.question, self.quiz.questions.all())


class QuizSubmissionModelTest(TestCase):
    def setUp(self):
        self.learner = CustomUser.objects.create_user(
            username="learner@example.com",
            email="learner@example.com",
            password="learnerpass123",
            user_type="learner"
        )
        creator = CustomUser.objects.create_user(
            username="creator@example.com",
            email="creator@example.com",
            password="creatorpass123",
            user_type="creator"
        )
        content = Content.objects.create(
            title="Test Content",
            description="Test description",
            creator=creator,
            category="tecnologia"
        )
        self.quiz = Quiz.objects.create(title="Test Quiz", content=content)
        self.submission = QuizSubmission.objects.create(
            user=self.learner,
            quiz=self.quiz,
            score=8
        )

    def test_submission_creation(self):
        """Testa se a submissão foi criada corretamente"""
        self.assertEqual(self.submission.user, self.learner)
        self.assertEqual(self.submission.quiz, self.quiz)
        self.assertEqual(self.submission.score, 8)

    def test_unique_submission_constraint(self):
        """Testa se não é possível criar submissões duplicadas"""
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            QuizSubmission.objects.create(
                user=self.learner,
                quiz=self.quiz,
                score=5
            )

    def test_submission_str_representation(self):
        """Testa a representação string da submissão"""
        expected = f"{self.learner.email} - {self.quiz.title} - Score: 8"
        self.assertEqual(str(self.submission), expected)


class QuizAnswerModelTest(TestCase):
    def setUp(self):
        learner = CustomUser.objects.create_user(
            username="learner@example.com",
            email="learner@example.com",
            password="learnerpass123",
            user_type="learner"
        )
        creator = CustomUser.objects.create_user(
            username="creator@example.com",
            email="creator@example.com",
            password="creatorpass123",
            user_type="creator"
        )
        content = Content.objects.create(
            title="Test Content",
            description="Test description",
            creator=creator,
            category="tecnologia"
        )
        quiz = Quiz.objects.create(title="Test Quiz", content=content)
        self.question = Question.objects.create(
            quiz=quiz,
            question_text="What is 2+2?"
        )
        self.option = Option.objects.create(
            question=self.question,
            text="4",
            is_correct=True
        )
        self.submission = QuizSubmission.objects.create(
            user=learner,
            quiz=quiz,
            score=1
        )
        self.answer = QuizAnswer.objects.create(
            submission=self.submission,
            question=self.question,
            selected_option=self.option
        )

    def test_answer_creation(self):
        """Testa se a resposta foi criada corretamente"""
        self.assertEqual(self.answer.submission, self.submission)
        self.assertEqual(self.answer.question, self.question)
        self.assertEqual(self.answer.selected_option, self.option)

    def test_answer_belongs_to_submission(self):
        """Testa que a resposta pertence à submissão"""
        self.assertIn(self.answer, self.submission.answers.all())


class QuizAPITest(APITestCase):
    def setUp(self):
        self.creator = CustomUser.objects.create_user(
            username="creator@example.com",
            email="creator@example.com",
            password="creatorpass123",
            user_type="creator"
        )
        self.learner = CustomUser.objects.create_user(
            username="learner@example.com",
            email="learner@example.com",
            password="learnerpass123",
            user_type="learner"
        )
        self.content = Content.objects.create(
            title="Content for Quiz",
            description="Description",
            creator=self.creator,
            category="tecnologia"
        )
        self.generate_url = reverse("quiz-generate", kwargs={"content_id": self.content.id})

    @patch("apps.quizzes.views.generate_quiz_from_opentdb")
    def test_generate_quiz_success(self, mock_generate):
        """Testa gerar quiz com sucesso (mockando serviço externo)"""
        self.client.force_authenticate(user=self.creator)
        
        # Mock return value
        mock_quiz = MagicMock()
        mock_quiz.pk = "12345678-1234-5678-1234-567812345678"
        mock_generate.return_value = mock_quiz
        
        data = {
            "difficulty": "easy",
            "number_of_questions": 5
        }
        response = self.client.post(self.generate_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("quiz_id", response.data)

    @patch("apps.quizzes.views.generate_quiz_from_opentdb")
    def test_generate_quiz_rate_limit_returns_503(self, mock_generate):
        """Testa que rate limit da OpenTDB retorna 503 com mensagem específica"""
        from apps.quizzes.services import OpenTDBRateLimitError
        mock_generate.side_effect = OpenTDBRateLimitError("rate limit")
        self.client.force_authenticate(user=self.creator)
        response = self.client.post(self.generate_url, {"difficulty": "easy"})
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("sobrecarregada", response.data["error"])

    def test_generate_quiz_as_learner(self):
        """Testa gerar quiz como aprendiz (deve falhar)"""
        self.client.force_authenticate(user=self.learner)
        data = {"difficulty": "easy", "number_of_questions": 5}
        response = self.client.post(self.generate_url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_submit_quiz(self):
        """Testa submeter respostas de um quiz"""
        # Setup quiz structure
        quiz = Quiz.objects.create(title="Quiz", content=self.content)
        question = Question.objects.create(quiz=quiz, question_text="Q1")
        option1 = Option.objects.create(question=question, text="A", is_correct=True)
        option2 = Option.objects.create(question=question, text="B", is_correct=False)
        
        submit_url = reverse("quiz-submit", kwargs={"quiz_id": quiz.id})
        self.client.force_authenticate(user=self.learner)
        
        data = {
            "answers": [
                {
                    "question_id": str(question.id),
                    "selected_option_id": str(option1.id)
                }
            ]
        }
        response = self.client.post(submit_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # score agora é XP = respostas correctas × 10
        self.assertEqual(response.data["score"], 10)
        self.assertEqual(response.data["correctAnswers"], 1)
        self.assertEqual(response.data["totalQuestions"], 1)
        self.assertEqual(response.data["xp earned"], 10)

    def test_submit_quiz_invalid_question(self):
        """Testa submeter resposta para questão que não é do quiz"""
        quiz = Quiz.objects.create(title="Quiz", content=self.content)
        # Create another content for the other quiz (content is required, NOT NULL)
        other_content = Content.objects.create(
            title="Other Content",
            description="Other description",
            creator=self.creator,
            category="design"
        )
        other_quiz = Quiz.objects.create(title="Other Quiz", content=other_content)
        
        other_question = Question.objects.create(quiz=other_quiz, question_text="Other Q")
        other_option = Option.objects.create(question=other_question, text="Opt", is_correct=True)
        
        submit_url = reverse("quiz-submit", kwargs={"quiz_id": quiz.id})
        self.client.force_authenticate(user=self.learner)
        
        data = {
            "answers": [
                {
                    "question_id": str(other_question.id),
                    "selected_option_id": str(other_option.id)
                }
            ]
        }
        response = self.client.post(submit_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
