from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import CustomUser
from apps.contents.models import Content
from apps.quizzes.models import Option, Question, Quiz, QuizSubmission
from apps.rankings.models import XPEvent
from apps.rankings.services import record_xp
from apps.tenancy.models import Membership, Organizacao


def make_user(email, user_type="learner", **extra):
    return CustomUser.objects.create_user(
        username=email, email=email, password="pass12345", user_type=user_type, **extra
    )


class RankingIsolationBase(APITestCase):
    """Duas escolas fictícias + marketplace (mesmo padrão do teste de tenancy)."""

    def setUp(self):
        self.org_a = Organizacao.objects.create(name="Escola A", slug="escola-a")
        self.org_b = Organizacao.objects.create(name="Escola B", slug="escola-b")
        self.hdr_a = {"HTTP_X_WORKSPACE": str(self.org_a.id)}
        self.hdr_b = {"HTTP_X_WORKSPACE": str(self.org_b.id)}

        self.ana = make_user("ana@test.com", first_name="Ana", last_name="A")
        self.bruno = make_user("bruno@test.com", first_name="Bruno", last_name="A")
        self.carla = make_user("carla@test.com", first_name="Carla", last_name="B")
        self.diogo = make_user("diogo@test.com", first_name="Diogo", last_name="M")
        for user, org in (
            (self.ana, self.org_a), (self.bruno, self.org_a), (self.carla, self.org_b)
        ):
            Membership.objects.create(user=user, organizacao=org, role="student")
        self._n = 0

    def xp(self, user, amount, org=None, source="quiz_submission"):
        self._n += 1
        return record_xp(
            user=user, amount=amount, source_type=source,
            source_id=f"seed-{self._n}", organizacao=org,
        )

    def ranking(self, user, **kwargs):
        self.client.force_authenticate(user)
        r = self.client.get(reverse("ranking-global"), **kwargs)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        return r.data

    @staticmethod
    def scores(data):
        return [(u["name"], u["total_score"]) for u in data["top_users"]]


class RankingIsolationTests(RankingIsolationBase):
    def test_each_workspace_only_ranks_its_own_xp(self):
        self.xp(self.ana, 30, self.org_a)
        self.xp(self.bruno, 50, self.org_a)
        self.xp(self.carla, 70, self.org_b)
        self.xp(self.diogo, 90)  # marketplace

        a = self.ranking(self.ana, **self.hdr_a)
        self.assertEqual(self.scores(a), [("Bruno A", 50), ("Ana A", 30)])
        self.assertEqual(a["workspace"], str(self.org_a.id))

        b = self.ranking(self.carla, **self.hdr_b)
        self.assertEqual(self.scores(b), [("Carla B", 70)])

        m = self.ranking(self.diogo)
        self.assertEqual(self.scores(m), [("Diogo M", 90)])
        self.assertIsNone(m["workspace"])

    def test_same_user_has_separate_totals_per_workspace(self):
        """Mesmo utilizador: XP escolar e do marketplace não se somam."""
        self.xp(self.ana, 40, self.org_a)
        self.xp(self.ana, 25)  # marketplace

        self.assertEqual(self.scores(self.ranking(self.ana, **self.hdr_a)), [("Ana A", 40)])
        self.assertEqual(self.scores(self.ranking(self.ana)), [("Ana A", 25)])

    def test_user_position_is_scoped(self):
        self.xp(self.ana, 10, self.org_a)
        self.xp(self.bruno, 20, self.org_a)
        self.xp(self.diogo, 500)  # marketplace: não conta na escola A

        data = self.ranking(self.ana, **self.hdr_a)
        self.assertEqual(data["user_position"], {"position": 2, "total_score": 10})

    def test_non_member_cannot_read_other_school_ranking(self):
        self.client.force_authenticate(self.diogo)
        r = self.client.get(reverse("ranking-global"), **self.hdr_a)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_school_users_never_leak_into_response(self):
        self.xp(self.carla, 99, self.org_b)
        self.xp(self.ana, 1, self.org_a)
        data = self.ranking(self.ana, **self.hdr_a)
        blob = str(data)
        self.assertNotIn("Carla", blob)
        self.assertNotIn("99", blob)
        self.assertNotIn("@", blob)

    def test_empty_workspace(self):
        self.xp(self.diogo, 10)
        data = self.ranking(self.ana, **self.hdr_a)
        self.assertEqual(data["top_users"], [])
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["user_position"], {"position": 1, "total_score": 0})


class RankingSourceTests(RankingIsolationBase):
    """O XPEvent é a fonte; o contexto vem da acção real do utilizador."""

    def test_real_quiz_submission_feeds_only_its_workspace(self):
        teacher = make_user("prof@test.com", "creator")
        Membership.objects.create(user=teacher, organizacao=self.org_a, role="teacher")
        content = Content.objects.create(
            title="C", description="d", creator=teacher,
            category="tecnologia", organizacao=self.org_a,
        )
        quiz = Quiz.objects.create(title="Q", content=content, organizacao=self.org_a)
        q = Question.objects.create(quiz=quiz, question_text="?")
        ok = Option.objects.create(question=q, text="ok", is_correct=True)

        self.client.force_authenticate(self.ana)
        r = self.client.post(
            reverse("quiz-submit", args=[quiz.id]),
            {"answers": [{"question_id": str(q.id), "selected_option_id": str(ok.id)}]},
            format="json", **self.hdr_a,
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        self.assertEqual(self.scores(self.ranking(self.ana, **self.hdr_a)), [("Ana A", 10)])
        self.assertEqual(self.ranking(self.ana)["top_users"], [])  # marketplace vazio

    def test_enquete_xp_counts_in_ranking(self):
        self.xp(self.ana, 5, self.org_a, source="enquete_voto")
        self.assertEqual(self.scores(self.ranking(self.ana, **self.hdr_a)), [("Ana A", 5)])

    def test_submission_without_xpevent_does_not_count(self):
        quiz_owner = make_user("owner@test.com", "creator")
        content = Content.objects.create(
            title="C", description="d", creator=quiz_owner, category="design"
        )
        quiz = Quiz.objects.create(title="Q", content=content)
        QuizSubmission.objects.create(user=self.diogo, quiz=quiz, score=80)
        self.assertEqual(self.ranking(self.diogo)["top_users"], [])
        self.assertEqual(XPEvent.objects.count(), 0)


class RankingPaginationTests(RankingIsolationBase):
    def setUp(self):
        super().setUp()
        self.users = [make_user(f"p{i}@test.com", first_name=f"P{i}") for i in range(5)]
        for i, u in enumerate(self.users):
            self.xp(u, (i + 1) * 10)  # 10..50 no marketplace

    def test_pages_are_consistent_and_complete(self):
        p1 = self.ranking(self.diogo, QUERY_STRING="page=1&page_size=2")
        p2 = self.ranking(self.diogo, QUERY_STRING="page=2&page_size=2")
        p3 = self.ranking(self.diogo, QUERY_STRING="page=3&page_size=2")

        self.assertEqual((p1["count"], p1["total_pages"], p1["page_size"]), (5, 3, 2))
        self.assertEqual([u["total_score"] for u in p1["top_users"]], [50, 40])
        self.assertEqual([u["total_score"] for u in p2["top_users"]], [30, 20])
        self.assertEqual([u["total_score"] for u in p3["top_users"]], [10])
        self.assertEqual([u["position"] for u in p2["top_users"]], [3, 4])
        self.assertEqual(p2["page"], 2)

    def test_ties_share_position(self):
        self.xp(self.diogo, 50)  # empata com o 1.º
        data = self.ranking(self.diogo)
        positions = [u["position"] for u in data["top_users"]]
        self.assertEqual(positions[:2], [1, 1])
        self.assertEqual(positions[2], 3)  # RANK(): salta a posição 2
        self.assertEqual(data["user_position"]["position"], 1)

    def test_page_size_is_capped_and_invalid_values_fall_back(self):
        data = self.ranking(self.diogo, QUERY_STRING="page_size=100000")
        self.assertEqual(data["page_size"], 100)
        data = self.ranking(self.diogo, QUERY_STRING="page=abc&page_size=xyz")
        self.assertEqual((data["page"], data["page_size"]), (1, 100))

    def test_ranking_runs_a_constant_number_of_queries(self):
        for i in range(20):
            u = make_user(f"extra{i}@test.com")
            self.xp(u, i + 1)
        self.client.force_authenticate(self.diogo)
        with self.assertNumQueries(4):  # page count + page + total + ahead
            self.client.get(reverse("ranking-global"))


class DashboardIsolationTests(RankingIsolationBase):
    def setUp(self):
        super().setUp()
        self.teacher_a = make_user("prof-a@test.com", "creator")
        self.market_creator = make_user("mkt@test.com", "creator")
        Membership.objects.create(user=self.teacher_a, organizacao=self.org_a, role="teacher")

        self.content_a = Content.objects.create(
            title="Curso A", description="d", creator=self.teacher_a,
            category="tecnologia", organizacao=self.org_a,
        )
        self.content_m = Content.objects.create(
            title="Curso Mkt", description="d", creator=self.market_creator,
            category="design",
        )
        self.quiz_a = Quiz.objects.create(
            title="QA", content=self.content_a, organizacao=self.org_a
        )
        self.quiz_m = Quiz.objects.create(title="QM", content=self.content_m)

        # Ana: 60 XP na escola A e 50 XP no marketplace
        self.sub_a = QuizSubmission.objects.create(
            user=self.ana, quiz=self.quiz_a, score=60, xp_awarded=60,
            organizacao=self.org_a,
        )
        self.sub_m = QuizSubmission.objects.create(
            user=self.ana, quiz=self.quiz_m, score=50, xp_awarded=50
        )
        self.xp(self.ana, 60, self.org_a)
        self.xp(self.ana, 50)

    def get(self, name, user, **kwargs):
        self.client.force_authenticate(user)
        r = self.client.get(reverse(name), **kwargs)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        return r.data

    def test_learner_stats_are_scoped_but_level_is_global(self):
        a = self.get("learner-stats", self.ana, **self.hdr_a)
        self.assertEqual((a["totalPoints"], a["quizzesTaken"], a["coursesCompleted"]), (60, 1, 1))
        m = self.get("learner-stats", self.ana)
        self.assertEqual((m["totalPoints"], m["quizzesTaken"], m["coursesCompleted"]), (50, 1, 1))
        # carteira única: 110 XP no total -> nível 2 em qualquer contexto
        self.assertEqual(a["currentLevel"], 2)
        self.assertEqual(m["currentLevel"], 2)

    def test_learner_courses_only_active_workspace(self):
        a = self.get("learner-courses", self.ana, **self.hdr_a)
        self.assertEqual([c["title"] for c in a], ["Curso A"])
        m = self.get("learner-courses", self.ana)
        self.assertEqual([c["title"] for c in m], ["Curso Mkt"])

    def test_creator_stats_are_scoped(self):
        QuizSubmission.objects.create(
            user=self.bruno, quiz=self.quiz_a, score=10, xp_awarded=10,
            organizacao=self.org_a,
        )
        a = self.get("creator-stats", self.teacher_a, **self.hdr_a)
        self.assertEqual((a["totalCourses"], a["totalStudents"]), (1, 2))
        # fora da escola, o mesmo professor não tem conteúdo nem alunos
        m = self.get("creator-stats", self.teacher_a)
        self.assertEqual((m["totalCourses"], m["totalStudents"]), (0, 0))

    def test_profile_points_come_from_global_wallet(self):
        from apps.accounts.serializers import UserProfileSerializer

        data = UserProfileSerializer(self.ana).data
        self.assertEqual((data["pontos"], data["nivel"]), (110, 2))

    def test_dashboards_reject_foreign_workspace(self):
        self.client.force_authenticate(self.diogo)
        for name in ("learner-stats", "learner-courses", "creator-stats"):
            r = self.client.get(reverse(name), **self.hdr_a)
            self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN, name)
