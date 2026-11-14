from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from apps.accounts.models import CustomUser
from apps.contents.models import Content


class ContentModelTest(TestCase):
    def setUp(self):
        self.creator = CustomUser.objects.create_user(
            username="creator@example.com",
            email="creator@example.com",
            password="creatorpass123",
            user_type="creator",
        )
        self.content = Content.objects.create(
            title="Test Content",
            description="Test description",
            creator=self.creator,
            category="tecnologia",
        )

    def test_content_creation(self):
        """Testa se o conteúdo foi criado corretamente"""
        self.assertEqual(self.content.title, "Test Content")
        self.assertEqual(self.content.category, "tecnologia")
        self.assertEqual(self.content.creator, self.creator)

    def test_has_quiz_property(self):
        """Testa a propriedade has_quiz quando não há quiz"""
        self.assertFalse(self.content.has_quiz)

    def test_quiz_id_property_without_quiz(self):
        """Testa a propriedade quiz_id quando não há quiz"""
        self.assertIsNone(self.content.quiz_id)

    def test_content_str_representation(self):
        """Testa a representação string do conteúdo"""
        self.assertEqual(str(self.content), "Test Content")

    def test_content_categories(self):
        """Testa as categorias disponíveis"""
        categories = ["tecnologia", "negocios", "design"]
        for category in categories:
            content = Content.objects.create(
                title=f"Content {category}",
                description="Test description",
                creator=self.creator,
                category=category,
            )
            self.assertEqual(content.category, category)

    def test_content_belongs_to_creator(self):
        """Testa que o conteúdo pertence ao criador"""
        self.assertIn(self.content, self.creator.created_contents.all())


class ContentAPITest(APITestCase):
    def setUp(self):
        self.list_url = reverse("content-list")
        self.creator = CustomUser.objects.create_user(
            username="creator@example.com",
            email="creator@example.com",
            password="creatorpass123",
            user_type="creator",
        )
        self.learner = CustomUser.objects.create_user(
            username="learner@example.com",
            email="learner@example.com",
            password="learnerpass123",
            user_type="learner",
        )
        self.content = Content.objects.create(
            title="Existing Content",
            description="Description",
            creator=self.creator,
            category="tecnologia",
        )

    def test_list_contents_authenticated(self):
        """Testa listar conteúdos autenticado"""
        self.client.force_authenticate(user=self.learner)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_list_contents_unauthenticated(self):
        """Testa listar conteúdos sem autenticação"""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_content_as_creator(self):
        """Testa criar conteúdo como criador"""
        self.client.force_authenticate(user=self.creator)
        data = {
            "title": "New Content",
            "description": "New Description",
            "category": "negocios",
        }
        response = self.client.post(self.list_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Content.objects.count(), 2)
        self.assertEqual(Content.objects.last().creator, self.creator)

    def test_create_content_as_learner(self):
        """Testa criar conteúdo como aprendiz (deve falhar)"""
        self.client.force_authenticate(user=self.learner)
        data = {
            "title": "Learner Content",
            "description": "Should fail",
            "category": "design",
        }
        response = self.client.post(self.list_url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_filter_by_has_quiz(self):
        """Testa filtrar conteúdos por has_quiz"""
        from apps.quizzes.models import Quiz

        Quiz.objects.create(title="Quiz", content=self.content)

        self.client.force_authenticate(user=self.learner)

        # Filter has_quiz=true
        response = self.client.get(self.list_url, {"has_quiz": "true"})
        self.assertEqual(len(response.data["results"]), 1)

        # Filter has_quiz=false
        response = self.client.get(self.list_url, {"has_quiz": "false"})
        self.assertEqual(len(response.data["results"]), 0)
