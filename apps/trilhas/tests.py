from django.db import IntegrityError, transaction
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import CustomUser
from apps.contents.models import Content
from apps.enquetes.models import Enquete, EnqueteOpcao
from apps.quizzes.models import Option, Question, Quiz
from apps.tenancy.models import Membership, Organizacao
from apps.trilhas.models import Trilha, TrilhaItem, TrilhaProgresso
from apps.trilhas.services import stars_for


def make_user(email, user_type="learner"):
    return CustomUser.objects.create_user(
        username=email, email=email, password="pass12345", user_type=user_type
    )


def make_quiz(creator, title, organizacao, n_questions=2):
    content = Content.objects.create(
        title=f"C {title}", description="d", creator=creator,
        category="tecnologia", organizacao=organizacao,
    )
    quiz = Quiz.objects.create(title=title, content=content, organizacao=organizacao)
    for i in range(n_questions):
        q = Question.objects.create(quiz=quiz, question_text=f"q{i}")
        Option.objects.create(question=q, text="ok", is_correct=True)
        Option.objects.create(question=q, text="ko", is_correct=False)
    return quiz


class StarsTests(SimpleTestCase):
    def test_thresholds(self):
        self.assertEqual(stars_for(10, 10), 3)
        self.assertEqual(stars_for(9, 10), 3)
        self.assertEqual(stars_for(8, 10), 2)
        self.assertEqual(stars_for(5, 10), 1)
        self.assertEqual(stars_for(4, 10), 0)
        self.assertEqual(stars_for(0, 0), 0)


class TrilhaBase(APITestCase):
    def setUp(self):
        self.org = Organizacao.objects.create(name="Uni", slug="uni")
        self.other_org = Organizacao.objects.create(name="Outra", slug="outra")
        self.teacher = make_user("prof@test.com", "creator")
        self.student = make_user("aluno@test.com")
        self.student2 = make_user("aluno2@test.com")
        Membership.objects.create(user=self.teacher, organizacao=self.org, role="teacher")
        for s in (self.student, self.student2):
            Membership.objects.create(user=s, organizacao=self.org, role="student")
        self.hdr = {"HTTP_X_WORKSPACE": str(self.org.id)}

        self.read = Content.objects.create(
            title="Ler capítulo 1", description="Resumo do capítulo",
            creator=self.teacher, category="tecnologia", organizacao=self.org,
        )
        self.read2 = Content.objects.create(
            title="Ler capítulo 2", description="d",
            creator=self.teacher, category="tecnologia", organizacao=self.org,
        )
        self.quiz = make_quiz(self.teacher, "Quiz 1", self.org, 2)
        self.exam = make_quiz(self.teacher, "Exame final", self.org, 4)
        self.enquete = Enquete.objects.create(
            organizacao=self.org, creator=self.teacher, kind="binaria",
            question="Gostaste?", decision="d", trigger="fim-modulo", sample_target=50,
        )
        for i, label in enumerate(["Sim", "Não"]):
            EnqueteOpcao.objects.create(enquete=self.enquete, label=label, order=i)

        self.trilha = Trilha.objects.create(
            organizacao=self.org, creator=self.teacher, title="Redes I",
            headline="Do zero ao routing", subject="Redes", year="2º ano",
            semester="1º semestre", final_exam=self.exam, is_published=True,
        )
        self.i1 = TrilhaItem.objects.create(
            trilha=self.trilha, order=1, kind="conteudo", content=self.read, minutes=10
        )
        self.i2 = TrilhaItem.objects.create(
            trilha=self.trilha, order=2, kind="conteudo", content=self.read2, minutes=5
        )
        self.i3 = TrilhaItem.objects.create(
            trilha=self.trilha, order=3, kind="quiz", quiz=self.quiz, minutes=8
        )
        self.i4 = TrilhaItem.objects.create(
            trilha=self.trilha, order=4, kind="enquete", enquete=self.enquete
        )

    def get_trilha(self, user=None):
        self.client.force_authenticate(user or self.student)
        r = self.client.get(
            reverse("trilha-detail", args=[self.trilha.id]), **self.hdr
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        return r.data

    def statuses(self, user=None):
        return [n["status"] for n in self.get_trilha(user)["nodes"]]

    def complete(self, item, user=None):
        self.client.force_authenticate(user or self.student)
        return self.client.post(
            reverse("trilha-item-complete", args=[item.id]), **self.hdr
        )

    def submit(self, quiz, correct, user=None):
        """Responde a `correct` perguntas bem e as restantes mal."""
        self.client.force_authenticate(user or self.student)
        answers = []
        for i, q in enumerate(quiz.questions.order_by("question_text")):
            opt = q.options.get(is_correct=(i < correct))
            answers.append(
                {"question_id": str(q.id), "selected_option_id": str(opt.id)}
            )
        return self.client.post(
            reverse("quiz-submit", args=[quiz.id]),
            {"answers": answers}, format="json", **self.hdr,
        )


class TrilhaShapeTests(TrilhaBase):
    def test_matches_learning_trail_shape(self):
        data = self.get_trilha()
        for key in ("subject", "headline", "year", "semester", "nodes", "finalExam"):
            self.assertIn(key, data)
        self.assertEqual(data["subject"], "Redes")
        self.assertEqual(data["year"], "2º ano")
        node = data["nodes"][0]
        for key in ("id", "order", "title", "summary", "minutes", "xp", "status"):
            self.assertIn(key, node)
        self.assertEqual(node["title"], "Ler capítulo 1")
        self.assertEqual(node["summary"], "Resumo do capítulo")
        self.assertEqual(node["minutes"], 10)
        self.assertNotIn("href", node)  # só no frontend

    def test_no_adaptive_fields(self):
        blob = str(self.get_trilha())
        for forbidden in ("multiplier", "gaps", "strengths", "initialAccuracy",
                          "failureRate", "dataMb", "badge"):
            self.assertNotIn(forbidden, blob)

    def test_final_exam_is_separate_from_nodes(self):
        data = self.get_trilha()
        self.assertEqual(len(data["nodes"]), 4)
        self.assertEqual(data["finalExam"]["title"], "Exame final")
        self.assertEqual(data["finalExam"]["xp"], 40)
        self.assertEqual(data["finalExam"]["quizId"], str(self.exam.id))

    def test_potential_xp_per_kind(self):
        nodes = {n["order"]: n for n in self.get_trilha()["nodes"]}
        self.assertEqual(nodes[1]["xp"], 0)       # conteúdo sem quiz
        self.assertEqual(nodes[3]["xp"], 20)      # 2 perguntas x 10
        self.assertEqual(nodes[4]["xp"], 5)       # XP por voto (D13)

    def test_xp_reward_overrides_computed(self):
        self.i3.xp_reward = 99
        self.i3.save()
        nodes = {n["order"]: n for n in self.get_trilha()["nodes"]}
        self.assertEqual(nodes[3]["xp"], 99)


class TrilhaProgressTests(TrilhaBase):
    """Progresso calculado por utilizador (SLA §8.4)."""

    def test_initial_state_is_sequential_unlock(self):
        self.assertEqual(
            self.statuses(), ["ativo", "bloqueado", "bloqueado", "bloqueado"]
        )
        self.assertEqual(
            self.get_trilha()["progress"], {"completed": 0, "total": 4, "percent": 0}
        )

    def test_completing_unlocks_next(self):
        self.assertEqual(self.complete(self.i1).status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            self.statuses(), ["concluido", "ativo", "bloqueado", "bloqueado"]
        )
        self.assertEqual(self.get_trilha()["progress"]["percent"], 25.0)

    def test_cannot_complete_blocked_item(self):
        r = self.complete(self.i2)
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(TrilhaProgresso.objects.exists())

    def test_only_content_items_complete_manually(self):
        self.complete(self.i1)
        self.complete(self.i2)
        r = self.complete(self.i3)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_quiz_submission_completes_item_with_stars(self):
        self.complete(self.i1)
        self.complete(self.i2)
        r = self.submit(self.quiz, correct=2)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        nodes = self.get_trilha()["nodes"]
        self.assertEqual(nodes[2]["status"], "concluido")
        self.assertEqual(nodes[2]["stars"], 3)
        self.assertEqual(nodes[3]["status"], "ativo")

    def test_stars_follow_accuracy(self):
        self.complete(self.i1)
        self.complete(self.i2)
        self.submit(self.quiz, correct=1)  # 50% -> 1 estrela
        nodes = self.get_trilha()["nodes"]
        self.assertEqual(nodes[2]["stars"], 1)

    def test_retry_keeps_best_stars(self):
        self.complete(self.i1)
        self.complete(self.i2)
        self.submit(self.quiz, correct=2)
        self.submit(self.quiz, correct=0)  # 2.ª tentativa pior
        nodes = self.get_trilha()["nodes"]
        self.assertEqual(nodes[2]["stars"], 3)
        self.assertEqual(nodes[2]["status"], "concluido")

    def test_enquete_vote_completes_item(self):
        for item in (self.i1, self.i2):
            self.complete(item)
        self.submit(self.quiz, correct=2)
        self.client.force_authenticate(self.student)
        opt = self.enquete.options.first()
        r = self.client.post(
            reverse("enquete-vote", args=[self.enquete.id]),
            {"optionId": str(opt.id)}, format="json", **self.hdr,
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(
            self.statuses(), ["concluido", "concluido", "concluido", "concluido"]
        )
        self.assertEqual(self.get_trilha()["progress"]["percent"], 100.0)

    def test_progress_is_per_user(self):
        self.complete(self.i1)
        self.assertEqual(self.statuses(self.student)[0], "concluido")
        self.assertEqual(self.statuses(self.student2)[0], "ativo")
        self.assertEqual(TrilhaProgresso.objects.filter(user=self.student2).count(), 0)

    def test_non_sequential_trilha_has_all_active(self):
        self.trilha.is_sequential = False
        self.trilha.save()
        self.assertEqual(self.statuses(), ["ativo"] * 4)
        self.complete(self.i3.__class__.objects.get(pk=self.i2.pk))  # fora de ordem
        self.assertEqual(self.statuses(), ["ativo", "concluido", "ativo", "ativo"])

    def test_submission_in_other_context_does_not_complete_item(self):
        """Quiz do marketplace com o mesmo id não existe; o scoping manda."""
        self.client.force_authenticate(self.student)
        r = self.client.post(
            reverse("quiz-submit", args=[self.quiz.id]),
            {"answers": []}, format="json",  # marketplace: 404 antes de validar
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(TrilhaProgresso.objects.exists())


class TrilhaVisibilityTests(TrilhaBase):
    def test_unpublished_hidden_from_students_visible_to_creator(self):
        self.trilha.is_published = False
        self.trilha.save()
        self.client.force_authenticate(self.student)
        r = self.client.get(reverse("trilha-list"), **self.hdr)
        self.assertEqual(r.data["results"], [])
        r = self.client.get(reverse("trilha-detail", args=[self.trilha.id]), **self.hdr)
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        self.client.force_authenticate(self.teacher)
        r = self.client.get(reverse("trilha-list"), **self.hdr)
        self.assertEqual(len(r.data["results"]), 1)

    def test_list_is_scoped_to_workspace(self):
        self.client.force_authenticate(self.student)
        r = self.client.get(reverse("trilha-list"), **self.hdr)
        self.assertEqual(len(r.data["results"]), 1)
        # marketplace não vê a trilha da organização
        r = self.client.get(reverse("trilha-list"))
        self.assertEqual(r.data["results"], [])

    def test_other_organization_cannot_read_or_complete(self):
        outsider = make_user("fora@test.com")
        Membership.objects.create(user=outsider, organizacao=self.other_org)
        other_hdr = {"HTTP_X_WORKSPACE": str(self.other_org.id)}
        self.client.force_authenticate(outsider)
        r = self.client.get(reverse("trilha-detail", args=[self.trilha.id]), **other_hdr)
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        r = self.client.post(
            reverse("trilha-item-complete", args=[self.i1.id]), **other_hdr
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(TrilhaProgresso.objects.exists())


class TrilhaItemConstraintTests(TrilhaBase):
    def test_item_must_have_exactly_one_matching_target(self):
        bad = [
            dict(kind="conteudo", content=self.read, quiz=self.quiz),
            dict(kind="conteudo"),
            dict(kind="quiz", content=self.read),
        ]
        for i, kwargs in enumerate(bad):
            with self.assertRaises(IntegrityError), transaction.atomic():
                TrilhaItem.objects.create(trilha=self.trilha, order=100 + i, **kwargs)

    def test_order_is_unique_per_trilha(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            TrilhaItem.objects.create(
                trilha=self.trilha, order=1, kind="conteudo", content=self.read
            )
