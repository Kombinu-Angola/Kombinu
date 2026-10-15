from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from apps.accounts.models import CustomUser
from apps.contents.models import Content
from apps.quizzes.models import Quiz, QuizSubmission
from apps.rankings.services import record_xp


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
        """Como a view: submissão + linha no ledger (o ranking lê o XPEvent)."""
        submission = QuizSubmission.objects.create(
            user=user, quiz=quiz, score=score, xp_awarded=score
        )
        record_xp(
            user=user,
            amount=score,
            source_type="quiz_submission",
            source_id=submission.pk,
        )
        return submission

    def test_ranking_reads_xpevent_not_submission_score(self):
        """R4: a fonte dos pontos é o ledger, não QuizSubmission.score."""
        QuizSubmission.objects.create(user=self.user1, quiz=self.quiz1, score=50)
        self._submit(self.user2, self.quiz1, 10)

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)

        self.assertEqual([u["total_score"] for u in response.data["top_users"]], [10])
        self.assertEqual(response.data["user_position"]["total_score"], 0)

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

    def test_top_users_exposes_display_name_and_never_email(self):
        self.user1.first_name = "Ana"
        self.user1.last_name = "Silva"
        self.user1.save()
        self._submit(self.user1, self.quiz1, 10)
        self._submit(self.user2, self.quiz1, 5)

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)

        top = response.data["top_users"]
        self.assertEqual(top[0]["name"], "Ana Silva")
        # sem nome: fallback neutro, nunca o email/username
        self.assertEqual(top[1]["name"], f"Utilizador {self.user2.pk}")
        for entry in top:
            self.assertNotIn("email", entry)
        self.assertNotIn("@", str(response.data))

    def test_user_ranked_last_with_zero_score(self):
        self._submit(self.user1, self.quiz1, 0)
        self._submit(self.user2, self.quiz1, 5)
        self._submit(self.user3, self.quiz1, 10)

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)

        self.assertEqual(response.data["user_position"]["position"], 3)


class XPEventLedgerTest(APITestCase):
    def setUp(self):
        self.creator = CustomUser.objects.create_user(
            username="led-creator@test.com", email="led-creator@test.com",
            password="pass12345", user_type="creator",
        )
        self.learner = CustomUser.objects.create_user(
            username="led-learner@test.com", email="led-learner@test.com",
            password="pass12345", user_type="learner",
        )
        content = Content.objects.create(
            title="C", description="d", creator=self.creator, category="tecnologia"
        )
        self.quiz = Quiz.objects.create(title="Q", content=content)
        from apps.quizzes.models import Option, Question
        q = Question.objects.create(quiz=self.quiz, question_text="a?")
        self.ok = Option.objects.create(question=q, text="ok", is_correct=True)
        self.q = q
        self.client.force_authenticate(self.learner)
        self.url = reverse("quiz-submit", args=[self.quiz.id])

    def _submit(self):
        return self.client.post(
            self.url,
            {"answers": [{"question_id": str(self.q.id), "selected_option_id": str(self.ok.id)}]},
            format="json",
        )

    def test_first_attempt_creates_one_event(self):
        from apps.rankings.models import XPEvent
        self._submit()
        events = XPEvent.objects.filter(user=self.learner)
        self.assertEqual(events.count(), 1)
        e = events.get()
        self.assertEqual((e.amount, e.source_type), (10, "quiz_submission"))
        self.assertIsNone(e.organizacao)
        self.assertEqual(
            e.source_id, str(QuizSubmission.objects.get(user=self.learner).pk)
        )

    def test_retry_creates_no_event(self):
        from apps.rankings.models import XPEvent
        self._submit()
        self._submit()
        self.assertEqual(XPEvent.objects.filter(user=self.learner).count(), 1)
        self.assertEqual(QuizSubmission.objects.filter(user=self.learner).count(), 2)

    def test_record_xp_is_idempotent_and_skips_zero(self):
        from apps.rankings.models import XPEvent
        from apps.rankings.services import record_xp
        kw = dict(user=self.learner, source_type="enquete_voto", source_id="abc")
        self.assertIsNone(record_xp(amount=0, **kw))
        record_xp(amount=5, **kw)
        record_xp(amount=5, **kw)
        self.assertEqual(XPEvent.objects.filter(source_id="abc").count(), 1)
