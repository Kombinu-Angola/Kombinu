"""
K4: `GET /api/trilhas/?cadeira=<id>`, usado no ecrã final do onboarding para
abrir a primeira trilha publicada da cadeira de foco no contexto activo.
"""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import CustomUser
from apps.contents.models import Cadeira
from apps.tenancy.models import Membership, Organizacao
from apps.trilhas.models import Trilha


def make_user(email, user_type="learner"):
    return CustomUser.objects.create_user(
        username=email, email=email, password="pass12345", user_type=user_type
    )


class TrilhaPorCadeiraTests(APITestCase):
    def setUp(self):
        self.escola = Organizacao.objects.create(name="Escola A", slug="escola-a")
        self.outra = Organizacao.objects.create(name="Escola B", slug="escola-b")
        self.hdr = {"HTTP_X_WORKSPACE": str(self.escola.pk)}
        self.direito = Cadeira.objects.create(nome="Direito Constitucional")
        self.calculo = Cadeira.objects.create(nome="Cálculo I")
        self.prof = make_user("prof@test.com")
        self.aluno = make_user("aluno@test.com")
        Membership.objects.create(
            user=self.prof, organizacao=self.escola, role="teacher"
        )
        Membership.objects.create(user=self.aluno, organizacao=self.escola)
        self.now = timezone.now()

    def trilha(self, title, cadeira, organizacao=None, minutes_ago=0, **extra):
        defaults = {
            "creator": self.prof,
            "subject": cadeira.nome,
            "is_published": True,
        }
        defaults.update(extra)
        trilha = Trilha.objects.create(
            title=title, cadeira=cadeira, organizacao=organizacao, **defaults
        )
        Trilha.objects.filter(pk=trilha.pk).update(
            created_at=self.now - timedelta(minutes=minutes_ago)
        )
        return trilha

    def first_trail(self, cadeira, user=None, **extra):
        self.client.force_authenticate(user or self.aluno)
        r = self.client.get(reverse("trilha-list"), {"cadeira": cadeira.pk}, **extra)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        return r.data["results"]

    def test_returns_published_trails_of_that_subject_newest_first(self):
        self.trilha("Antiga", self.direito, self.escola, minutes_ago=30)
        self.trilha("Recente", self.direito, self.escola, minutes_ago=5)
        self.trilha("Outra cadeira", self.calculo, self.escola)
        results = self.first_trail(self.direito, **self.hdr)
        self.assertEqual([t["title"] for t in results], ["Recente", "Antiga"])

    def test_ignores_drafts_and_archived_trails(self):
        self.trilha("Rascunho", self.direito, self.escola, is_published=False)
        self.trilha("Arquivada", self.direito, self.escola, archived_at=self.now)
        self.trilha("Publicada", self.direito, self.escola, minutes_ago=60)
        results = self.first_trail(self.direito, **self.hdr)
        self.assertEqual([t["title"] for t in results], ["Publicada"])

    def test_only_the_active_context(self):
        self.trilha("Da outra escola", self.direito, self.outra)
        self.trilha("Do marketplace", self.direito, None)
        self.trilha("Da escola", self.direito, self.escola, minutes_ago=60)
        self.assertEqual(
            [t["title"] for t in self.first_trail(self.direito, **self.hdr)],
            ["Da escola"],
        )
        self.assertEqual(
            [t["title"] for t in self.first_trail(self.direito)],
            ["Do marketplace"],
        )

    def test_empty_when_the_subject_has_no_trail(self):
        self.trilha("Cálculo", self.calculo, self.escola)
        self.assertEqual(self.first_trail(self.direito, **self.hdr), [])

    def test_unknown_subject_is_400(self):
        self.client.force_authenticate(self.aluno)
        r = self.client.get(reverse("trilha-list"), {"cadeira": 999999}, **self.hdr)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
