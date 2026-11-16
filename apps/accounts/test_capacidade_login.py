"""K1 (Argon2id e limite de login) e K2 (mensagem de throttling em PT)."""

from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.hashers import (
    Argon2PasswordHasher,
    identify_hasher,
    make_password,
)
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.hashers import KombinuArgon2PasswordHasher
from apps.accounts.models import CustomUser
from apps.accounts.throttles import LoginRateThrottle
from core import settings as base_settings
from core.exceptions import throttled_message

PRODUCTION_HASHERS = base_settings.PASSWORD_HASHERS
KOMBINU_ARGON2_PREFIX = "argon2$argon2id$v=19$m=19456,t=2,p=1$"
PASSWORD = "Senha-Forte-2026"


class HasherConfigTests(SimpleTestCase):
    def test_argon2_is_first_and_pbkdf2_remains(self):
        self.assertEqual(
            PRODUCTION_HASHERS[0], "apps.accounts.hashers.KombinuArgon2PasswordHasher"
        )
        self.assertIn(
            "django.contrib.auth.hashers.PBKDF2PasswordHasher", PRODUCTION_HASHERS
        )

    def test_owasp_minimum_parameters(self):
        hasher = KombinuArgon2PasswordHasher()
        self.assertEqual(
            (hasher.memory_cost, hasher.time_cost, hasher.parallelism),
            (19456, 2, 1),
        )

    def test_test_settings_keep_md5(self):
        self.assertEqual(
            settings.PASSWORD_HASHERS,
            ["django.contrib.auth.hashers.MD5PasswordHasher"],
        )

    @override_settings(PASSWORD_HASHERS=PRODUCTION_HASHERS)
    def test_new_passwords_use_argon2id_with_low_memory(self):
        encoded = make_password(PASSWORD)
        self.assertTrue(encoded.startswith(KOMBINU_ARGON2_PREFIX), encoded)

    def test_login_rates(self):
        rates = base_settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        self.assertEqual(rates["login"], "120/min")
        self.assertEqual(rates["login_identifier"], "5/min")


@override_settings(PASSWORD_HASHERS=PRODUCTION_HASHERS)
class PasswordUpgradeTests(APITestCase):
    def setUp(self):
        cache.clear()

    def make_user(self, encoded):
        user = CustomUser.objects.create_user(
            username="antiga@example.com",
            email="antiga@example.com",
            password=None,
            user_type="learner",
        )
        CustomUser.objects.filter(pk=user.pk).update(password=encoded)
        user.refresh_from_db()
        return user

    def login(self):
        return self.client.post(
            reverse("auth_login"),
            {"email": "antiga@example.com", "password": PASSWORD},
            format="json",
        )

    def assert_upgraded_on_login(self, user):
        changed_at = user.password_changed_at
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        user.refresh_from_db()
        self.assertTrue(user.password.startswith(KOMBINU_ARGON2_PREFIX))
        self.assertTrue(user.check_password(PASSWORD))
        # O rehash no login não conta como troca de password: não revoga sessões.
        self.assertEqual(user.password_changed_at, changed_at)
        # E o login seguinte continua a funcionar com o hash novo.
        self.assertEqual(self.login().status_code, status.HTTP_200_OK)

    def test_pbkdf2_password_is_upgraded_on_login(self):
        user = self.make_user(make_password(PASSWORD, hasher="pbkdf2_sha256"))
        self.assertEqual(identify_hasher(user.password).algorithm, "pbkdf2_sha256")
        self.assert_upgraded_on_login(user)

    def test_argon2_with_django_defaults_is_upgraded_to_low_memory(self):
        hasher = Argon2PasswordHasher()
        user = self.make_user(hasher.encode(PASSWORD, hasher.salt()))
        self.assertIn("m=102400", user.password)
        self.assert_upgraded_on_login(user)

    def test_wrong_password_does_not_touch_hash(self):
        encoded = make_password(PASSWORD, hasher="pbkdf2_sha256")
        user = self.make_user(encoded)
        response = self.client.post(
            reverse("auth_login"),
            {"email": "antiga@example.com", "password": "errada-123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        user.refresh_from_db()
        self.assertEqual(user.password, encoded)


class ThrottleMessageTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_message_text(self):
        self.assertEqual(
            throttled_message(1),
            "Demasiadas tentativas. Tenta novamente dentro de 1 segundo.",
        )
        self.assertEqual(
            throttled_message(0.2),
            "Demasiadas tentativas. Tenta novamente dentro de 1 segundo.",
        )
        self.assertEqual(
            throttled_message(41.3),
            "Demasiadas tentativas. Tenta novamente dentro de 42 segundos.",
        )
        self.assertEqual(
            throttled_message(None),
            "Demasiadas tentativas. Tenta novamente mais tarde.",
        )

    @patch.object(LoginRateThrottle, "rate", "1/min", create=True)
    def test_login_429_uses_portuguese_message(self):
        url = reverse("auth_login")
        self.client.post(url, {})
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertRegex(
            response.data["detail"],
            r"^Demasiadas tentativas\. Tenta novamente dentro de \d+ segundos?\.$",
        )
        self.assertNotIn("diponível", str(response.data))
        self.assertIn("Retry-After", response.headers)
