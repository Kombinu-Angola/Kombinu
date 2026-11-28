"""C-K5: o registo público cria sempre `learner`; criadores só pelo admin."""

from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.consentimento import ano_actual
from apps.accounts.models import CustomUser

PASSWORD = "Registo-Valido-2026"


class RegistoSemCriadorTests(APITestCase):
    def setUp(self):
        cache.clear()

    def register(self, email, **extra):
        data = {
            "email": email,
            "password": PASSWORD,
            "ano_nascimento": ano_actual() - 25,
            "aceita_termos": True,
        }
        data.update(extra)
        return self.client.post(reverse("auth_register"), data, format="json")

    def test_creator_request_creates_a_learner(self):
        r = self.register("quer-ser-criador@example.com", user_type="creator")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["user_type"], "learner")
        user = CustomUser.objects.get(pk=r.data["user_id"])
        self.assertEqual(user.user_type, "learner")

    def test_account_registered_as_creator_has_no_creator_access(self):
        r = self.register("quer-ser-criador@example.com", user_type="creator")
        user = CustomUser.objects.get(pk=r.data["user_id"])
        self.client.force_authenticate(user)
        stats = self.client.get(reverse("creator-stats"))
        self.assertEqual(stats.status_code, status.HTTP_403_FORBIDDEN)
        content = self.client.post(
            reverse("content-list"),
            {"title": "Tentativa", "description": "d", "category": "tecnologia"},
            format="json",
        )
        self.assertEqual(content.status_code, status.HTTP_403_FORBIDDEN)

    def test_learner_registration_is_unchanged(self):
        r = self.register("aluno@example.com", user_type="learner")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["user_type"], "learner")
        self.assertEqual(
            CustomUser.objects.get(pk=r.data["user_id"]).user_type, "learner"
        )

    def test_user_type_can_be_omitted(self):
        r = self.register("sem-tipo@example.com")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["user_type"], "learner")

    def test_unknown_user_type_is_still_rejected(self):
        r = self.register("admin@example.com", user_type="admin")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("user_type", r.data)
        self.assertFalse(CustomUser.objects.filter(email="admin@example.com").exists())

    def test_existing_creators_keep_their_access(self):
        creator = CustomUser.objects.create_user(
            username="criador@example.com",
            email="criador@example.com",
            password=PASSWORD,
            user_type="creator",
        )
        self.client.force_authenticate(creator)
        self.assertEqual(
            self.client.get(reverse("creator-stats")).status_code, status.HTTP_200_OK
        )
        creator.refresh_from_db()
        self.assertEqual(creator.user_type, "creator")
