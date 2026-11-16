"""K4: `GET /api/rankings/me/` (XP total e do workspace, nível e ofensiva)."""

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest import mock
from zoneinfo import ZoneInfo

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import CustomUser
from apps.rankings.models import XPEvent
from apps.rankings.selectors import streaks
from apps.tenancy.models import Membership, Organizacao

LUANDA = ZoneInfo("Africa/Luanda")
# "Agora" fixo: 16 Nov 2026, 10:00 em Luanda.
NOW = datetime(2026, 11, 16, 10, 0, tzinfo=LUANDA)
TODAY = NOW.date()
CONTRACT_KEYS = {
    "xp_total",
    "xp_workspace",
    "level",
    "streak",
    "best_streak",
    "last_activity_date",
}


def make_user(email):
    return CustomUser.objects.create_user(
        username=email, email=email, password="pass12345", user_type="learner"
    )


class GamificationMeBase(APITestCase):
    def setUp(self):
        self.user = make_user("ana@test.com")
        self.org_a = Organizacao.objects.create(name="Escola A", slug="escola-a")
        self.org_b = Organizacao.objects.create(name="Escola B", slug="escola-b")
        Membership.objects.create(user=self.user, organizacao=self.org_a)
        self.n = 0
        patcher = mock.patch("django.utils.timezone.now", return_value=NOW)
        patcher.start()
        self.addCleanup(patcher.stop)

    def xp(self, when, amount=10, organizacao=None, user=None):
        """Evento de XP com `created_at` controlado (o campo é auto_now_add)."""
        self.n += 1
        event = XPEvent.objects.create(
            user=user or self.user,
            organizacao=organizacao,
            source_type="quiz_submission",
            source_id=f"teste-{self.n}",
            amount=amount,
        )
        XPEvent.objects.filter(pk=event.pk).update(created_at=when)
        return event

    def on_day(self, days_ago, hour=12, **kwargs):
        when = datetime.combine(
            TODAY - timedelta(days=days_ago), datetime.min.time(), tzinfo=LUANDA
        ).replace(hour=hour)
        return self.xp(when, **kwargs)

    def get(self, **extra):
        self.client.force_authenticate(self.user)
        return self.client.get(reverse("ranking-me"), **extra)

    def me(self, **extra):
        r = self.get(**extra)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        return r.data


class ContractTests(GamificationMeBase):
    def test_without_activity(self):
        data = self.me()
        self.assertEqual(set(data), CONTRACT_KEYS)
        self.assertEqual(
            data,
            {
                "xp_total": 0,
                "xp_workspace": 0,
                "level": 1,
                "streak": 0,
                "best_streak": 0,
                "last_activity_date": None,
            },
        )

    def test_no_gems(self):
        self.on_day(0)
        data = self.me()
        self.assertEqual(set(data), CONTRACT_KEYS)
        self.assertNotIn("gems", data)

    def test_requires_authentication(self):
        r = self.client.get(reverse("ranking-me"))
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_last_activity_date_format(self):
        self.on_day(1)
        self.assertEqual(self.me()["last_activity_date"], "2026-11-15")


class StreakTests(GamificationMeBase):
    def test_consecutive_days_ending_today(self):
        for days_ago in (0, 1, 2):
            self.on_day(days_ago)
        data = self.me()
        self.assertEqual((data["streak"], data["best_streak"]), (3, 3))

    def test_several_events_on_the_same_day_count_once(self):
        self.on_day(0, hour=9)
        self.on_day(0, hour=10)
        self.on_day(1, hour=20)
        self.assertEqual(self.me()["streak"], 2)

    def test_activity_only_until_yesterday_still_counts(self):
        self.on_day(1)
        self.on_day(2)
        data = self.me()
        self.assertEqual(data["streak"], 2)
        self.assertEqual(data["last_activity_date"], "2026-11-15")

    def test_last_activity_before_yesterday_is_zero(self):
        self.on_day(2)
        self.on_day(3)
        data = self.me()
        self.assertEqual(data["streak"], 0)
        self.assertEqual(data["best_streak"], 2)

    def test_two_day_gap_breaks_the_streak(self):
        # Hoje e há 3 dias: há um buraco de 2 dias (ontem e anteontem).
        self.on_day(0)
        self.on_day(3)
        self.on_day(4)
        data = self.me()
        self.assertEqual(data["streak"], 1)
        self.assertEqual(data["best_streak"], 2)

    def test_best_streak_is_the_longest_ever(self):
        for days_ago in (20, 19, 18, 17, 16):
            self.on_day(days_ago)
        for days_ago in (1, 0):
            self.on_day(days_ago)
        data = self.me()
        self.assertEqual((data["streak"], data["best_streak"]), (2, 5))

    def test_streak_uses_the_global_wallet(self):
        # XP de contextos diferentes conta para a mesma ofensiva.
        self.on_day(0, organizacao=self.org_a)
        self.on_day(1)
        self.on_day(2, organizacao=self.org_a)
        self.assertEqual(self.me(HTTP_X_WORKSPACE=str(self.org_a.pk))["streak"], 3)
        self.assertEqual(self.me()["streak"], 3)

    def test_day_boundary_is_luanda_not_utc(self):
        # 15 Nov às 23:30 UTC já é 16 Nov às 00:30 em Luanda (UTC+1).
        self.xp(datetime(2026, 11, 15, 23, 30, tzinfo=dt_timezone.utc))
        self.xp(datetime(2026, 11, 15, 12, 0, tzinfo=dt_timezone.utc))
        data = self.me()
        self.assertEqual(data["last_activity_date"], "2026-11-16")
        # Em UTC seriam ambos 15 Nov (ofensiva 1); em Luanda são 2 dias.
        self.assertEqual(data["streak"], 2)

    def test_today_follows_luanda_time(self):
        # Às 23:30 UTC de 15 Nov, em Luanda já é dia 16: XP de dia 14 já não conta.
        late = datetime(2026, 11, 15, 23, 30, tzinfo=dt_timezone.utc)
        self.on_day(2)  # 14 Nov
        with mock.patch("django.utils.timezone.now", return_value=late):
            self.assertEqual(self.me()["streak"], 0)

    def test_streaks_function(self):
        d = TODAY
        day = timedelta(days=1)
        self.assertEqual(streaks([], d), (0, 0))
        self.assertEqual(streaks([d], d), (1, 1))
        self.assertEqual(streaks([d - day], d), (1, 1))
        self.assertEqual(streaks([d - 2 * day], d), (0, 1))
        self.assertEqual(streaks([d - 3 * day, d - 2 * day, d], d), (1, 2))


class XpAndIsolationTests(GamificationMeBase):
    def setUp(self):
        super().setUp()
        Membership.objects.create(user=self.user, organizacao=self.org_b)
        self.on_day(0, amount=30)  # marketplace
        self.on_day(1, amount=50, organizacao=self.org_a)
        self.on_day(2, amount=70, organizacao=self.org_b)
        # XP de outra pessoa na mesma escola não entra.
        self.on_day(0, amount=500, organizacao=self.org_a, user=make_user("b@t.com"))

    def test_totals_and_level(self):
        data = self.me(HTTP_X_WORKSPACE=str(self.org_a.pk))
        self.assertEqual(data["xp_total"], 150)
        self.assertEqual(data["xp_workspace"], 50)
        self.assertEqual(data["level"], 2)

    def test_marketplace_workspace_is_xp_without_organization(self):
        self.assertEqual(self.me()["xp_workspace"], 30)
        self.assertEqual(self.me(HTTP_X_WORKSPACE="marketplace")["xp_workspace"], 30)

    def test_other_school_xp_does_not_leak(self):
        data = self.me(HTTP_X_WORKSPACE=str(self.org_b.pk))
        self.assertEqual(data["xp_workspace"], 70)
        self.assertNotEqual(data["xp_workspace"], 120)

    def test_workspace_without_membership_is_denied(self):
        org_c = Organizacao.objects.create(name="Escola C", slug="escola-c")
        r = self.get(HTTP_X_WORKSPACE=str(org_c.pk))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("xp_total", r.data)

    def test_inactive_membership_is_denied(self):
        Membership.objects.filter(user=self.user, organizacao=self.org_b).update(
            is_active=False
        )
        r = self.get(HTTP_X_WORKSPACE=str(self.org_b.pk))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_workspace_is_400(self):
        r = self.get(HTTP_X_WORKSPACE="nao-e-uuid")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
