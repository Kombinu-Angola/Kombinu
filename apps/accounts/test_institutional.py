from datetime import timedelta

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import CustomUser
from apps.tenancy.models import Membership, Organizacao

PASSWORD = "Temporaria-123"


def make_student(org, student_code, first_name="", password=PASSWORD, **user_fields):
    email = f"{student_code.lower()}@{org.slug}.kombinu.invalid"
    user = CustomUser.objects.create_user(
        username=email,
        email=email,
        password=password,
        user_type="learner",
        first_name=first_name,
        **user_fields,
    )
    Membership.objects.create(
        user=user, organizacao=org, role="student", student_code=student_code
    )
    return user


class InstitutionalLoginTests(APITestCase):
    """D1/D10: login por código da escola + número de aluno, com isolamento."""

    def setUp(self):
        cache.clear()
        self.url = reverse("auth_institutional_login")
        self.org_a = Organizacao.objects.create(name="Escola A", slug="escola-a")
        self.org_b = Organizacao.objects.create(name="Escola B", slug="escola-b")
        # O mesmo número de aluno nas duas escolas são pessoas diferentes.
        self.ana = make_student(self.org_a, "2024-001", first_name="Ana")
        self.bruno = make_student(self.org_b, "2024-001", first_name="Bruno")

    def _login(self, school, student, password=PASSWORD):
        return self.client.post(
            self.url,
            {"school_code": school, "student_code": student, "password": password},
            format="json",
        )

    def test_login_success_returns_envelope_and_only_own_school(self):
        r = self._login(self.org_a.code, "2024-001")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", r.data)
        self.assertIn("refresh_token", r.data)
        user = r.data["user"]
        self.assertEqual(user["id"], self.ana.id)
        self.assertEqual(user["first_name"], "Ana")
        self.assertIsNone(user["email"])
        self.assertFalse(user["must_change_password"])
        self.assertEqual(
            user["memberships"],
            [
                {
                    "organizacao_id": str(self.org_a.id),
                    "name": "Escola A",
                    "code": self.org_a.code,
                    "role": "student",
                }
            ],
        )

    def test_same_student_code_resolves_by_school(self):
        r = self._login(self.org_b.code, "2024-001")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["user"]["id"], self.bruno.id)
        self.assertEqual(
            [m["organizacao_id"] for m in r.data["user"]["memberships"]],
            [str(self.org_b.id)],
        )

    def test_codes_are_normalized(self):
        r = self._login(f" {self.org_a.code.lower()} ", " 2024-001 ")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["user"]["id"], self.ana.id)

    def test_student_of_school_a_cannot_login_with_school_b_code(self):
        make_student(self.org_a, "2024-777", password="So-da-A-123")
        r = self._login(self.org_b.code, "2024-777", password="So-da-A-123")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_password_of_school_a_student_does_not_open_school_b_account(self):
        bruno = CustomUser.objects.get(pk=self.bruno.pk)
        bruno.set_password("So-do-B-123")
        bruno.save()
        r = self._login(self.org_b.code, "2024-001", password=PASSWORD)
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_all_failures_return_the_same_401(self):
        expected = {"error": "Invalid credentials."}
        cases = [
            self._login("ZZZZZZ", "2024-001"),  # escola inexistente
            self._login(self.org_a.code, "9999"),  # aluno inexistente
            self._login(self.org_a.code, "2024-001", "errada"),  # password errada
            self.client.post(self.url, {"school_code": self.org_a.code}, format="json"),
            self._login(str(self.org_a.id), "2024-001"),  # o UUID não é o código
        ]
        for r in cases:
            self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertEqual(r.data, expected)

    def test_inactive_school_cannot_login(self):
        Organizacao.objects.filter(pk=self.org_a.pk).update(is_active=False)
        self.assertEqual(
            self._login(self.org_a.code, "2024-001").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_student_who_left_keeps_account_without_school_context(self):
        # D13: a Membership inactiva não impede o login, mas sai das memberships.
        Membership.objects.filter(user=self.ana).update(is_active=False)
        r = self._login(self.org_a.code, "2024-001")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["user"]["memberships"], [])

    def test_inactive_user_cannot_login(self):
        CustomUser.objects.filter(pk=self.ana.pk).update(is_active=False)
        self.assertEqual(
            self._login(self.org_a.code, "2024-001").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_expired_temporary_password_cannot_login(self):
        CustomUser.objects.filter(pk=self.ana.pk).update(
            must_change_password=True,
            temp_password_expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertEqual(
            self._login(self.org_a.code, "2024-001").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_display_name_falls_back_to_student_code(self):
        make_student(self.org_a, "2024-050")
        r = self._login(self.org_a.code, "2024-050")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["user"]["first_name"], "2024-050")
        self.assertEqual(r.data["user"]["nome"], "2024-050")
        self.assertIsNone(r.data["user"]["email"])
        self.assertNotIn("kombinu.invalid", str(r.data))

    def test_login_ignores_stale_bearer_header(self):
        r = self.client.post(
            self.url,
            {"school_code": self.org_a.code, "student_code": "2024-001", "password": PASSWORD},
            format="json",
            HTTP_AUTHORIZATION="Bearer expirado.invalido.x",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)


class EmailLoginContractTests(APITestCase):
    """Login por email: mesmos campos novos no `user`, contrato antigo intacto."""

    def setUp(self):
        cache.clear()
        self.org = Organizacao.objects.create(name="Escola A", slug="escola-a")
        self.prof = CustomUser.objects.create_user(
            username="prof@escola.ao",
            email="prof@escola.ao",
            password=PASSWORD,
            user_type="learner",
        )
        Membership.objects.create(user=self.prof, organizacao=self.org, role="teacher")

    def test_email_login_includes_memberships_and_flag(self):
        r = self.client.post(
            reverse("auth_login"),
            {"email": "prof@escola.ao", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        user = r.data["user"]
        self.assertEqual(user["email"], "prof@escola.ao")
        self.assertEqual(user["nome"], "prof@escola.ao")
        self.assertFalse(user["must_change_password"])
        self.assertEqual(user["memberships"][0]["role"], "teacher")
        self.assertEqual(user["memberships"][0]["code"], self.org.code)

    def test_email_login_ignores_stale_bearer_header(self):
        r = self.client.post(
            reverse("auth_login"),
            {"email": "prof@escola.ao", "password": PASSWORD},
            format="json",
            HTTP_AUTHORIZATION="Bearer expirado.invalido.x",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)


class PasswordChangeGateTests(APITestCase):
    """D6: troca obrigatória com gate na API; a troca devolve tokens novos (D7)."""

    def setUp(self):
        cache.clear()
        self.org = Organizacao.objects.create(name="Escola A", slug="escola-a")
        self.user = make_student(
            self.org,
            "2024-001",
            first_name="Ana",
            must_change_password=True,
            temp_password_expires_at=timezone.now() + timedelta(days=7),
        )
        r = self.client.post(
            reverse("auth_institutional_login"),
            {"school_code": self.org.code, "student_code": "2024-001", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["user"]["must_change_password"])
        self.access = r.data["access_token"]
        self.refresh = r.data["refresh_token"]
        self.change_url = reverse("auth_password_change")

    def _auth(self, token=None):
        return {"HTTP_AUTHORIZATION": f"Bearer {token or self.access}"}

    def _change(self, current=PASSWORD, new="Nova-Password-456", token=None):
        return self.client.post(
            self.change_url,
            {"current_password": current, "new_password": new},
            format="json",
            **self._auth(token),
        )

    def test_api_is_blocked_until_password_changes(self):
        for url in (
            reverse("learner-stats"),
            reverse("content-list"),
            reverse("ranking-global"),
        ):
            r = self.client.get(url, **self._auth())
            self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN, url)
            self.assertEqual(r.data["code"], "password_change_required")
            self.assertIn("detail", r.data)

    def test_refresh_is_allowed_while_change_is_pending(self):
        r = self.client.post(reverse("token_refresh"), {"refresh": self.refresh})
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_change_clears_flag_returns_new_tokens_and_revokes_old_ones(self):
        before = timezone.now().replace(microsecond=0)
        r = self._change()
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(set(r.data), {"access_token", "refresh_token"})

        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertIsNone(self.user.temp_password_expires_at)
        self.assertGreaterEqual(self.user.password_changed_at, before)
        self.assertTrue(self.user.check_password("Nova-Password-456"))

        ok = self.client.get(reverse("learner-stats"), **self._auth(r.data["access_token"]))
        self.assertEqual(ok.status_code, status.HTTP_200_OK)

        # Os tokens anteriores ficam revogados (simula-se a troca 1 s depois
        # da emissão, porque a comparação é feita ao segundo).
        CustomUser.objects.filter(pk=self.user.pk).update(
            password_changed_at=self.user.password_changed_at + timedelta(seconds=1)
        )
        old = self.client.get(reverse("learner-stats"), **self._auth())
        self.assertEqual(old.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_wrong_current_password(self):
        r = self._change(current="errada")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("current_password", r.data)

    def test_new_password_must_differ_and_pass_validators(self):
        same = self._change(new=PASSWORD)
        self.assertEqual(same.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", same.data)

        weak = self._change(new="123")
        self.assertEqual(weak.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", weak.data)

        self.user.refresh_from_db()
        self.assertTrue(self.user.must_change_password)

    def test_change_requires_authentication(self):
        r = self.client.post(
            self.change_url,
            {"current_password": PASSWORD, "new_password": "Nova-Password-456"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)
