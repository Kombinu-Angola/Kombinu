from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from apps.accounts.models import CustomUser
from apps.contents.models import Content
from apps.quizzes.models import Quiz, QuizSubmission


class GlobalRankingViewTest(APITestCase):
    def setUp(self):
        self.url = reverse("ranking-global")

        self.creator = CustomUser.objects.create_user(
            username="creator@test.com",
            email="creator@test.com",
            password="pass123",
            user_type="creator",
        )
        self.user1 = CustomUser.objects.create_user(
            username="user1@test.com",
            email="user1@test.com",
            password="pass123",
            user_type="learner",
        )
        self.user2 = CustomUser.objects.create_user(
            username="user2@test.com",
            email="user2@test.com",
            password="pass123",
            user_type="learner",
        )
        self.user3 = CustomUser.objects.create_user(
            username="user3@test.com",
            email="user3@test.com",
            password="pass123",
            user_type="learner",
        )

        self.content1 = Content.objects.create(
            title="Conteúdo 1",
            description="Desc",
            creator=self.creator,
            category="tecnologia",
        )
        self.content2 = Content.objects.create(
            title="Conteúdo 2",
            description="Desc",
            creator=self.creator,
            category="negocios",
        )
        self.quiz1 = Quiz.objects.create(title="Quiz 1", content=self.content1)
        self.quiz2 = Quiz.objects.create(title="Quiz 2", content=self.content2)

    def _submit(self, user, quiz, score):
        return QuizSubmission.objects.create(user=user, quiz=quiz, score=score)

    def test_unauthenticated_returns_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_response_structure(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("top_users", response.data)
        self.assertIn("user_position", response.data)
        self.assertIn("position", response.data["user_position"])
        self.assertIn("total_score", response.data["user_position"])

    def test_user_with_no_submissions_returns_empty_ranking(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)

        self.assertEqual(response.data["top_users"], [])
        self.assertEqual(response.data["user_position"]["total_score"], 0)

    def test_user_with_no_submissions_position_is_after_all_others(self):
        self._submit(self.user2, self.quiz1, 10)
        self._submit(self.user3, self.quiz1, 5)

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)

        self.assertEqual(response.data["user_position"]["total_score"], 0)
        self.assertEqual(response.data["user_position"]["position"], 3)

    def test_single_user_in_ranking_is_position_one(self):
        self._submit(self.user1, self.quiz1, 8)

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)

        self.assertEqual(len(response.data["top_users"]), 1)
        self.assertEqual(response.data["top_users"][0]["total_score"], 8)
        self.assertEqual(response.data["top_users"][0]["position"], 1)
        self.assertEqual(response.data["user_position"]["position"], 1)
        self.assertEqual(response.data["user_position"]["total_score"], 8)

    def test_top_users_ordered_by_score_descending(self):
        self._submit(self.user1, self.quiz1, 5)
        self._submit(self.user2, self.quiz1, 10)
        self._submit(self.user3, self.quiz1, 3)

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)

        scores = [u["total_score"] for u in response.data["top_users"]]
        self.assertEqual(scores, [10, 5, 3])

    def test_top_users_positions_are_sequential(self):
        self._submit(self.user1, self.quiz1, 5)
        self._submit(self.user2, self.quiz1, 10)
        self._submit(self.user3, self.quiz1, 3)

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)

        positions = [u["position"] for u in response.data["top_users"]]
        self.assertEqual(positions, [1, 2, 3])

    def test_current_user_position_is_correct(self):
        self._submit(self.user1, self.quiz1, 5)
        self._submit(self.user2, self.quiz1, 10)
        self._submit(self.user3, self.quiz1, 3)

        # user1 tem 5 pontos — user2 (10) está à frente, user3 (3) atrás
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)

        self.assertEqual(response.data["user_position"]["position"], 2)
        self.assertEqual(response.data["user_position"]["total_score"], 5)

    def test_score_aggregates_multiple_quiz_submissions(self):
        self._submit(self.user1, self.quiz1, 7)
        self._submit(self.user1, self.quiz2, 3)

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)

        self.assertEqual(response.data["user_position"]["total_score"], 10)
        self.assertEqual(response.data["top_users"][0]["total_score"], 10)

    def test_top_users_contains_email_field(self):
        self._submit(self.user1, self.quiz1, 5)

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)

        self.assertIn("email", response.data["top_users"][0])
        self.assertEqual(response.data["top_users"][0]["email"], self.user1.email)

    def test_user_ranked_last_with_zero_score(self):
        self._submit(self.user1, self.quiz1, 0)
        self._submit(self.user2, self.quiz1, 5)
        self._submit(self.user3, self.quiz1, 10)

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)

        self.assertEqual(response.data["user_position"]["position"], 3)
