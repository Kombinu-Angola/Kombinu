"""K2: catálogo global de cadeiras e filtro `?cadeira=` sempre no contexto activo."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import CustomUser
from apps.contents.models import Cadeira, Content
from apps.quizzes.models import Quiz
from apps.tenancy.models import Membership, Organizacao
from apps.trilhas.models import Trilha


def make_user(email, user_type="learner"):
    return CustomUser.objects.create_user(
        username=email, email=email, password="pass12345", user_type=user_type
    )


class CadeiraCatalogTests(APITestCase):
    def setUp(self):
        self.user = make_user("leitor@test.com")
        self.client.force_authenticate(self.user)
        Cadeira.objects.create(nome="Direito Constitucional", curso="Direito")
        Cadeira.objects.create(nome="Direito Romano", curso="Direito")
        Cadeira.objects.create(nome="Cálculo I", curso="Engenharia Informática")

    def test_lists_whole_catalog_without_pagination(self):
        r = self.client.get(reverse("cadeira-list"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsInstance(r.data, list)
        self.assertEqual(
            [c["nome"] for c in r.data],
            ["Cálculo I", "Direito Constitucional", "Direito Romano"],
        )
        self.assertEqual(set(r.data[0]), {"id", "nome", "curso"})

    def test_filter_by_course_ignores_case(self):
        r = self.client.get(reverse("cadeira-list"), {"curso": "direito"})
        self.assertEqual(
            [c["nome"] for c in r.data], ["Direito Constitucional", "Direito Romano"]
        )

    def test_catalog_is_the_same_in_every_workspace(self):
        org = Organizacao.objects.create(name="Escola A", slug="escola-a")
        Membership.objects.create(user=self.user, organizacao=org)
        r = self.client.get(reverse("cadeira-list"), HTTP_X_WORKSPACE=str(org.pk))
        self.assertEqual(len(r.data), 3)

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        r = self.client.get(reverse("cadeira-list"))
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_same_name_in_two_courses_is_allowed(self):
        Cadeira.objects.create(nome="Cálculo I", curso="Economia")
        self.assertEqual(Cadeira.objects.filter(nome="Cálculo I").count(), 2)


class CadeiraIsolationTests(APITestCase):
    """
    Duas escolas e o marketplace, com objectos da mesma cadeira em cada um:
    o filtro por cadeira nunca atravessa o contexto activo.
    """

    def setUp(self):
        self.org_a = Organizacao.objects.create(name="Escola A", slug="escola-a")
        self.org_b = Organizacao.objects.create(name="Escola B", slug="escola-b")
        self.hdr_a = {"HTTP_X_WORKSPACE": str(self.org_a.pk)}
        self.hdr_b = {"HTTP_X_WORKSPACE": str(self.org_b.pk)}
        self.direito = Cadeira.objects.create(nome="Direito Constitucional")
        self.calculo = Cadeira.objects.create(nome="Cálculo I")

        self.autor = make_user("autor@test.com", "creator")
        self.aluno = make_user("aluno@test.com")
        Membership.objects.create(user=self.aluno, organizacao=self.org_a)
        Membership.objects.create(user=self.aluno, organizacao=self.org_b)
        self.estranho = make_user("estranho@test.com")
        Membership.objects.create(user=self.estranho, organizacao=self.org_a)

        for label, org in (("A", self.org_a), ("B", self.org_b), ("Mkt", None)):
            for cadeira in (self.direito, self.calculo):
                Content.objects.create(
                    title=f"{cadeira.nome} {label}",
                    description="d",
                    creator=self.autor,
                    category="tecnologia",
                    organizacao=org,
                    cadeira=cadeira,
                )
                Trilha.objects.create(
                    title=f"Trilha {cadeira.nome} {label}",
                    subject=cadeira.nome,
                    creator=self.autor,
                    organizacao=org,
                    cadeira=cadeira,
                    is_published=True,
                )

    def titles(self, url_name, user=None, **extra):
        self.client.force_authenticate(user or self.aluno)
        r = self.client.get(reverse(url_name), {"cadeira": self.direito.pk}, **extra)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        return {row["title"] for row in r.data["results"]}

    def test_contents_filter_stays_in_school_a(self):
        self.assertEqual(
            self.titles("content-list", **self.hdr_a), {"Direito Constitucional A"}
        )

    def test_contents_filter_stays_in_school_b(self):
        self.assertEqual(
            self.titles("content-list", **self.hdr_b), {"Direito Constitucional B"}
        )

    def test_contents_filter_stays_in_marketplace(self):
        self.assertEqual(self.titles("content-list"), {"Direito Constitucional Mkt"})
        self.assertEqual(
            self.titles("content-list", HTTP_X_WORKSPACE="marketplace"),
            {"Direito Constitucional Mkt"},
        )

    def test_trilhas_filter_stays_in_each_context(self):
        self.assertEqual(
            self.titles("trilha-list", **self.hdr_a),
            {"Trilha Direito Constitucional A"},
        )
        self.assertEqual(
            self.titles("trilha-list", **self.hdr_b),
            {"Trilha Direito Constitucional B"},
        )
        self.assertEqual(
            self.titles("trilha-list"), {"Trilha Direito Constitucional Mkt"}
        )

    def test_filter_needs_membership_in_the_workspace(self):
        self.client.force_authenticate(self.estranho)
        for name in ("content-list", "trilha-list"):
            r = self.client.get(
                reverse(name), {"cadeira": self.direito.pk}, **self.hdr_b
            )
            self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN, name)

    def test_unknown_cadeira_is_400(self):
        self.client.force_authenticate(self.aluno)
        for name in ("content-list", "trilha-list"):
            r = self.client.get(reverse(name), {"cadeira": 999999}, **self.hdr_a)
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, name)

    def test_unpublished_trilha_of_another_author_is_not_listed(self):
        Trilha.objects.filter(organizacao=self.org_a, cadeira=self.direito).update(
            is_published=False
        )
        self.assertEqual(self.titles("trilha-list", **self.hdr_a), set())

    def test_content_exposes_and_accepts_cadeira(self):
        content = Content.objects.get(title="Direito Constitucional Mkt")
        self.client.force_authenticate(self.autor)
        r = self.client.get(reverse("content-detail", args=[content.pk]))
        # C-K4: a leitura passa a ser o objecto {id, nome, curso}.
        self.assertEqual(r.data["cadeira"]["id"], self.direito.pk)
        r = self.client.patch(
            reverse("content-detail", args=[content.pk]),
            {"cadeira": self.calculo.pk},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        content.refresh_from_db()
        self.assertEqual(content.cadeira, self.calculo)
        r = self.client.patch(
            reverse("content-detail", args=[content.pk]),
            {"cadeira": 999999},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deleting_a_cadeira_keeps_the_objects(self):
        content = Content.objects.get(title="Direito Constitucional A")
        quiz = Quiz.objects.create(
            title="Quiz", content=content, organizacao=self.org_a, cadeira=self.direito
        )
        self.direito.delete()
        content.refresh_from_db()
        quiz.refresh_from_db()
        self.assertIsNone(content.cadeira)
        self.assertIsNone(quiz.cadeira)
        self.assertEqual(Trilha.objects.filter(cadeira__isnull=True).count(), 3)
