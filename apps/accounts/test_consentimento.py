"""K3: consentimento e idade no registo."""

from unittest import mock

from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts import consentimento
from apps.accounts.consentimento import (
    IDADE_LIMITE_CONSENTIMENTO,
    NAO_NECESSARIO,
    PENDENTE,
    TERMOS_VERSAO_ACTUAL,
    ano_actual,
    estado_consentimento,
)
from apps.accounts.models import CustomUser

PASSWORD = "Registo-Valido-2026"


class RegistoBase(APITestCase):
    def setUp(self):
        cache.clear()

    def register(self, email="nova@example.com", **overrides):
        data = {
            "email": email,
            "password": PASSWORD,
            "user_type": "learner",
            "ano_nascimento": ano_actual() - 25,
            "aceita_termos": True,
        }
        data.update(overrides)
        data = {k: v for k, v in data.items() if v is not ...}
        return self.client.post(reverse("auth_register"), data, format="json")


class RegistoObrigatorioTests(RegistoBase):
    def assert_400(self, response, field, message):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(response.data[field][0]), message)
        self.assertFalse(CustomUser.objects.exists())

    def test_without_birth_year_is_400(self):
        self.assert_400(
            self.register(ano_nascimento=...),
            "ano_nascimento",
            "Indica o ano de nascimento.",
        )

    def test_without_terms_is_400(self):
        message = "Tens de aceitar os termos de utilização para criar conta."
        self.assert_400(self.register(aceita_termos=...), "aceita_termos", message)
        self.assert_400(self.register(aceita_termos=False), "aceita_termos", message)

    def test_without_both_is_400_on_both(self):
        r = self.register(ano_nascimento=..., aceita_termos=...)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ano_nascimento", r.data)
        self.assertIn("aceita_termos", r.data)

    def test_birth_year_out_of_range_is_400(self):
        message = f"O ano de nascimento tem de estar entre 1900 e {ano_actual()}."
        self.assert_400(self.register(ano_nascimento=1899), "ano_nascimento", message)
        self.assert_400(
            self.register(ano_nascimento=ano_actual() + 1), "ano_nascimento", message
        )
        self.assert_400(
            self.register(ano_nascimento="dois mil"),
            "ano_nascimento",
            "Indica o ano de nascimento como um número (ex.: 2005).",
        )


class RegistoGravaConsentimentoTests(RegistoBase):
    def created(self, response):
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return CustomUser.objects.get(pk=response.data["user_id"])

    def test_minor_is_pending(self):
        ano = ano_actual() - (IDADE_LIMITE_CONSENTIMENTO - 1)
        user = self.created(self.register(ano_nascimento=ano))
        self.assertEqual(user.consentimento_encarregado, PENDENTE)
        self.assertEqual(user.ano_nascimento, ano)

    def test_at_the_age_limit_is_not_needed(self):
        ano = ano_actual() - IDADE_LIMITE_CONSENTIMENTO
        user = self.created(self.register(ano_nascimento=ano))
        self.assertEqual(user.consentimento_encarregado, NAO_NECESSARIO)

    def test_adult_is_not_needed(self):
        user = self.created(self.register(ano_nascimento=ano_actual() - 40))
        self.assertEqual(user.consentimento_encarregado, NAO_NECESSARIO)

    def test_records_terms_version_and_acceptance(self):
        user = self.created(self.register())
        self.assertEqual(user.termos_versao, TERMOS_VERSAO_ACTUAL)
        self.assertEqual(TERMOS_VERSAO_ACTUAL, "3.0")
        self.assertIsNotNone(user.termos_aceites_em)
        self.assertFalse(user.marketing_opt_in)

    def test_marketing_opt_in_is_optional(self):
        user = self.created(self.register(marketing_opt_in=True))
        self.assertTrue(user.marketing_opt_in)

    def test_response_contract_unchanged(self):
        r = self.register()
        self.assertEqual(set(r.data), {"message", "user_id", "email"})


class ConsentimentoRegraTests(APITestCase):
    def test_rule_uses_the_single_constant(self):
        limite = IDADE_LIMITE_CONSENTIMENTO
        self.assertEqual(estado_consentimento(2026 - (limite - 1), ano=2026), PENDENTE)
        self.assertEqual(estado_consentimento(2026 - limite, ano=2026), NAO_NECESSARIO)

    def test_changing_the_limit_is_one_line(self):
        # A regra prudente em estudo (< 19 → pendente) muda só a constante.
        with mock.patch.object(consentimento, "IDADE_LIMITE_CONSENTIMENTO", 19):
            self.assertEqual(estado_consentimento(2008, ano=2026), PENDENTE)
            self.assertEqual(estado_consentimento(2007, ano=2026), NAO_NECESSARIO)


class ContasAntigasTests(RegistoBase):
    def setUp(self):
        super().setUp()
        self.antigo = CustomUser.objects.create_user(
            username="antigo@example.com",
            email="antigo@example.com",
            password=PASSWORD,
            user_type="learner",
        )

    def test_existing_users_have_null_fields_and_still_log_in(self):
        self.assertIsNone(self.antigo.ano_nascimento)
        self.assertIsNone(self.antigo.termos_versao)
        self.assertIsNone(self.antigo.termos_aceites_em)
        self.assertIsNone(self.antigo.consentimento_encarregado)
        self.assertFalse(self.antigo.marketing_opt_in)
        r = self.client.post(
            reverse("auth_login"),
            {"email": "antigo@example.com", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertIn("access_token", r.data)

    def test_me_shows_nulls_for_existing_users(self):
        self.client.force_authenticate(self.antigo)
        data = self.client.get(reverse("me")).data
        self.assertIsNone(data["ano_nascimento"])
        self.assertIsNone(data["consentimento_encarregado"])
        self.assertFalse(data["marketing_opt_in"])


class MeConsentimentoTests(RegistoBase):
    def setUp(self):
        super().setUp()
        r = self.register(ano_nascimento=ano_actual() - 15)
        self.user = CustomUser.objects.get(pk=r.data["user_id"])
        self.client.force_authenticate(self.user)

    def test_get_me_shows_the_three_fields(self):
        data = self.client.get(reverse("me")).data
        self.assertEqual(data["ano_nascimento"], ano_actual() - 15)
        self.assertEqual(data["consentimento_encarregado"], PENDENTE)
        self.assertFalse(data["marketing_opt_in"])

    def test_patch_changes_only_marketing_opt_in(self):
        r = self.client.patch(
            reverse("me"),
            {
                "marketing_opt_in": True,
                "ano_nascimento": 1980,
                "consentimento_encarregado": "concedido",
                "termos_versao": "9.9",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertTrue(r.data["marketing_opt_in"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.marketing_opt_in)
        self.assertEqual(self.user.ano_nascimento, ano_actual() - 15)
        self.assertEqual(self.user.consentimento_encarregado, PENDENTE)
        self.assertEqual(self.user.termos_versao, TERMOS_VERSAO_ACTUAL)

    def test_marketing_opt_in_can_be_withdrawn(self):
        self.client.patch(reverse("me"), {"marketing_opt_in": True}, format="json")
        r = self.client.patch(reverse("me"), {"marketing_opt_in": False}, format="json")
        self.assertFalse(r.data["marketing_opt_in"])

    def test_invalid_marketing_value_is_400(self):
        r = self.client.patch(
            reverse("me"), {"marketing_opt_in": "talvez"}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            str(r.data["marketing_opt_in"][0]),
            "`marketing_opt_in` tem de ser true ou false.",
        )
