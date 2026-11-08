from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.contents.models import Content
from apps.quizzes.models import Quiz, QuizSubmission
from apps.rankings.models import XPEvent
from apps.tenancy.models import Membership, Organizacao
from apps.tenancy.tests import make_content, make_quiz, make_user


class TenantIsolationTests(APITestCase):
    """
    SLA §8.3: dados de uma organização não vazam para outra nem para o
    marketplace. Duas organizações fictícias + marketplace.
    """

    def setUp(self):
        self.org_a = Organizacao.objects.create(name="Escola A", slug="escola-a")
        self.org_b = Organizacao.objects.create(name="Escola B", slug="escola-b")

        self.teacher_a = make_user("prof-a@test.com", "creator")
        self.student_a = make_user("aluno-a@test.com")
        self.teacher_b = make_user("prof-b@test.com", "creator")
        self.student_b = make_user("aluno-b@test.com")
        self.market_creator = make_user("mkt-creator@test.com", "creator")
        self.market_learner = make_user("mkt-learner@test.com")

        Membership.objects.create(user=self.teacher_a, organizacao=self.org_a, role="teacher")
        Membership.objects.create(user=self.student_a, organizacao=self.org_a, role="student")
        Membership.objects.create(user=self.teacher_b, organizacao=self.org_b, role="teacher")
        Membership.objects.create(user=self.student_b, organizacao=self.org_b, role="student")

        self.content_a = make_content(self.teacher_a, "Conteúdo A", self.org_a)
        self.content_b = make_content(self.teacher_b, "Conteúdo B", self.org_b)
        self.content_m = make_content(self.market_creator, "Conteúdo Mkt")
        self.quiz_a = make_quiz(self.content_a, self.org_a)
        self.quiz_b = make_quiz(self.content_b, self.org_b)
        self.quiz_m = make_quiz(self.content_m)

    def _hdr(self, org):
        return {"HTTP_X_WORKSPACE": str(org.id)} if org else {}

    def _titles(self, user, org=None):
        self.client.force_authenticate(user)
        r = self.client.get(reverse("content-list"), **self._hdr(org))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        return {c["title"] for c in r.data["results"]}

    def _submit_payload(self, quiz):
        question = quiz.questions.get()
        option = question.options.get(is_correct=True)
        return {
            "answers": [
                {"question_id": str(question.id), "selected_option_id": str(option.id)}
            ]
        }

    # --- listagens -----------------------------------------------------
    def test_list_shows_only_own_organization(self):
        self.assertEqual(self._titles(self.student_a, self.org_a), {"Conteúdo A"})
        self.assertEqual(self._titles(self.student_b, self.org_b), {"Conteúdo B"})

    def test_marketplace_excludes_organization_content(self):
        self.assertEqual(self._titles(self.market_learner), {"Conteúdo Mkt"})
        # membro de A, sem header, está no marketplace: não vê o conteúdo de A
        self.assertEqual(self._titles(self.student_a), {"Conteúdo Mkt"})

    def test_workspace_switch_without_new_login(self):
        """Mesmo utilizador, contextos disjuntos (SLA §1, alternância)."""
        both = make_user("both@test.com")
        Membership.objects.create(user=both, organizacao=self.org_a)
        Membership.objects.create(user=both, organizacao=self.org_b)
        self.assertEqual(self._titles(both, self.org_a), {"Conteúdo A"})
        self.assertEqual(self._titles(both, self.org_b), {"Conteúdo B"})
        self.assertEqual(self._titles(both), {"Conteúdo Mkt"})

    def test_filters_cannot_cross_context(self):
        self.client.force_authenticate(self.student_a)
        r = self.client.get(
            reverse("content-list"),
            {"creator": self.teacher_b.pk},
            **self._hdr(self.org_a),
        )
        self.assertEqual(r.data["results"], [])

    # --- acesso por id -------------------------------------------------
    def test_cross_organization_detail_is_404(self):
        self.client.force_authenticate(self.student_a)
        url_b = reverse("content-detail", args=[self.content_b.id])
        self.assertEqual(
            self.client.get(url_b, **self._hdr(self.org_a)).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        # e a partir do marketplace
        self.assertEqual(self.client.get(url_b).status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_organization_write_is_404_and_untouched(self):
        self.client.force_authenticate(self.teacher_a)
        url_b = reverse("content-detail", args=[self.content_b.id])
        hdr = self._hdr(self.org_a)
        self.assertEqual(
            self.client.patch(url_b, {"title": "hack"}, format="json", **hdr).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.delete(url_b, **hdr).status_code, status.HTTP_404_NOT_FOUND
        )
        self.content_b.refresh_from_db()
        self.assertEqual(self.content_b.title, "Conteúdo B")

    def test_marketplace_content_not_visible_inside_organization(self):
        self.client.force_authenticate(self.student_a)
        url_m = reverse("content-detail", args=[self.content_m.id])
        self.assertEqual(
            self.client.get(url_m, **self._hdr(self.org_a)).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    # --- acesso ao workspace ------------------------------------------
    def test_non_member_cannot_enter_workspace(self):
        self.client.force_authenticate(self.student_a)
        r = self.client.get(reverse("content-list"), **self._hdr(self.org_b))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_or_malformed_workspace(self):
        self.client.force_authenticate(self.student_a)
        r = self.client.get(reverse("content-list"), HTTP_X_WORKSPACE="nao-e-uuid")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        r = self.client.get(
            reverse("content-list"),
            HTTP_X_WORKSPACE="00000000-0000-0000-0000-000000000000",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_inactive_membership_or_organization_is_denied(self):
        Membership.objects.filter(user=self.student_a).update(is_active=False)
        self.client.force_authenticate(self.student_a)
        r = self.client.get(reverse("content-list"), **self._hdr(self.org_a))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        Membership.objects.filter(user=self.student_a).update(is_active=True)
        Organizacao.objects.filter(pk=self.org_a.pk).update(is_active=False)
        r = self.client.get(reverse("content-list"), **self._hdr(self.org_a))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    # --- criação -------------------------------------------------------
    def test_create_content_is_stamped_with_active_workspace(self):
        self.client.force_authenticate(self.teacher_a)
        payload = {"title": "Novo", "description": "d", "category": "design"}
        r = self.client.post(
            reverse("content-list"), payload, format="json", **self._hdr(self.org_a)
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Content.objects.get(title="Novo").organizacao_id, self.org_a.id)

    def test_student_role_cannot_create_inside_organization(self):
        student_creator = make_user("student-creator@test.com", "creator")
        Membership.objects.create(
            user=student_creator, organizacao=self.org_a, role="student"
        )
        self.client.force_authenticate(student_creator)
        payload = {"title": "Nope", "description": "d", "category": "design"}
        r = self.client.post(
            reverse("content-list"), payload, format="json", **self._hdr(self.org_a)
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Content.objects.filter(title="Nope").exists())

    # --- papel de criador (D11) --------------------------------------------
    def _manual_quiz(self, user, content, org):
        self.client.force_authenticate(user)
        body = {"questions": [{"question": "2+2?", "options": ["4", "5"], "correctAnswer": 0}]}
        return self.client.post(
            reverse("quiz-manual-create", args=[content.id]),
            body,
            format="json",
            **self._hdr(org),
        )

    def test_teacher_with_learner_type_creates_inside_own_school_only(self):
        prof = make_user("prof-learner@test.com")  # user_type learner
        Membership.objects.create(user=prof, organizacao=self.org_a, role="teacher")
        self.client.force_authenticate(prof)
        payload = {"title": "Aula", "description": "d", "category": "design"}

        r = self.client.post(
            reverse("content-list"), payload, format="json", **self._hdr(self.org_a)
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        content = Content.objects.get(title="Aula")
        self.assertEqual(content.organizacao_id, self.org_a.id)
        self.assertEqual(
            self._manual_quiz(prof, content, self.org_a).status_code,
            status.HTTP_201_CREATED,
        )

        # Noutra escola não tem Membership; no marketplace não é creator.
        r = self.client.post(
            reverse("content-list"), payload, format="json", **self._hdr(self.org_b)
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        r = self.client.post(reverse("content-list"), payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_creator_demoted_to_student_cannot_create_quiz_in_school(self):
        Membership.objects.filter(user=self.teacher_a, organizacao=self.org_a).update(
            role="student"
        )
        content = make_content(self.teacher_a, "Sem quiz", self.org_a)
        self.assertEqual(
            self._manual_quiz(self.teacher_a, content, self.org_a).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.client.force_authenticate(self.teacher_a)
        r = self.client.post(
            reverse("quiz-generate", args=[content.id]),
            {"difficulty": "easy"},
            format="json",
            **self._hdr(self.org_a),
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_marketplace_creation_still_requires_creator_type(self):
        content = make_content(self.market_creator, "Mkt sem quiz")
        self.assertEqual(
            self._manual_quiz(self.market_creator, content, None).status_code,
            status.HTTP_201_CREATED,
        )
        self.client.force_authenticate(self.market_learner)
        payload = {"title": "Nope", "description": "d", "category": "design"}
        r = self.client.post(reverse("content-list"), payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    # --- organizacao só de leitura ---------------------------------------
    def test_create_ignores_organizacao_in_body(self):
        self.client.force_authenticate(self.teacher_a)
        payload = {
            "title": "Infiltrado",
            "description": "d",
            "category": "design",
            "organizacao": str(self.org_b.id),
        }
        r = self.client.post(
            reverse("content-list"), payload, format="json", **self._hdr(self.org_a)
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Content.objects.get(title="Infiltrado").organizacao_id, self.org_a.id
        )

    def test_owner_cannot_move_content_to_other_organization(self):
        self.client.force_authenticate(self.teacher_a)
        url = reverse("content-detail", args=[self.content_a.id])
        hdr = self._hdr(self.org_a)
        self.client.patch(url, {"organizacao": str(self.org_b.id)}, format="json", **hdr)
        self.client.patch(url, {"organizacao": None}, format="json", **hdr)
        self.content_a.refresh_from_db()
        self.assertEqual(self.content_a.organizacao_id, self.org_a.id)
        # E não aparece na escola B nem no marketplace.
        self.assertNotIn("Conteúdo A", self._titles(self.teacher_b, self.org_b))
        self.assertNotIn("Conteúdo A", self._titles(self.market_learner))

    def test_put_cannot_move_content_to_other_organization(self):
        self.client.force_authenticate(self.teacher_a)
        url = reverse("content-detail", args=[self.content_a.id])
        payload = {
            "title": "Conteúdo A",
            "description": "d",
            "category": "design",
            "organizacao": str(self.org_b.id),
        }
        r = self.client.put(url, payload, format="json", **self._hdr(self.org_a))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.content_a.refresh_from_db()
        self.assertEqual(self.content_a.organizacao_id, self.org_a.id)

    # --- quizzes -------------------------------------------------------
    def test_quiz_detail_cross_organization_is_404(self):
        self.client.force_authenticate(self.student_a)
        cross = reverse("quiz-detail", args=[self.quiz_b.id])
        self.assertEqual(
            self.client.get(cross, **self._hdr(self.org_a)).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        own = reverse("quiz-detail", args=[self.quiz_a.id])
        self.assertEqual(
            self.client.get(own, **self._hdr(self.org_a)).status_code,
            status.HTTP_200_OK,
        )

    def test_submit_cross_organization_is_404_and_leaves_no_trace(self):
        self.client.force_authenticate(self.student_a)
        r = self.client.post(
            reverse("quiz-submit", args=[self.quiz_b.id]),
            self._submit_payload(self.quiz_b),
            format="json",
            **self._hdr(self.org_a),
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(QuizSubmission.objects.exists())
        self.assertFalse(XPEvent.objects.exists())

    def test_submission_and_xp_carry_workspace(self):
        self.client.force_authenticate(self.student_a)
        r = self.client.post(
            reverse("quiz-submit", args=[self.quiz_a.id]),
            self._submit_payload(self.quiz_a),
            format="json",
            **self._hdr(self.org_a),
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(QuizSubmission.objects.get().organizacao_id, self.org_a.id)
        self.assertEqual(XPEvent.objects.get().organizacao_id, self.org_a.id)

    def test_quiz_creation_for_other_organization_content_is_404(self):
        """Mesmo sendo membro das duas, o contexto activo manda."""
        dual = make_user("dual@test.com", "creator")
        Membership.objects.create(user=dual, organizacao=self.org_a, role="teacher")
        Membership.objects.create(user=dual, organizacao=self.org_b, role="teacher")
        content = make_content(dual, "Do dual em B", self.org_b)
        self.client.force_authenticate(dual)
        url = reverse("quiz-manual-create", args=[content.id])
        body = {"questions": [{"question": "q", "options": ["a", "b"], "correctAnswer": 0}]}

        r = self.client.post(url, body, format="json", **self._hdr(self.org_a))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Quiz.objects.filter(content=content).exists())

        # no contexto certo funciona e o quiz herda a organização do conteúdo
        r = self.client.post(url, body, format="json", **self._hdr(self.org_b))
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Quiz.objects.get(content=content).organizacao_id, self.org_b.id)
