"""K1: perfil académico e onboarding (`/api/me/`, `/api/instituicoes/`)."""

from datetime import datetime
from datetime import timezone as dt_timezone

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import CustomUser, Instituicao, PerfilEstudante
from apps.contents.models import Cadeira

CONTRACT_KEYS = {
    "id",
    "nome",
    "email",
    "intent",
    "instituicao",
    "instituicao_outra",
    "curso",
    "ano",
    "cadeira_foco",
    "minutos_por_dia",
    "provincia",
    "ano_entrada",
    "onboarding_completed_at",
    "ano_nascimento",
    "marketing_opt_in",
    "consentimento_encarregado",
}


def make_user(email, **extra):
    return CustomUser.objects.create_user(
        username=email, email=email, password="pass12345", user_type="learner", **extra
    )


class PerfilBase(APITestCase):
    def setUp(self):
        self.ana = make_user("ana@test.com", first_name="Ana", last_name="Kiame")
        self.bruno = make_user("bruno@test.com", first_name="Bruno")
        self.uan = Instituicao.objects.get(sigla="UAN")
        self.benguela = Instituicao.objects.create(
            nome="Instituto de Teste de Benguela", sigla="ITB", provincia="benguela"
        )
        self.cadeira = Cadeira.objects.create(
            nome="Direito Constitucional", curso="Direito"
        )

    def get(self, user=None):
        self.client.force_authenticate(user or self.ana)
        return self.client.get(reverse("me"))

    def patch(self, data, user=None):
        self.client.force_authenticate(user or self.ana)
        return self.client.patch(reverse("me"), data, format="json")


class ContractTests(PerfilBase):
    def test_first_get_creates_empty_profile(self):
        self.assertFalse(PerfilEstudante.objects.filter(user=self.ana).exists())
        r = self.get()
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(set(r.data), CONTRACT_KEYS)
        self.assertEqual(r.data["id"], self.ana.pk)
        self.assertEqual(r.data["nome"], "Ana Kiame")
        self.assertEqual(r.data["email"], "ana@test.com")
        for key in (
            "intent",
            "instituicao",
            "ano",
            "cadeira_foco",
            "minutos_por_dia",
            "onboarding_completed_at",
        ):
            self.assertIsNone(r.data[key], key)
        self.assertEqual(
            (r.data["instituicao_outra"], r.data["curso"], r.data["provincia"]),
            ("", "", ""),
        )
        self.assertEqual(PerfilEstudante.objects.filter(user=self.ana).count(), 1)
        self.get()
        self.assertEqual(PerfilEstudante.objects.filter(user=self.ana).count(), 1)

    def test_full_patch_and_nested_objects(self):
        r = self.patch(
            {
                "intent": "exam_prep",
                "instituicao": self.uan.pk,
                "curso": "Direito",
                "ano": 2,
                "cadeira_foco": self.cadeira.pk,
                "minutos_por_dia": 15,
            }
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(
            r.data["instituicao"],
            {
                "id": self.uan.pk,
                "nome": "Universidade Agostinho Neto",
                "sigla": "UAN",
                "provincia": "luanda",
            },
        )
        self.assertEqual(
            r.data["cadeira_foco"],
            {"id": self.cadeira.pk, "nome": "Direito Constitucional"},
        )
        self.assertEqual(r.data["intent"], "exam_prep")
        self.assertEqual(r.data["ano"], 2)
        self.assertEqual(r.data["minutos_por_dia"], 15)
        self.assertEqual(self.get().data, r.data)

    def test_ano_entrada_comes_from_date_joined(self):
        CustomUser.objects.filter(pk=self.ana.pk).update(
            date_joined=datetime(2025, 3, 1, tzinfo=dt_timezone.utc)
        )
        self.assertEqual(self.get().data["ano_entrada"], 2025)
        r = self.patch({"ano_entrada": 2020})
        self.assertEqual(r.data["ano_entrada"], 2025)

    def test_technical_email_never_leaves_the_api(self):
        tecnico = make_user("2024-001@escola-a.kombinu.invalid")
        self.assertIsNone(self.get(tecnico).data["email"])

    def test_requires_authentication(self):
        self.assertEqual(
            self.client.get(reverse("me")).status_code, status.HTTP_401_UNAUTHORIZED
        )
        self.assertEqual(
            self.client.patch(reverse("me"), {}, format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class OwnershipTests(PerfilBase):
    def test_user_never_reads_another_profile(self):
        self.patch({"curso": "Medicina"}, user=self.bruno)
        r = self.get()
        self.assertEqual(r.data["id"], self.ana.pk)
        self.assertEqual(r.data["curso"], "")

    def test_user_never_changes_another_profile(self):
        self.patch({"curso": "Medicina"}, user=self.bruno)
        # Tentar apontar para o outro utilizador no corpo não tem efeito.
        r = self.patch(
            {"id": self.bruno.pk, "user": self.bruno.pk, "curso": "Engenharia"}
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["id"], self.ana.pk)
        self.assertEqual(PerfilEstudante.objects.get(user=self.bruno).curso, "Medicina")
        self.assertEqual(PerfilEstudante.objects.get(user=self.ana).curso, "Engenharia")

    def test_read_only_fields_are_ignored(self):
        r = self.patch(
            {
                "nome": "Outro Nome",
                "email": "outro@test.com",
                "onboarding_completed_at": "2020-01-01T00:00:00Z",
            }
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.email, "ana@test.com")
        self.assertIsNone(r.data["onboarding_completed_at"])


class ProvinciaTests(PerfilBase):
    def test_province_comes_from_new_institution(self):
        r = self.patch({"instituicao": self.benguela.pk})
        self.assertEqual(r.data["provincia"], "benguela")
        r = self.patch({"instituicao": self.uan.pk})
        self.assertEqual(r.data["provincia"], "luanda")

    def test_explicit_province_wins(self):
        r = self.patch({"instituicao": self.uan.pk, "provincia": "huila"})
        self.assertEqual(r.data["provincia"], "huila")

    def test_same_institution_keeps_chosen_province(self):
        self.patch({"instituicao": self.uan.pk})
        self.patch({"provincia": "huambo"})
        r = self.patch({"instituicao": self.uan.pk, "curso": "Direito"})
        self.assertEqual(r.data["provincia"], "huambo")

    def test_clearing_institution_keeps_province(self):
        self.patch({"instituicao": self.uan.pk})
        r = self.patch({"instituicao": None, "instituicao_outra": "Outra escola"})
        self.assertIsNone(r.data["instituicao"])
        self.assertEqual(r.data["provincia"], "luanda")
        self.assertEqual(r.data["instituicao_outra"], "Outra escola")


class ConcluirTests(PerfilBase):
    def test_concluir_records_only_the_first_time(self):
        r = self.patch({"concluir": True})
        first = r.data["onboarding_completed_at"]
        self.assertIsNotNone(first)
        r = self.patch({"concluir": True, "curso": "Direito"})
        self.assertEqual(r.data["onboarding_completed_at"], first)
        self.assertEqual(r.data["curso"], "Direito")

    def test_concluir_false_does_nothing(self):
        r = self.patch({"concluir": False})
        self.assertIsNone(r.data["onboarding_completed_at"])
        self.assertNotIn("concluir", r.data)


class ValidationTests(PerfilBase):
    def assert_400(self, data, field, message):
        r = self.patch(data)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, r.data)
        self.assertEqual(str(r.data[field][0]), message)

    def test_invalid_values_have_portuguese_messages(self):
        self.assert_400(
            {"intent": "outro"},
            "intent",
            "Intenção inválida: usa exam_prep ou explore.",
        )
        self.assert_400({"ano": 7}, "ano", "O ano tem de estar entre 1 e 6.")
        self.assert_400({"ano": 0}, "ano", "O ano tem de estar entre 1 e 6.")
        self.assert_400(
            {"ano": "segundo"}, "ano", "Indica o ano como um número entre 1 e 6."
        )
        self.assert_400(
            {"minutos_por_dia": 20},
            "minutos_por_dia",
            "Escolhe 5, 15, 30 ou 60 minutos por dia.",
        )
        self.assert_400({"provincia": "lisboa"}, "provincia", "Província inválida.")
        self.assert_400(
            {"instituicao": 999999}, "instituicao", "Instituição não encontrada."
        )
        self.assert_400(
            {"cadeira_foco": 999999}, "cadeira_foco", "Cadeira não encontrada."
        )
        self.assert_400(
            {"curso": "x" * 121}, "curso", "O curso pode ter no máximo 120 caracteres."
        )

    def test_invalid_patch_changes_nothing(self):
        self.patch({"curso": "Direito"})
        self.patch({"curso": "Medicina", "ano": 9})
        self.assertEqual(PerfilEstudante.objects.get(user=self.ana).curso, "Direito")

    def test_all_21_provinces_are_accepted(self):
        provinces = [
            "bengo", "benguela", "bie", "cabinda", "cuando", "cuanza_norte",
            "cuanza_sul", "cubango", "cunene", "huambo", "huila", "icolo_e_bengo",
            "luanda", "lunda_norte", "lunda_sul", "malanje", "moxico",
            "moxico_leste", "namibe", "uige", "zaire",
        ]  # fmt: skip
        self.assertEqual(len(provinces), 21)
        for slug in provinces:
            r = self.patch({"provincia": slug})
            self.assertEqual(r.status_code, status.HTTP_200_OK, slug)


class InstituicaoListTests(PerfilBase):
    def test_seeded_catalog_without_pagination(self):
        Instituicao.objects.filter(pk=self.benguela.pk).delete()
        self.client.force_authenticate(self.ana)
        r = self.client.get(reverse("instituicao-list"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsInstance(r.data, list)
        self.assertEqual(
            {i["sigla"] for i in r.data},
            {
                "UAN",
                "UCAN",
                "ISPTEC",
                "UGS",
                "UMA",
                "UOR",
                "Lusíada",
                "Jean Piaget",
                "ISCED Luanda",
            },
        )
        self.assertTrue(all(i["provincia"] == "luanda" for i in r.data))
        self.assertEqual(set(r.data[0]), {"id", "nome", "sigla", "provincia"})

    def test_requires_authentication(self):
        r = self.client.get(reverse("instituicao-list"))
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_deleting_institution_keeps_profile(self):
        self.patch({"instituicao": self.benguela.pk})
        self.benguela.delete()
        r = self.get()
        self.assertIsNone(r.data["instituicao"])
        self.assertEqual(r.data["provincia"], "benguela")
