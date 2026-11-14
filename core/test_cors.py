"""CORS: o preflight do frontend tem de aceitar o header `X-Workspace`."""

from django.test import TestCase, override_settings
from django.urls import reverse

ALLOWED = "https://kombinu.com"


@override_settings(CORS_ALLOW_ALL_ORIGINS=False, CORS_ALLOWED_ORIGINS=[ALLOWED])
class CorsPreflightTests(TestCase):
    def preflight(self, origin):
        return self.client.options(
            reverse("auth_login"),
            HTTP_ORIGIN=origin,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type,authorization,x-workspace",
        )

    def test_allowed_origin_accepts_x_workspace(self):
        r = self.preflight(ALLOWED)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["access-control-allow-origin"], ALLOWED)
        allowed = {
            h.strip().lower()
            for h in r.headers["access-control-allow-headers"].split(",")
        }
        self.assertIn("x-workspace", allowed)
        # Os headers por omissão continuam lá.
        self.assertTrue({"content-type", "authorization"} <= allowed)

    def test_other_origin_is_still_refused(self):
        r = self.preflight("https://atacante.example")
        self.assertNotIn("access-control-allow-origin", r.headers)
