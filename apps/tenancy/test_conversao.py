"""B4: conversão B2B -> B2C (1.ª entrada no marketplace por escola de origem)."""

from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import CustomUser
from apps.tenancy.models import ConversaoMarketplace, Membership, Organizacao


def make_user(email, user_type="learner"):
    return CustomUser.objects.create_user(
        username=email, email=email, password="pass12345", user_type=user_type
    )


class MarketplaceVisitTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("tenancy-marketplace-visit")
        self.org_a = Organizacao.objects.create(name="Escola A", slug="escola-a")
        self.org_b = Organizacao.objects.create(name="Escola B", slug="escola-b")
        self.org_off = Organizacao.objects.create(
            name="Fechada", slug="fechada", is_active=False
        )
        self.user = make_user("aluno@test.com")

    def visit(self, user=None, **hdr):
        self.client.force_authenticate(user or self.user)
        return self.client.post(self.url, **hdr)

    def pairs(self):
        return set(
            ConversaoMarketplace.objects.values_list("user_id", "organizacao_id")
        )

    def test_records_once_per_school_and_is_idempotent(self):
        Membership.objects.create(
            user=self.user, organizacao=self.org_a, role="student"
        )
        first = self.visit()
        self.assertEqual(first.status_code, status.HTTP_204_NO_CONTENT)
        visit_at = ConversaoMarketplace.objects.get().first_visit_at
        self.assertEqual(self.visit().status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.pairs(), {(self.user.pk, self.org_a.pk)})
        self.assertEqual(ConversaoMarketplace.objects.get().first_visit_at, visit_at)

    def test_one_row_per_school_of_origin(self):
        for org in (self.org_a, self.org_b):
            Membership.objects.create(user=self.user, organizacao=org, role="student")
        self.visit()
        self.assertEqual(
            self.pairs(), {(self.user.pk, self.org_a.pk), (self.user.pk, self.org_b.pk)}
        )

    def test_new_school_later_adds_only_new_row(self):
        Membership.objects.create(
            user=self.user, organizacao=self.org_a, role="student"
        )
        self.visit()
        Membership.objects.create(
            user=self.user, organizacao=self.org_b, role="teacher"
        )
        self.visit()
        self.assertEqual(ConversaoMarketplace.objects.count(), 2)

    def test_user_without_school_is_noop(self):
        r = self.visit()
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ConversaoMarketplace.objects.exists())

    def test_inactive_membership_or_organization_ignored(self):
        Membership.objects.create(
            user=self.user, organizacao=self.org_a, role="student", is_active=False
        )
        Membership.objects.create(
            user=self.user, organizacao=self.org_off, role="student"
        )
        self.visit()
        self.assertFalse(ConversaoMarketplace.objects.exists())

    def test_only_records_for_requesting_user(self):
        other = make_user("outro@test.com")
        Membership.objects.create(user=other, organizacao=self.org_a, role="student")
        Membership.objects.create(
            user=self.user, organizacao=self.org_b, role="student"
        )
        self.visit()
        self.assertEqual(self.pairs(), {(self.user.pk, self.org_b.pk)})

    def test_header_does_not_change_outcome(self):
        """O registo depende das pertenças, não do X-Workspace enviado."""
        Membership.objects.create(
            user=self.user, organizacao=self.org_a, role="student"
        )
        r = self.visit(HTTP_X_WORKSPACE=str(self.org_b.pk))
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.pairs(), {(self.user.pk, self.org_a.pk)})

    def test_requires_authentication(self):
        r = self.client.post(self.url)
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_only_post_allowed(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(
            self.client.get(self.url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )

    @patch(
        "apps.tenancy.views.MarketplaceVisitRateThrottle.rate", "2/hour", create=True
    )
    def test_is_throttled(self):
        for _ in range(2):
            self.assertEqual(self.visit().status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.visit().status_code, status.HTTP_429_TOO_MANY_REQUESTS)
