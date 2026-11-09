from datetime import timedelta

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.institutional import TEMP_PASSWORD_LENGTH
from apps.accounts.models import CustomUser
from apps.tenancy.models import AuditoriaMembro, Membership, Organizacao
from apps.tenancy.tests import make_user


def make_provisioned(org, student_code, admin, first_name=""):
    email = f"{student_code.lower()}@{org.slug}.kombinu.invalid"
    user = CustomUser.objects.create_user(
        username=email,
        email=email,
        password="Antiga-123",
        user_type="learner",
        first_name=first_name,
    )
    return Membership.objects.create(
        user=user,
        organizacao=org,
        role="student",
        student_code=student_code,
        provisioned_by=admin,
        provisioned_at=timezone.now(),
    )


class MemberManagementTests(APITestCase):
    """Etapa 6 (D9, D13): gestão de membros só pelo admin da própria organização."""

    def setUp(self):
        cache.clear()
        self.org_a = Organizacao.objects.create(name="Escola A", slug="escola-a")
        self.org_b = Organizacao.objects.create(name="Escola B", slug="escola-b")
        self.admin_a = make_user("admin-a@escola.ao")
        self.admin_b = make_user("admin-b@escola.ao")
        self.teacher_a = make_user("prof-a@escola.ao")
        self.m_admin_a = Membership.objects.create(
            user=self.admin_a, organizacao=self.org_a, role="admin"
        )
        Membership.objects.create(
            user=self.admin_b, organizacao=self.org_b, role="admin"
        )
        self.m_teacher_a = Membership.objects.create(
            user=self.teacher_a, organizacao=self.org_a, role="teacher"
        )
        self.aluno_a = make_provisioned(self.org_a, "2024-001", self.admin_a, "Ana")
        self.aluno_b = make_provisioned(self.org_b, "2024-001", self.admin_b, "Bruno")

    def _as(self, user, org):
        self.client.force_authenticate(user)
        return {"HTTP_X_WORKSPACE": str(org.id)} if org else {}

    def _action(self, user, org, membership, action):
        hdr = self._as(user, org)
        return self.client.post(
            reverse(f"tenancy-member-{action}", args=[membership.id]), **hdr
        )

    # --- listar --------------------------------------------------------------
    def test_admin_lists_only_own_school_without_technical_email(self):
        r = self.client.get(
            reverse("tenancy-members"), **self._as(self.admin_a, self.org_a)
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {m["id"] for m in r.data["results"]}
        self.assertEqual(
            ids,
            {str(self.m_admin_a.id), str(self.m_teacher_a.id), str(self.aluno_a.id)},
        )
        self.assertNotIn(str(self.aluno_b.id), ids)
        self.assertNotIn("kombinu.invalid", str(r.data))
        aluno = next(m for m in r.data["results"] if m["id"] == str(self.aluno_a.id))
        self.assertIsNone(aluno["email"])
        self.assertEqual(aluno["student_code"], "2024-001")
        self.assertEqual(aluno["first_name"], "Ana")
        admin = next(m for m in r.data["results"] if m["id"] == str(self.m_admin_a.id))
        self.assertEqual(admin["email"], "admin-a@escola.ao")

    def test_list_filters(self):
        hdr = self._as(self.admin_a, self.org_a)
        url = reverse("tenancy-members")
        r = self.client.get(url, {"role": "student"}, **hdr)
        self.assertEqual([m["id"] for m in r.data["results"]], [str(self.aluno_a.id)])
        r = self.client.get(url, {"search": "ana"}, **hdr)
        self.assertEqual([m["id"] for m in r.data["results"]], [str(self.aluno_a.id)])
        Membership.objects.filter(pk=self.aluno_a.pk).update(is_active=False)
        r = self.client.get(url, {"is_active": "false"}, **hdr)
        self.assertEqual([m["id"] for m in r.data["results"]], [str(self.aluno_a.id)])

    def test_only_workspace_admin_can_list(self):
        url = reverse("tenancy-members")
        self.assertEqual(
            self.client.get(url, **self._as(self.teacher_a, self.org_a)).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        # Admin da escola A com o workspace da B: não é membro → 403.
        self.assertEqual(
            self.client.get(url, **self._as(self.admin_a, self.org_b)).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.get(url, **self._as(self.admin_a, None)).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    # --- isolamento das acções -------------------------------------------------
    def test_admin_cannot_act_on_member_of_other_school(self):
        for action in ("deactivate", "reactivate", "reset-password"):
            # Pelo próprio workspace: a pertença da B não existe aqui → 404.
            r = self._action(self.admin_a, self.org_a, self.aluno_b, action)
            self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND, action)
            # Pelo workspace da B: não é membro → 403.
            r = self._action(self.admin_a, self.org_b, self.aluno_b, action)
            self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN, action)
        self.aluno_b.refresh_from_db()
        self.assertTrue(self.aluno_b.is_active)
        self.assertFalse(AuditoriaMembro.objects.exists())

    def test_teacher_cannot_manage_members(self):
        for action in ("deactivate", "reactivate", "reset-password"):
            r = self._action(self.teacher_a, self.org_a, self.aluno_a, action)
            self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN, action)

    # --- desactivar / reactivar ------------------------------------------------
    def test_deactivate_and_reactivate_with_audit(self):
        r = self._action(self.admin_a, self.org_a, self.aluno_a, "deactivate")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(r.data["is_active"])
        self.aluno_a.refresh_from_db()
        self.assertFalse(self.aluno_a.is_active)
        # D13: a conta mantém-se.
        self.assertTrue(CustomUser.objects.get(pk=self.aluno_a.user_id).is_active)

        r = self._action(self.admin_a, self.org_a, self.aluno_a, "reactivate")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["is_active"])

        actions = list(
            AuditoriaMembro.objects.order_by("created_at").values_list(
                "action", "actor", "organizacao", "membership"
            )
        )
        self.assertEqual(
            actions,
            [
                ("deactivate", self.admin_a.id, self.org_a.id, self.aluno_a.id),
                ("reactivate", self.admin_a.id, self.org_a.id, self.aluno_a.id),
            ],
        )

    def test_repeated_action_is_idempotent_and_not_audited_twice(self):
        self._action(self.admin_a, self.org_a, self.aluno_a, "deactivate")
        r = self._action(self.admin_a, self.org_a, self.aluno_a, "deactivate")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(AuditoriaMembro.objects.filter(action="deactivate").count(), 1)

    def test_deactivated_member_loses_workspace_access(self):
        self._action(self.admin_a, self.org_a, self.m_teacher_a, "deactivate")
        r = self.client.get(
            reverse("content-list"), **self._as(self.teacher_a, self.org_a)
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_deactivate_self(self):
        r = self._action(self.admin_a, self.org_a, self.m_admin_a, "deactivate")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.m_admin_a.refresh_from_db()
        self.assertTrue(self.m_admin_a.is_active)

    def test_organization_always_keeps_an_active_admin(self):
        second = make_user("admin2-a@escola.ao")
        m_second = Membership.objects.create(
            user=second, organizacao=self.org_a, role="admin"
        )
        # Com dois admins, um pode desactivar o outro.
        r = self._action(self.admin_a, self.org_a, m_second, "deactivate")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        # O último admin activo não pode ser desactivado (nem por outro caminho).
        Membership.objects.filter(pk=m_second.pk).update(is_active=True)
        Membership.objects.filter(pk=self.m_admin_a.pk).update(is_active=False)
        self.client.force_authenticate(second)
        r = self.client.post(
            reverse("tenancy-member-deactivate", args=[m_second.id]),
            HTTP_X_WORKSPACE=str(self.org_a.id),
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(
            Membership.objects.filter(
                organizacao=self.org_a, role="admin", is_active=True
            ).exists()
        )

    # --- reset de password -----------------------------------------------------
    def test_reset_password_issues_new_temporary_password_and_revokes_sessions(self):
        user = CustomUser.objects.get(pk=self.aluno_a.user_id)
        old_refresh = RefreshToken.for_user(user)
        old_access = str(old_refresh.access_token)
        before = timezone.now()

        r = self._action(self.admin_a, self.org_a, self.aluno_a, "reset-password")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r["Cache-Control"], "no-store")
        password = r.data["temporary_password"]
        self.assertEqual(len(password), TEMP_PASSWORD_LENGTH)
        self.assertEqual(r.data["student_code"], "2024-001")

        user.refresh_from_db()
        self.assertTrue(user.check_password(password))
        self.assertFalse(user.check_password("Antiga-123"))
        self.assertTrue(user.must_change_password)
        self.assertGreaterEqual(
            user.temp_password_expires_at, before + timedelta(days=7)
        )
        self.assertGreaterEqual(user.password_changed_at, before.replace(microsecond=0))
        self.assertEqual(AuditoriaMembro.objects.get().action, "reset_password")

        # Sessões anteriores revogadas (troca simulada 1 s depois da emissão).
        CustomUser.objects.filter(pk=user.pk).update(
            password_changed_at=user.password_changed_at + timedelta(seconds=1)
        )
        self.client.force_authenticate(None)
        old = self.client.get(
            reverse("learner-stats"), HTTP_AUTHORIZATION=f"Bearer {old_access}"
        )
        self.assertEqual(old.status_code, status.HTTP_401_UNAUTHORIZED)

        # A nova password temporária entra pelo login institucional.
        CustomUser.objects.filter(pk=user.pk).update(password_changed_at=before)
        login = self.client.post(
            reverse("auth_institutional_login"),
            {
                "school_code": self.org_a.code,
                "student_code": "2024-001",
                "password": password,
            },
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertTrue(login.data["user"]["must_change_password"])

    def test_reset_refused_for_accounts_not_managed_only_by_this_school(self):
        # Conta do marketplace (não provisionada) que entrou na escola A.
        externo = make_user("externo@gmail.com", "creator")
        m_externo = Membership.objects.create(user=externo, organizacao=self.org_a)
        r = self._action(self.admin_a, self.org_a, m_externo, "reset-password")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            CustomUser.objects.get(pk=externo.pk).check_password("pass12345")
        )

        # Conta provisionada pela A que também pertence à B.
        Membership.objects.create(user=self.aluno_a.user, organizacao=self.org_b)
        r = self._action(self.admin_a, self.org_a, self.aluno_a, "reset-password")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            CustomUser.objects.get(pk=self.aluno_a.user_id).check_password("Antiga-123")
        )
        self.assertFalse(AuditoriaMembro.objects.exists())

    def test_admin_cannot_reset_own_password_here(self):
        Membership.objects.filter(pk=self.m_admin_a.pk).update(
            provisioned_at=timezone.now()
        )
        r = self._action(self.admin_a, self.org_a, self.m_admin_a, "reset-password")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
