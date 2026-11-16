"""K3: `/api/dashboard/creator/stats/` só para criadores, professores e admins."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import CustomUser
from apps.contents.models import Content
from apps.tenancy.models import Membership, Organizacao


def make_user(email, user_type="learner"):
    return CustomUser.objects.create_user(
        username=email, email=email, password="pass12345", user_type=user_type
    )


class CreatorStatsPermissionTests(APITestCase):
    def setUp(self):
        self.org_a = Organizacao.objects.create(name="Escola A", slug="escola-a")
        self.org_b = Organizacao.objects.create(name="Escola B", slug="escola-b")
        self.hdr_a = {"HTTP_X_WORKSPACE": str(self.org_a.pk)}
        self.hdr_b = {"HTTP_X_WORKSPACE": str(self.org_b.pk)}

        self.learner = make_user("learner@test.com")
        self.creator = make_user("creator@test.com", "creator")
        self.teacher = make_user("prof@test.com")
        self.admin = make_user("admin@test.com")
        self.student = make_user("aluno@test.com")
        Membership.objects.create(
            user=self.teacher, organizacao=self.org_a, role="teacher"
        )
        Membership.objects.create(user=self.admin, organizacao=self.org_a, role="admin")
        Membership.objects.create(
            user=self.student, organizacao=self.org_a, role="student"
        )
        Content.objects.create(
            title="Aula da escola",
            description="d",
            creator=self.teacher,
            category="tecnologia",
            organizacao=self.org_a,
        )

    def get(self, user, **extra):
        self.client.force_authenticate(user)
        return self.client.get(reverse("creator-stats"), **extra)

    def assert_denied(self, response):
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("totalCourses", response.data)

    def test_learner_without_role_is_denied(self):
        self.assert_denied(self.get(self.learner))
        self.assert_denied(self.get(self.learner, HTTP_X_WORKSPACE="marketplace"))

    def test_creator_is_allowed(self):
        r = self.get(self.creator)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["totalCourses"], 0)

    def test_teacher_in_school_is_allowed(self):
        r = self.get(self.teacher, **self.hdr_a)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["totalCourses"], 1)

    def test_admin_in_school_is_allowed(self):
        r = self.get(self.admin, **self.hdr_a)
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_student_of_school_is_denied(self):
        self.assert_denied(self.get(self.student, **self.hdr_a))
        self.assert_denied(self.get(self.student))

    def test_teacher_outside_school_is_denied(self):
        # Professor (learner) no marketplace: lá não tem papel de criador.
        self.assert_denied(self.get(self.teacher))

    def test_teacher_with_other_school_header_is_denied(self):
        self.assert_denied(self.get(self.teacher, **self.hdr_b))

    def test_inactive_teacher_is_denied(self):
        Membership.objects.filter(user=self.teacher).update(is_active=False)
        self.assert_denied(self.get(self.teacher, **self.hdr_a))

    def test_creator_still_needs_membership_for_a_school_header(self):
        # O papel de criador não abre uma escola a que não pertence.
        self.assert_denied(self.get(self.creator, **self.hdr_a))

    def test_requires_authentication(self):
        r = self.client.get(reverse("creator-stats"))
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)
