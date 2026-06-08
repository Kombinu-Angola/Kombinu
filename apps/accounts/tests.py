from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from apps.accounts.models import CustomUser
from apps.contents.models import Content
from apps.quizzes.models import Quiz, QuizSubmission


class CustomUserModelTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            password="testpass123",
            user_type="learner"
        )

    def test_user_creation(self):
        """Testa se o usuário foi criado corretamente"""
        self.assertEqual(self.user.email, "test@example.com")
        self.assertEqual(self.user.user_type, "learner")
        self.assertTrue(self.user.check_password("testpass123"))

    def test_user_str_representation(self):
        """Testa a representação string do usuário"""
        self.assertEqual(str(self.user), "test@example.com")

    def test_email_is_unique(self):
        """Testa que o email deve ser único"""
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            CustomUser.objects.create_user(
                username="test2@example.com",
                email="test@example.com",  # Email duplicado
                password="testpass456",
                user_type="creator"
            )

    def test_user_type_choices(self):
        """Testa os tipos de usuário disponíveis"""
        creator = CustomUser.objects.create_user(
            username="creator@example.com",
            email="creator@example.com",
            password="creatorpass123",
            user_type="creator"
        )
        self.assertEqual(creator.user_type, "creator")
        
        learner = CustomUser.objects.create_user(
            username="learner@example.com",
            email="learner@example.com",
            password="learnerpass123",
            user_type="learner"
        )
        self.assertEqual(learner.user_type, "learner")


class AuthAPITest(APITestCase):
    def setUp(self):
        self.register_url = reverse("auth_register")
        self.login_url = reverse("auth_login")
        self.user_data = {
            "email": "newuser@example.com",
            "password": "newpassword123",
            "first_name": "New",
            "last_name": "User",
            "user_type": "learner"
        }
        self.existing_user = CustomUser.objects.create_user(
            username="existing@example.com",
            email="existing@example.com",
            password="existingpass123",
            user_type="learner"
        )

    def test_register_user_success(self):
        """Testa o registro de um novo usuário com sucesso"""
        response = self.client.post(self.register_url, self.user_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CustomUser.objects.count(), 2)
        self.assertEqual(CustomUser.objects.get(email="newuser@example.com").first_name, "New")

    def test_register_user_invalid_email(self):
        """Testa o registro com email inválido"""
        data = self.user_data.copy()
        data["email"] = "invalid-email"
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_register_user_missing_fields(self):
        """Testa o registro faltando campos obrigatórios"""
        data = {"email": "incomplete@example.com"}
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_success(self):
        """Testa o login com credenciais válidas"""
        data = {
            "email": "existing@example.com",
            "password": "existingpass123"
        }
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data)
        self.assertIn("refresh_token", response.data)

    def test_login_invalid_credentials(self):
        """Testa o login com credenciais inválidas"""
        data = {
            "email": "existing@example.com",
            "password": "wrongpassword"
        }
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_returns_first_and_last_name(self):
        """Testa que o login expõe first_name e last_name no objecto user"""
        user = CustomUser.objects.create_user(
            username="named@example.com",
            email="named@example.com",
            password="namedpass123",
            user_type="learner",
            first_name="João",
            last_name="Silva",
        )
        data = {"email": "named@example.com", "password": "namedpass123"}
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("first_name", response.data["user"])
        self.assertIn("last_name", response.data["user"])
        self.assertEqual(response.data["user"]["first_name"], "João")
        self.assertEqual(response.data["user"]["last_name"], "Silva")

    def test_token_refresh_success(self):
        """Testa renovação de access token com refresh token válido"""
        login_data = {"email": "existing@example.com", "password": "existingpass123"}
        login_response = self.client.post(self.login_url, login_data)
        refresh_token = login_response.data["refresh_token"]

        refresh_url = reverse("token_refresh")
        response = self.client.post(refresh_url, {"refresh": refresh_token})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_token_refresh_with_invalid_token_returns_401(self):
        """Testa que refresh token inválido retorna 401"""
        refresh_url = reverse("token_refresh")
        response = self.client.post(refresh_url, {"refresh": "token-invalido"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LearnerCoursesAPITest(APITestCase):
    def setUp(self):
        self.url = reverse("learner-courses")
        self.creator = CustomUser.objects.create_user(
            username="creator@test.com",
            email="creator@test.com",
            password="pass123",
            user_type="creator",
        )
        self.learner = CustomUser.objects.create_user(
            username="learner@test.com",
            email="learner@test.com",
            password="pass123",
            user_type="learner",
        )
        self.content = Content.objects.create(
            title="Curso de Python",
            description="Aprenda Python",
            creator=self.creator,
            category="tecnologia",
            thumbnail="https://example.com/thumb.jpg",
        )
        self.quiz = Quiz.objects.create(title="Quiz Python", content=self.content)

    def test_unauthenticated_returns_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_empty_when_no_submissions(self):
        self.client.force_authenticate(user=self.learner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_returns_course_after_quiz_submission(self):
        QuizSubmission.objects.create(user=self.learner, quiz=self.quiz, score=5)
        self.client.force_authenticate(user=self.learner)
        response = self.client.get(self.url)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "Curso de Python")

    def test_last_accessed_is_real_submission_date(self):
        QuizSubmission.objects.create(user=self.learner, quiz=self.quiz, score=5)
        self.client.force_authenticate(user=self.learner)
        response = self.client.get(self.url)
        last_accessed = response.data[0]["lastAccessed"]
        self.assertNotEqual(last_accessed, "2024-03-10")
        from datetime import date
        date.fromisoformat(last_accessed)

    def test_thumbnail_uses_content_thumbnail(self):
        QuizSubmission.objects.create(user=self.learner, quiz=self.quiz, score=5)
        self.client.force_authenticate(user=self.learner)
        response = self.client.get(self.url)
        self.assertEqual(response.data[0]["thumbnail"], "https://example.com/thumb.jpg")

    def test_thumbnail_falls_back_to_placeholder_when_empty(self):
        self.content.thumbnail = ""
        self.content.save()
        QuizSubmission.objects.create(user=self.learner, quiz=self.quiz, score=5)
        self.client.force_authenticate(user=self.learner)
        response = self.client.get(self.url)
        self.assertIn("placehold.co", response.data[0]["thumbnail"])

    def test_same_content_appears_only_once(self):
        content2 = Content.objects.create(
            title="Curso de Design",
            description="Aprenda Design",
            creator=self.creator,
            category="design",
        )
        quiz2 = Quiz.objects.create(title="Quiz Design", content=content2)
        QuizSubmission.objects.create(user=self.learner, quiz=self.quiz, score=8)
        QuizSubmission.objects.create(user=self.learner, quiz=quiz2, score=6)
        self.client.force_authenticate(user=self.learner)
        response = self.client.get(self.url)
        self.assertEqual(len(response.data), 2)

    def test_courses_of_other_users_not_included(self):
        other_learner = CustomUser.objects.create_user(
            username="other@test.com",
            email="other@test.com",
            password="pass123",
            user_type="learner",
        )
        QuizSubmission.objects.create(user=other_learner, quiz=self.quiz, score=5)
        self.client.force_authenticate(user=self.learner)
        response = self.client.get(self.url)
        self.assertEqual(response.data, [])
