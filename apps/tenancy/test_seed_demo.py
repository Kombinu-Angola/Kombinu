"""Comando `seed_demo`: idempotência, limpeza segura e isolamento."""

import os
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import CustomUser
from apps.contents.models import Content
from apps.enquetes.models import Enquete, EnqueteVoto
from apps.notificacoes.models import Notificacao
from apps.quizzes.models import Question, Quiz, QuizSubmission
from apps.rankings.models import XPEvent
from apps.rankings.services import record_xp
from apps.tenancy.management.commands import _seed_demo_dados as dados
from apps.tenancy.models import Membership, Organizacao
from apps.trilhas.models import Trilha, TrilhaItem, TrilhaProgresso

DOMAIN = "@" + dados.DEMO_EMAIL_DOMAIN
MODELS = (
    CustomUser,
    Organizacao,
    Membership,
    Content,
    Quiz,
    Question,
    QuizSubmission,
    XPEvent,
    Trilha,
    TrilhaItem,
    TrilhaProgresso,
    Enquete,
    EnqueteVoto,
    Notificacao,
)


def seed(**options):
    out = StringIO()
    call_command("seed_demo", stdout=out, **options)
    return out.getvalue()


def seed_args(*args, **options):
    out = StringIO()
    call_command("seed_demo", *args, stdout=out, **options)
    return out.getvalue()


def counts():
    return {m.__name__: m.objects.count() for m in MODELS}


def demo_users():
    return CustomUser.objects.filter(email__endswith=DOMAIN)


def create_real_data(cls):
    """Escola real com membro, e conteúdo, quiz, submissão e XP reais."""
    cls.org = Organizacao.objects.create(name="Escola Real", slug="escola-real")
    cls.student = CustomUser.objects.create_user(
        username="aluno@real.ao",
        email="aluno@real.ao",
        password="x",
        user_type="learner",
    )
    Membership.objects.create(user=cls.student, organizacao=cls.org)
    cls.creator = CustomUser.objects.create_user(
        username="autor@real.ao",
        email="autor@real.ao",
        password="x",
        user_type="creator",
    )
    cls.content = Content.objects.create(
        title="Conteúdo real",
        description="d",
        creator=cls.creator,
        category="tecnologia",
    )
    cls.quiz = Quiz.objects.create(title="Quiz real", content=cls.content)
    sub = QuizSubmission.objects.create(
        user=cls.student, quiz=cls.quiz, score=10, xp_awarded=10
    )
    record_xp(
        user=cls.student,
        amount=10,
        source_type="quiz_submission",
        source_id=sub.pk,
    )


@override_settings(DEBUG=True)
class SeededTests(TestCase):
    """Um único seed por classe; cada teste corre numa transacção revertida."""

    @classmethod
    def setUpTestData(cls):
        create_real_data(cls)
        cls.real = counts()
        cls.output = seed()
        cls.uan = Organizacao.objects.get(slug="demo-uan")
        cls.kiala = Organizacao.objects.get(slug="demo-colegio-kiala")

    # ---------------------------------------------------------------- criação
    def test_creates_demo_data(self):
        users = demo_users()
        self.assertEqual(users.count(), len(dados.UTILIZADORES))
        self.assertFalse(users.filter(must_change_password=True).exists())
        demo_contents = Content.objects.filter(creator__in=users)
        self.assertEqual(demo_contents.count(), len(dados.CONTEUDOS))
        self.assertEqual(demo_contents.filter(organizacao=None).count(), 15)
        self.assertEqual(
            set(demo_contents.values_list("category", flat=True)),
            {"tecnologia", "negocios", "design"},
        )
        self.assertTrue(QuizSubmission.objects.filter(user__in=users).exists())
        self.assertTrue(TrilhaProgresso.objects.exists())
        self.assertTrue(EnqueteVoto.objects.exists())
        self.assertTrue(Notificacao.objects.filter(organizacao=self.uan).exists())
        self.assertTrue(Notificacao.objects.filter(organizacao=self.kiala).exists())
        self.assertFalse(Trilha.objects.filter(is_published=False).exists())
        self.assertTrue(Enquete.objects.filter(state="encerrada").exists())

    def test_xp_ledger_matches_activity(self):
        users = demo_users()
        subs = QuizSubmission.objects.filter(user__in=users)
        self.assertEqual(
            sum(subs.values_list("xp_awarded", flat=True)),
            sum(
                XPEvent.objects.filter(
                    user__in=users, source_type="quiz_submission"
                ).values_list("amount", flat=True)
            ),
        )
        self.assertEqual(
            XPEvent.objects.filter(source_type="enquete_voto").count(),
            EnqueteVoto.objects.count(),
        )
        totals = {}
        for event in XPEvent.objects.filter(organizacao=self.uan):
            totals[event.user_id] = totals.get(event.user_id, 0) + event.amount
        self.assertGreater(len(set(totals.values())), 3)

    def test_printed_passwords_work(self):
        for user in demo_users()[:3]:
            line = next(l for l in self.output.splitlines() if user.email in l)
            self.assertTrue(user.check_password(line.split()[-1]))

    def test_idempotent(self):
        before = counts()
        output = seed()
        self.assertEqual(counts(), before)
        self.assertIn("Nenhuma conta nova", output)

    def test_reset_passwords(self):
        user = demo_users().first()
        old_hash = user.password
        output = seed(redefinir_passwords=True)
        user.refresh_from_db()
        self.assertNotEqual(user.password, old_hash)
        line = next(l for l in output.splitlines() if user.email in l)
        self.assertTrue(user.check_password(line.split()[-1]))

    # ---------------------------------------------------------- --set-password
    def test_set_password_value_applies_to_existing_demo_accounts(self):
        chosen = "Reuniao-Kombinu-2026"
        real_hashes = dict(
            CustomUser.objects.exclude(email__endswith=DOMAIN).values_list(
                "pk", "password"
            )
        )
        err = StringIO()
        output = seed(set_password=chosen, stderr=err)
        self.assertIn("histórico", err.getvalue())
        self.assertNotIn(chosen, output)
        for user in demo_users():
            self.assertTrue(user.check_password(chosen), user.email)
            self.assertFalse(user.must_change_password)
        # Só as contas demo mudam.
        self.assertEqual(
            dict(
                CustomUser.objects.exclude(email__endswith=DOMAIN).values_list(
                    "pk", "password"
                )
            ),
            real_hashes,
        )
        self.assertTrue(self.student.check_password("x"))

    def test_set_password_prompt_asks_twice_without_echo(self):
        chosen = "Reuniao-Kombinu-2026"
        with mock.patch("getpass.getpass", side_effect=[chosen, chosen]) as ask:
            err = StringIO()
            output = seed_args("--set-password", stderr=err)
        self.assertEqual(ask.call_count, 2)
        self.assertEqual(err.getvalue(), "")
        self.assertNotIn(chosen, output)
        self.assertTrue(demo_users().first().check_password(chosen))

    def test_set_password_beats_environment(self):
        chosen = "Reuniao-Kombinu-2026"
        with mock.patch.dict(
            os.environ, {"SEED_DEMO_PASSWORD": "Outra-Password-Longa"}
        ):
            seed(set_password=chosen, stderr=StringIO())
        self.assertTrue(demo_users().first().check_password(chosen))

    def test_set_password_invalid_changes_nothing(self):
        before = dict(demo_users().values_list("pk", "password"))
        with self.assertRaises(CommandError):
            seed(set_password="12345678", stderr=StringIO())
        self.assertEqual(dict(demo_users().values_list("pk", "password")), before)

    # ----------------------------------------------- revogação de tokens antigos
    def old_token(self, user):
        """Token emitido há uma hora, depois da última troca de password."""
        CustomUser.objects.filter(pk=user.pk).update(
            password_changed_at=timezone.now() - timedelta(days=1)
        )
        token = AccessToken.for_user(user)
        token["iat"] = int(timezone.now().timestamp()) - 3600
        return str(token)

    def status_with(self, token):
        client = APIClient()
        r = client.get(reverse("content-list"), HTTP_AUTHORIZATION=f"Bearer {token}")
        return r.status_code

    def test_set_password_revokes_old_tokens(self):
        user = demo_users().first()
        token = self.old_token(user)
        self.assertEqual(self.status_with(token), 200)
        seed(set_password="Reuniao-Kombinu-2026", stderr=StringIO())
        self.assertEqual(self.status_with(token), 401)

    def test_reset_passwords_revokes_old_tokens(self):
        user = demo_users().first()
        token = self.old_token(user)
        self.assertEqual(self.status_with(token), 200)
        seed(redefinir_passwords=True)
        self.assertEqual(self.status_with(token), 401)

    def test_rerun_without_reset_keeps_tokens(self):
        user = demo_users().first()
        token = self.old_token(user)
        seed()
        self.assertEqual(self.status_with(token), 200)

    # ----------------------------------------------------------------- limpar
    def test_limpar_removes_only_demo(self):
        seed(limpar=True)
        self.assertEqual(counts(), self.real)
        self.assertFalse(demo_users().exists())
        self.assertFalse(Organizacao.objects.filter(slug__startswith="demo-").exists())
        self.assertTrue(Content.objects.filter(pk=self.content.pk).exists())
        self.assertTrue(XPEvent.objects.filter(user=self.student).exists())
        self.assertTrue(Membership.objects.filter(organizacao=self.org).exists())

    def test_limpar_refuses_when_real_user_used_demo(self):
        demo_quiz = Quiz.objects.filter(
            content__creator__in=demo_users(), organizacao=None
        ).first()
        QuizSubmission.objects.create(user=self.student, quiz=demo_quiz, score=0)
        before = counts()
        with self.assertRaises(CommandError):
            seed(limpar=True)
        self.assertEqual(counts(), before)

    def test_limpar_refuses_when_real_trilha_uses_demo_content(self):
        trilha = Trilha.objects.create(
            creator=self.creator, title="Trilha real", subject="x"
        )
        demo_content = Content.objects.filter(
            creator__in=demo_users(), organizacao=None
        ).first()
        TrilhaItem.objects.create(
            trilha=trilha, order=1, kind="conteudo", content=demo_content
        )
        before = counts()
        with self.assertRaises(CommandError):
            seed(limpar=True)
        self.assertEqual(counts(), before)

    # ------------------------------------------------------------- isolamento
    def titles(self, user, org=None):
        client = APIClient()
        client.force_authenticate(user)
        extra = {"HTTP_X_WORKSPACE": str(org.pk)} if org else {}
        r = client.get(reverse("content-list"), **extra)
        self.assertEqual(r.status_code, 200, r.data)
        return {row["title"] for row in r.data["results"]}

    def school_titles(self, org):
        return set(
            Content.objects.filter(organizacao=org).values_list("title", flat=True)
        )

    def neusa(self):
        # Estudante das duas escolas demo.
        return CustomUser.objects.get(email="neusa.kalandula" + DOMAIN)

    def test_school_content_not_in_marketplace(self):
        marketplace = self.titles(self.neusa())
        expected = set(
            Content.objects.filter(organizacao=None).values_list("title", flat=True)
        )
        self.assertEqual(marketplace, expected)
        self.assertFalse(marketplace & self.school_titles(self.uan))
        self.assertFalse(marketplace & self.school_titles(self.kiala))

    def test_school_content_not_in_other_school(self):
        kiala = self.titles(self.neusa(), self.kiala)
        self.assertEqual(kiala, self.school_titles(self.kiala))
        self.assertFalse(kiala & self.school_titles(self.uan))

    def test_other_school_detail_is_404(self):
        uan_content = Content.objects.filter(organizacao=self.uan).first()
        client = APIClient()
        client.force_authenticate(self.neusa())
        r = client.get(
            reverse("content-detail", args=[uan_content.pk]),
            HTTP_X_WORKSPACE=str(self.kiala.pk),
        )
        self.assertEqual(r.status_code, 404)

    def test_non_member_cannot_open_school(self):
        hugo = CustomUser.objects.get(email="hugo.lussati" + DOMAIN)
        client = APIClient()
        client.force_authenticate(hugo)
        r = client.get(reverse("content-list"), HTTP_X_WORKSPACE=str(self.uan.pk))
        self.assertEqual(r.status_code, 403)

    def test_school_xp_stays_in_school(self):
        subs = QuizSubmission.objects.filter(quiz__organizacao=self.uan)
        self.assertTrue(subs.exists())
        self.assertFalse(subs.exclude(organizacao=self.uan).exists())
        for sub in subs.filter(xp_awarded__gt=0):
            event = XPEvent.objects.get(
                source_type="quiz_submission", source_id=str(sub.pk)
            )
            self.assertEqual(event.organizacao_id, self.uan.pk)


@override_settings(DEBUG=True)
class UnseededTests(TestCase):
    def test_short_environment_password_refused(self):
        with mock.patch.dict(os.environ, {"SEED_DEMO_PASSWORD": "curta"}):
            with self.assertRaises(CommandError):
                seed()
        self.assertFalse(CustomUser.objects.exists())

    def test_set_password_validation_failure_creates_nothing(self):
        for weak in ("password", "12345678", "curta"):
            with self.assertRaises(CommandError):
                seed(set_password=weak, stderr=StringIO())
        self.assertFalse(CustomUser.objects.exists())

    def test_set_password_prompt_mismatch_creates_nothing(self):
        with mock.patch(
            "getpass.getpass", side_effect=["Reuniao-2026-A", "Reuniao-2026-B"]
        ):
            with self.assertRaises(CommandError):
                seed_args("--set-password")
        self.assertFalse(CustomUser.objects.exists())

    def test_seed_refuses_preexisting_demo_accounts(self):
        # Contas registadas no domínio demo antes da 1.ª execução (ex.: por um
        # caminho antigo de registo) não podem herdar papéis.
        for email in ("admin.uan@demo.kombinu.com", "Outra@Demo.Kombinu.com"):
            CustomUser.objects.create_user(
                username=email, email=email, password="x", user_type="learner"
            )
        with self.assertRaises(CommandError) as ctx:
            seed()
        message = str(ctx.exception)
        self.assertIn("2 contas", message)
        self.assertNotIn("admin.uan", message.lower())
        self.assertNotIn("outra", message.lower())
        self.assertFalse(Organizacao.objects.filter(slug__startswith="demo-").exists())
        self.assertFalse(Membership.objects.exists())
        self.assertTrue(
            CustomUser.objects.get(email="admin.uan@demo.kombinu.com").check_password(
                "x"
            )
        )

    def test_limpar_without_demo_data_is_harmless(self):
        create_real_data(self)
        before = counts()
        seed(limpar=True)
        self.assertEqual(counts(), before)

    def test_seed_refuses_real_member_in_demo_slug(self):
        create_real_data(self)
        org = Organizacao.objects.create(name="Engano", slug="demo-uan")
        Membership.objects.create(user=self.student, organizacao=org)
        with self.assertRaises(CommandError):
            seed()
        self.assertFalse(demo_users().exists())


@override_settings(DEBUG=False)
class ProducaoTests(TestCase):
    def test_refuses_without_flag(self):
        with self.assertRaises(CommandError):
            seed()
        with self.assertRaises(CommandError):
            seed(limpar=True)
        self.assertFalse(CustomUser.objects.exists())

    def test_runs_with_flag_and_environment_password(self):
        secret = "Demo-Reuniao-2026!"
        with mock.patch.dict(os.environ, {"SEED_DEMO_PASSWORD": secret}):
            output = seed(confirmar_producao=True)
        self.assertNotIn(secret, output)
        user = demo_users().first()
        self.assertTrue(user.check_password(secret))
        seed(limpar=True, confirmar_producao=True)
        self.assertFalse(demo_users().exists())
