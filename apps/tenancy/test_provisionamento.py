import logging
from datetime import timedelta
from io import StringIO

from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.institutional import TEMP_PASSWORD_ALPHABET, TEMP_PASSWORD_LENGTH
from apps.accounts.models import CustomUser
from apps.tenancy.models import Membership, Organizacao, ProvisionamentoLote
from apps.tenancy.tests import make_user


class _CaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


class ProvisionMembersTests(APITestCase):
    """D3/D4/D5/D12: lote atómico pelo admin da organização activa."""

    def setUp(self):
        cache.clear()
        self.url = reverse("tenancy-members-bulk")
        self.org_a = Organizacao.objects.create(name="Escola A", slug="escola-a")
        self.org_b = Organizacao.objects.create(name="Escola B", slug="escola-b")
        self.admin_a = make_user("admin-a@escola.ao")
        self.admin_b = make_user("admin-b@escola.ao")
        self.teacher_a = make_user("prof-a@escola.ao", "creator")
        Membership.objects.create(user=self.admin_a, organizacao=self.org_a, role="admin")
        Membership.objects.create(user=self.admin_b, organizacao=self.org_b, role="admin")
        Membership.objects.create(user=self.teacher_a, organizacao=self.org_a, role="teacher")

    def _post(self, user, org, rows, dry_run=False):
        self.client.force_authenticate(user)
        headers = {"HTTP_X_WORKSPACE": str(org.id)} if org else {}
        return self.client.post(
            self.url, {"dry_run": dry_run, "rows": rows}, format="json", **headers
        )

    def _users_created(self):
        return CustomUser.objects.filter(memberships__provisioned_at__isnull=False)

    # --- sucesso -------------------------------------------------------------
    def test_admin_provisions_accounts_in_own_school(self):
        before = timezone.now()
        r = self._post(
            self.admin_a,
            self.org_a,
            [
                {"student_code": " 2024 - 001 ".replace(" - ", "-"), "first_name": "Ana"},
                {"student_code": "2024-002", "role": "teacher", "academic_year": "10.º"},
            ],
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r["Cache-Control"], "no-store")
        self.assertEqual(r.data["created"], 2)

        accounts = {a["student_code"]: a for a in r.data["accounts"]}
        self.assertEqual(set(accounts), {"2024-001", "2024-002"})
        for account in accounts.values():
            pw = account["temporary_password"]
            self.assertEqual(len(pw), TEMP_PASSWORD_LENGTH)
            self.assertTrue(set(pw) <= set(TEMP_PASSWORD_ALPHABET))
            self.assertIsNone(account["email"])
        # Nome de exibição: o número de aluno quando a escola não manda nome.
        self.assertEqual(accounts["2024-002"]["first_name"], "2024-002")

        m = Membership.objects.select_related("user").get(
            organizacao=self.org_a, student_code="2024-001"
        )
        user = m.user
        self.assertEqual(m.role, "student")
        self.assertEqual(m.provisioned_by, self.admin_a)
        self.assertIsNotNone(m.provisioned_at)
        self.assertEqual(user.email, "2024-001@escola-a.kombinu.invalid")
        self.assertTrue(user.must_change_password)
        self.assertIsNotNone(user.password_changed_at)
        self.assertGreaterEqual(user.temp_password_expires_at, before + timedelta(days=7))
        self.assertLessEqual(
            user.temp_password_expires_at, timezone.now() + timedelta(days=7)
        )
        self.assertTrue(user.check_password(accounts["2024-001"]["temporary_password"]))
        # Nada fica em claro na base de dados.
        self.assertNotIn(accounts["2024-001"]["temporary_password"], user.password)

        teacher = Membership.objects.get(organizacao=self.org_a, student_code="2024-002")
        self.assertEqual(teacher.role, "teacher")
        self.assertEqual(teacher.academic_year, "10.º")

        lote = ProvisionamentoLote.objects.get(id=r.data["lote_id"])
        self.assertEqual(lote.organizacao, self.org_a)
        self.assertEqual(lote.created_by, self.admin_a)
        self.assertEqual(lote.accounts_created, 2)

    def test_provisioned_student_logs_in_and_must_change_password(self):
        r = self._post(self.admin_a, self.org_a, [{"student_code": "2024-010"}])
        password = r.data["accounts"][0]["temporary_password"]
        self.client.force_authenticate(None)
        login = self.client.post(
            reverse("auth_institutional_login"),
            {"school_code": self.org_a.code, "student_code": "2024-010", "password": password},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertTrue(login.data["user"]["must_change_password"])
        self.assertEqual(login.data["user"]["first_name"], "2024-010")
        self.assertIsNone(login.data["user"]["email"])

    def test_row_with_real_email_uses_it_for_the_account(self):
        r = self._post(
            self.admin_a,
            self.org_a,
            [{"student_code": "P-01", "email": " Prof.Nova@Escola.AO ", "role": "teacher"}],
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["accounts"][0]["email"], "prof.nova@escola.ao")
        self.assertTrue(CustomUser.objects.filter(email="prof.nova@escola.ao").exists())

    def test_temporary_passwords_never_reach_the_logs(self):
        handler = _CaptureHandler()
        root = logging.getLogger()
        previous = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        try:
            r = self._post(self.admin_a, self.org_a, [{"student_code": "LOG-1"}])
        finally:
            root.removeHandler(handler)
            root.setLevel(previous)
        password = r.data["accounts"][0]["temporary_password"]
        self.assertFalse(any(password in message for message in handler.messages))

    # --- isolamento ----------------------------------------------------------
    def test_admin_of_school_a_cannot_provision_in_school_b(self):
        r = self._post(self.admin_a, self.org_b, [{"student_code": "INTRUSO-1"}])
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Membership.objects.filter(student_code="INTRUSO-1").exists())
        self.assertFalse(ProvisionamentoLote.objects.exists())

    def test_marketplace_context_cannot_provision(self):
        r = self._post(self.admin_a, None, [{"student_code": "MKT-1"}])
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Membership.objects.filter(student_code="MKT-1").exists())

    def test_teacher_and_student_cannot_provision(self):
        student = make_user("aluno-a@escola.ao")
        Membership.objects.create(user=student, organizacao=self.org_a, role="student")
        for user in (self.teacher_a, student):
            r = self._post(user, self.org_a, [{"student_code": "NAO-1"}])
            self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Membership.objects.filter(student_code="NAO-1").exists())

    def test_inactive_admin_membership_cannot_provision(self):
        Membership.objects.filter(user=self.admin_a).update(is_active=False)
        r = self._post(self.admin_a, self.org_a, [{"student_code": "X-1"}])
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_each_admin_only_creates_in_own_school(self):
        self._post(self.admin_a, self.org_a, [{"student_code": "2024-001"}])
        r = self._post(self.admin_b, self.org_b, [{"student_code": "2024-001"}])
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        orgs = set(
            Membership.objects.filter(student_code="2024-001").values_list(
                "organizacao_id", flat=True
            )
        )
        self.assertEqual(orgs, {self.org_a.id, self.org_b.id})
        self.assertEqual(
            Membership.objects.get(organizacao=self.org_b, student_code="2024-001").provisioned_by,
            self.admin_b,
        )

    # --- tudo ou nada e validação --------------------------------------------
    def test_invalid_row_rejects_the_whole_batch(self):
        Membership.objects.create(
            user=make_user("antigo@escola.ao"), organizacao=self.org_a, student_code="2024-001"
        )
        r = self._post(
            self.admin_a,
            self.org_a,
            [{"student_code": "2024-100"}, {"student_code": "2024-001"}],
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["errors"][0]["row"], 1)
        self.assertIn("student_code", r.data["errors"][0]["errors"])
        self.assertFalse(Membership.objects.filter(student_code="2024-100").exists())
        self.assertFalse(ProvisionamentoLote.objects.exists())

    def test_row_level_errors(self):
        make_user("ja.existe@escola.ao")
        rows = [
            {"student_code": "BOM-1"},
            {"student_code": "BOM-1"},  # repetido no lote
            {"student_code": "MAU@1"},  # caracteres inválidos
            {"student_code": "E-1", "email": "ja.existe@escola.ao"},  # D12
            {"student_code": "E-2", "email": "x@escola-a.kombinu.invalid"},  # domínio reservado
            {"student_code": "E-3", "email": "dup@escola.ao"},
            {"student_code": "E-4", "email": "DUP@escola.ao"},
        ]
        with override_settings(PROVISIONING_MAX_ROWS=10):
            r = self._post(self.admin_a, self.org_a, rows)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        by_row = {e["row"]: e["errors"] for e in r.data["errors"]}
        # Só as repetições são marcadas; a 1.ª ocorrência (linhas 0 e 5) é válida.
        self.assertEqual(set(by_row), {1, 2, 3, 4, 6})
        self.assertIn("student_code", by_row[1])
        self.assertIn("student_code", by_row[2])
        for row in (3, 4, 6):
            self.assertIn("email", by_row[row])
        self.assertEqual(CustomUser.objects.filter(email__endswith=".kombinu.invalid").count(), 0)

    def test_dry_run_validates_without_creating(self):
        ok = self._post(self.admin_a, self.org_a, [{"student_code": "D-1"}], dry_run=True)
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertEqual(ok.data, {"dry_run": True, "rows": 1, "errors": []})

        bad = self._post(
            self.admin_a, self.org_a, [{"student_code": "D-1"}, {"student_code": "D-1"}], dry_run=True
        )
        self.assertEqual(bad.status_code, status.HTTP_200_OK)
        self.assertEqual(bad.data["errors"][0]["row"], 1)
        self.assertFalse(Membership.objects.filter(student_code="D-1").exists())
        self.assertFalse(ProvisionamentoLote.objects.exists())

    @override_settings(PROVISIONING_MAX_ROWS=2)
    def test_batch_size_limit(self):
        rows = [{"student_code": f"L-{i}"} for i in range(3)]
        r = self._post(self.admin_a, self.org_a, rows)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("rows", r.data)
        self.assertFalse(Membership.objects.filter(student_code__startswith="L-").exists())

    def test_empty_batch_is_rejected(self):
        r = self._post(self.admin_a, self.org_a, [])
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class CriarAdminOrganizacaoCommandTests(TestCase):
    def setUp(self):
        self.org = Organizacao.objects.create(name="Escola A", slug="escola-a")

    def _run(self, *args, **kwargs):
        out = StringIO()
        call_command("criar_admin_organizacao", *args, stdout=out, **kwargs)
        return out.getvalue()

    def test_creates_admin_with_temporary_password(self):
        out = self._run(self.org.code.lower(), email=" Diretora@Escola.AO ", first_name="Rosa")
        user = CustomUser.objects.get(email="diretora@escola.ao")
        membership = Membership.objects.get(user=user)
        self.assertEqual(membership.organizacao, self.org)
        self.assertEqual(membership.role, "admin")
        self.assertTrue(user.must_change_password)
        self.assertIsNotNone(user.temp_password_expires_at)
        self.assertEqual(ProvisionamentoLote.objects.get().accounts_created, 1)
        password = out.split("Password temporária (mostrada só agora): ")[1].split()[0]
        self.assertTrue(user.check_password(password))

    def test_accepts_slug(self):
        self._run("escola-a", email="admin2@escola.ao")
        self.assertTrue(Membership.objects.filter(role="admin", organizacao=self.org).exists())

    def test_rejects_existing_email_technical_domain_and_unknown_org(self):
        make_user("existe@escola.ao")
        with self.assertRaises(CommandError):
            self._run(self.org.code, email="existe@escola.ao")
        with self.assertRaises(CommandError):
            self._run(self.org.code, email="x@escola-a.kombinu.invalid")
        with self.assertRaises(CommandError):
            self._run("NAOEXISTE", email="novo@escola.ao")
        Organizacao.objects.filter(pk=self.org.pk).update(is_active=False)
        with self.assertRaises(CommandError):
            self._run(self.org.code, email="novo@escola.ao")
        self.assertFalse(Membership.objects.filter(role="admin").exists())
