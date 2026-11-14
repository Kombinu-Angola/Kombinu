"""Campo `isOwner` na lista e no detalhe das Enquetes."""

from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status

from apps.enquetes.test_ciclo_de_vida import CicloBase


class IsOwnerTests(CicloBase):
    def get_list(self, user, hdr=None):
        self.client.force_authenticate(user)
        r = self.client.get(
            reverse("enquete-list"), **(self.hdr if hdr is None else hdr)
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        return {e["id"]: e for e in r.data["results"]}

    def get_detail(self, user, enquete, hdr=None):
        self.client.force_authenticate(user)
        return self.client.get(
            reverse("enquete-detail", args=[enquete["id"]]),
            **(self.hdr if hdr is None else hdr),
        )

    def test_owner_sees_is_owner_true(self):
        data = self.create_enquete()
        self.assertTrue(data["isOwner"])
        self.assertTrue(self.get_list(self.teacher)[data["id"]]["isOwner"])
        r = self.get_detail(self.teacher, data)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["isOwner"])

    def test_owner_draft_has_is_owner_true(self):
        data = self.create_enquete(publish=False)
        self.assertTrue(self.get_list(self.teacher)[data["id"]]["isOwner"])

    def test_other_members_see_is_owner_false(self):
        data = self.create_enquete()
        for user in (self.other_teacher, self.student):
            self.assertFalse(self.get_list(user)[data["id"]]["isOwner"])
            r = self.get_detail(user, data)
            self.assertEqual(r.status_code, status.HTTP_200_OK)
            self.assertFalse(r.data["isOwner"])
            self.assertNotIn("decision", r.data)

    def test_mixed_list_flags_each_row(self):
        mine = self.create_enquete()
        self.teacher, original = self.other_teacher, self.teacher
        theirs = self.create_enquete()
        self.teacher = original
        rows = self.get_list(self.teacher)
        self.assertTrue(rows[mine["id"]]["isOwner"])
        self.assertFalse(rows[theirs["id"]]["isOwner"])

    def test_other_workspace_still_404(self):
        data = self.create_enquete()
        r = self.get_detail(self.foreign_teacher, data, hdr=self.foreign_hdr)
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotIn(
            data["id"], self.get_list(self.foreign_teacher, self.foreign_hdr)
        )

    def test_is_owner_does_not_query_users(self):
        for _ in range(3):
            self.create_enquete()
        user_table = get_user_model()._meta.db_table
        self.client.force_authenticate(self.student)
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get(reverse("enquete-list"), **self.hdr)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data["results"]), 3)
        user_queries = [
            q["sql"] for q in ctx.captured_queries if user_table in q["sql"]
        ]
        self.assertEqual(user_queries, [])
