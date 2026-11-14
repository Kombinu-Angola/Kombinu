"""
Dados de demonstração: duas escolas, contas, conteúdos, quizzes com
submissões, trilhas, enquetes com votos e notificações.

Tudo o que este comando cria é identificável: contas em `@demo.kombinu.com` e
organizações com slug `demo-*`. É idempotente (correr de novo não duplica) e
`--limpar` apaga só esses dados. Se houver dados reais ligados aos de
demonstração (ex.: um utilizador real respondeu a um quiz demo), o `--limpar`
recusa e não apaga nada.

As submissões de quizzes passam pela própria `QuizSubmissionView`, e as
enquetes e trilhas pelos serviços normais, para o ledger de XP, o progresso
nas trilhas e as notificações ficarem consistentes com a API.
"""

import os
import random
import unicodedata

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.institutional import generate_temporary_password
from apps.accounts.models import CustomUser
from apps.contents.models import Content
from apps.enquetes import services as enquete_services
from apps.enquetes.models import Enquete, EnqueteVoto
from apps.notificacoes.models import Notificacao
from apps.notificacoes.services import notify_members
from apps.quizzes.models import Option, Question, Quiz, QuizSubmission
from apps.quizzes.views import QuizSubmissionView
from apps.rankings.models import XPEvent
from apps.tenancy import services as tenancy_services
from apps.tenancy.models import (
    AuditoriaMembro,
    ConversaoMarketplace,
    Membership,
    Organizacao,
    ProvisionamentoLote,
)
from apps.trilhas import services as trilha_services
from apps.trilhas.models import Trilha, TrilhaItem, TrilhaProgresso

from . import _seed_demo_dados as dados

PASSWORD_ENV = "SEED_DEMO_PASSWORD"
MIN_PASSWORD_LENGTH = 12
DEMO_SLUGS = [o["slug"] for o in dados.ORGANIZACOES.values()]
STUDENT_KEYS = list(dados.APTIDAO)


def demo_email(key):
    first, last = next((u[1], u[2]) for u in dados.UTILIZADORES if u[0] == key)
    if key.startswith("admin_"):
        local = key.replace("_", ".")
    else:
        local = f"{first}.{last}"
    return f"{_ascii(local).lower()}@{dados.DEMO_EMAIL_DOMAIN}"


def _ascii(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def demo_users():
    return CustomUser.objects.filter(email__iendswith="@" + dados.DEMO_EMAIL_DOMAIN)


def demo_orgs():
    return Organizacao.objects.filter(slug__in=DEMO_SLUGS)


class Command(BaseCommand):
    help = (
        "Cria dados de demonstração (contas @demo.kombinu.com e escolas demo-*). "
        "Idempotente. Use --limpar para os remover."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limpar",
            action="store_true",
            help="Remove só os dados de demonstração e termina.",
        )
        parser.add_argument(
            "--confirmar-producao",
            action="store_true",
            help="Necessário para correr com DEBUG=False.",
        )
        parser.add_argument(
            "--redefinir-passwords",
            action="store_true",
            help="Gera passwords novas também para as contas demo que já existem.",
        )

    # ------------------------------------------------------------------ entrada
    def handle(self, *args, **options):
        if not settings.DEBUG and not options["confirmar_producao"]:
            raise CommandError(
                "DEBUG=False: isto parece produção. Volte a correr com "
                "--confirmar-producao se é mesmo isso que quer."
            )
        if options["limpar"]:
            self.limpar()
            return

        env_password = os.environ.get(PASSWORD_ENV) or None
        if env_password is not None and len(env_password) < MIN_PASSWORD_LENGTH:
            raise CommandError(
                f"{PASSWORD_ENV} tem de ter pelo menos {MIN_PASSWORD_LENGTH} caracteres."
            )

        self._check_orgs_are_demo()
        with transaction.atomic():
            credenciais = self.seed(env_password, options["redefinir_passwords"])
        self._print_summary(credenciais, env_password is not None)

    # ------------------------------------------------------------ verificações
    def _check_orgs_are_demo(self):
        intrusos = Membership.objects.filter(organizacao__in=demo_orgs()).exclude(
            user__in=demo_users()
        )
        if intrusos.exists():
            raise CommandError(
                "Há membros reais numa organização com slug de demonstração "
                f"({', '.join(DEMO_SLUGS)}). Nada foi alterado."
            )

    # -------------------------------------------------------------------- seed
    def seed(self, env_password, reset_passwords):
        now = timezone.now()
        self.orgs = {}
        for key, data in dados.ORGANIZACOES.items():
            org, _ = Organizacao.objects.get_or_create(
                slug=data["slug"],
                defaults={"name": data["name"], "org_type": data["org_type"]},
            )
            self.orgs[key] = org

        roles = {}
        for user_key, org_key, role, *_ in dados.MEMBROS:
            roles.setdefault(user_key, set()).add(f"{role}@{org_key}")

        credenciais = []
        self.users = {}
        for key, first, last, user_type in dados.UTILIZADORES:
            email = demo_email(key)
            user = CustomUser.objects.filter(email__iexact=email).first()
            password = None
            if user is None:
                user = CustomUser(
                    username=email,
                    email=email,
                    first_name=first,
                    last_name=last,
                    user_type=user_type,
                    must_change_password=False,
                )
                password = env_password or generate_temporary_password()
                user.set_password(password)
                user.password_changed_at = now
                user.save()
            elif reset_passwords:
                password = env_password or generate_temporary_password()
                user.set_password(password)
                user.must_change_password = False
                user.temp_password_expires_at = None
                user.save()
            self.users[key] = user
            papel = ", ".join(sorted(roles.get(key, set()))) or (
                "criador marketplace"
                if user_type == "creator"
                else "estudante marketplace"
            )
            credenciais.append((email, papel, password))

        for user_key, org_key, role, year, faculty, course, code in dados.MEMBROS:
            Membership.objects.get_or_create(
                user=self.users[user_key],
                organizacao=self.orgs[org_key],
                defaults={
                    "role": role,
                    "academic_year": year,
                    "faculty": faculty,
                    "course": course,
                    "student_code": code,
                },
            )

        for org in self.orgs.values():
            notify_members(
                organizacao=org,
                source_key=f"demo_boas_vindas:{org.pk}",
                category="conta",
                tone="neutro",
                title="Bem-vindo ao Kombinu",
                body=f"Explora os conteúdos, as trilhas e as enquetes de {org.name}.",
            )

        self._seed_contents()
        self._seed_enquetes()
        self._seed_trilhas()
        self._seed_submissions()
        self._seed_content_progress()
        self._seed_votes()
        self._seed_marketplace_visits()
        return credenciais

    def _org(self, key):
        return self.orgs[key] if key else None

    def _seed_contents(self):
        self.contents = {}
        for key, d in dados.CONTEUDOS.items():
            content, _ = Content.objects.get_or_create(
                title=d["title"],
                creator=self.users[d["creator"]],
                organizacao=self._org(d["org"]),
                defaults={
                    "description": d["description"],
                    "category": d["category"],
                    "level": d["level"],
                    "duration": d["duration"],
                    "tags": d["tags"],
                    "text_content": "\n\n".join(d["paragraphs"]),
                    "type": "text",
                },
            )
            self.contents[key] = content
            if d["questions"] and not Quiz.objects.filter(content=content).exists():
                quiz = Quiz.objects.create(
                    title=f"Quiz: {content.title}",
                    content=content,
                    organizacao=content.organizacao,
                )
                for q in d["questions"]:
                    question = Question.objects.create(
                        quiz=quiz, question_text=q["question"]
                    )
                    for index, text in enumerate(q["options"]):
                        Option.objects.create(
                            question=question,
                            text=text,
                            is_correct=index == q["correct"],
                        )

    def _quiz_for(self, content_key):
        return Quiz.objects.get(content=self.contents[content_key])

    def _seed_enquetes(self):
        self.enquetes = {}
        for d in dados.ENQUETES:
            creator = self.users[d["creator"]]
            org = self._org(d["org"])
            enquete = Enquete.objects.filter(
                question=d["question"], creator=creator, organizacao=org
            ).first()
            if enquete is None:
                enquete = enquete_services.create_enquete(
                    creator=creator,
                    organizacao=org,
                    data={
                        "kind": d["kind"],
                        "question": d["question"],
                        "decision": d["decision"],
                        "faculty": d["faculty"],
                        "subject": d["subject"],
                        "trigger": d["trigger"],
                        "sample_target": d["sample_target"],
                        "segment_size": d["segment_size"],
                        "options": d["options"],
                    },
                )
                enquete = enquete_services.publish(enquete)
            self.enquetes[d["key"]] = enquete

    def _seed_trilhas(self):
        self.trilhas = []
        for d in dados.TRILHAS:
            creator = self.users[d["creator"]]
            org = self._org(d["org"])
            trilha, created = Trilha.objects.get_or_create(
                title=d["title"],
                creator=creator,
                organizacao=org,
                defaults={
                    "headline": d["headline"],
                    "subject": d["subject"],
                    "year": d["year"],
                    "semester": d["semester"],
                    "is_sequential": d["is_sequential"],
                },
            )
            if created:
                for kind, key in d["items"]:
                    if kind == "conteudo":
                        target = self.contents[key]
                    elif kind == "quiz":
                        target = self._quiz_for(key)
                    else:
                        target = self.enquetes[key]
                    trilha_services.add_item(
                        trilha, creator, {"kind": kind, "target_id": target.pk}
                    )
                trilha = trilha_services.publish_trilha(trilha)
            self.trilhas.append((d, trilha))

    def _members_of(self, org_key):
        return [
            self.users[u]
            for u, o, role, *_ in dados.MEMBROS
            if o == org_key and role == "student"
        ]

    def _eligible_students(self, org_key):
        if org_key is None:
            return [self.users[k] for k in STUDENT_KEYS]
        return self._members_of(org_key)

    def _seed_submissions(self):
        factory = APIRequestFactory()
        view = QuizSubmissionView.as_view()
        student_keys = {self.users[k].pk: k for k in STUDENT_KEYS}
        for content_key, d in dados.CONTEUDOS.items():
            if not d["questions"]:
                continue
            quiz = self._quiz_for(content_key)
            org = self._org(d["org"])
            questions = list(quiz.questions.prefetch_related("options"))
            for user in self._eligible_students(d["org"]):
                key = student_keys[user.pk]
                rng = random.Random(f"{key}:{content_key}")
                if rng.random() > 0.75:
                    continue
                if QuizSubmission.objects.filter(user=user, quiz=quiz).exists():
                    continue
                answers = []
                for question in questions:
                    options = list(question.options.all())
                    correct = [o for o in options if o.is_correct]
                    wrong = [o for o in options if not o.is_correct]
                    pick = (
                        correct[0]
                        if rng.random() < dados.APTIDAO[key] or not wrong
                        else rng.choice(wrong)
                    )
                    answers.append(
                        {
                            "question_id": str(question.pk),
                            "selected_option_id": str(pick.pk),
                        }
                    )
                extra = {"HTTP_X_WORKSPACE": str(org.pk)} if org else {}
                request = factory.post(
                    reverse("quiz-submit", args=[quiz.pk]),
                    {"answers": answers},
                    format="json",
                    **extra,
                )
                force_authenticate(request, user=user)
                response = view(request, quiz_id=quiz.pk)
                if response.status_code not in (200, 201):
                    raise CommandError(
                        f"Submissão demo falhou ({response.status_code}) em {quiz.title}."
                    )

    def _seed_content_progress(self):
        for d, trilha in self.trilhas:
            for user in self._eligible_students(d["org"]):
                rng = random.Random(f"{user.email}:{d['key']}")
                for item in trilha.items.filter(kind="conteudo"):
                    if rng.random() < 0.6:
                        trilha_services.complete_content_item(user, item)

    def _seed_votes(self):
        for d in dados.ENQUETES:
            enquete = Enquete.objects.get(pk=self.enquetes[d["key"]].pk)
            options = list(enquete.options.all())
            for user in self._members_of(d["org"]):
                if enquete.state != Enquete.STATE_PUBLISHED:
                    break
                rng = random.Random(f"{user.email}:{d['key']}")
                if rng.random() > 0.85:
                    continue
                if EnqueteVoto.objects.filter(enquete=enquete, user=user).exists():
                    continue
                # Preferência ligeira pelas primeiras opções, para os
                # resultados não ficarem uniformes.
                weights = [len(options) - i for i in range(len(options))]
                opcao = rng.choices(options, weights=weights)[0]
                enquete_services.cast_vote(
                    user=user,
                    enquete=enquete,
                    opcao_id=opcao.pk,
                    organizacao=enquete.organizacao,
                )
                enquete.refresh_from_db()
            if d["close"] and enquete.state == Enquete.STATE_PUBLISHED:
                enquete_services.close(enquete)

    def _seed_marketplace_visits(self):
        for user_key in {m[0] for m in dados.MEMBROS if m[2] == "student"}:
            user = self.users[user_key]
            if random.Random(f"{user.email}:visita").random() < 0.6:
                tenancy_services.record_marketplace_visit(user)

    def _print_summary(self, credenciais, from_env):
        out = self.stdout
        out.write(self.style.SUCCESS("Dados de demonstração prontos."))
        for org in demo_orgs().order_by("slug"):
            out.write(f"  {org.name}: código {org.code}, workspace {org.pk}")
        users = demo_users()
        out.write(
            f"  {users.count()} contas, "
            f"{Content.objects.filter(creator__in=users).count()} conteúdos, "
            f"{QuizSubmission.objects.filter(user__in=users).count()} submissões, "
            f"{Trilha.objects.filter(creator__in=users).count()} trilhas, "
            f"{Enquete.objects.filter(creator__in=users).count()} enquetes"
        )
        novas = [c for c in credenciais if c[2]]
        if not novas:
            out.write(
                "Nenhuma conta nova: as passwords existentes não mudaram "
                "(use --redefinir-passwords para gerar novas)."
            )
            return
        if from_env:
            out.write(f"{len(novas)} contas com a password definida em {PASSWORD_ENV}:")
        else:
            out.write("Credenciais (mostradas só agora; guarde-as num local seguro):")
        width = max(len(c[0]) for c in novas)
        for email, papel, password in novas:
            shown = "" if from_env else password
            out.write(f"  {email.ljust(width)}  {papel:<35}  {shown}")

    # ------------------------------------------------------------------ limpar
    def limpar(self):
        user_ids = list(demo_users().values_list("pk", flat=True))
        org_ids = list(demo_orgs().values_list("pk", flat=True))
        content_ids = list(
            Content.objects.filter(
                Q(creator_id__in=user_ids) | Q(organizacao_id__in=org_ids)
            ).values_list("pk", flat=True)
        )
        quiz_ids = list(
            Quiz.objects.filter(
                Q(content_id__in=content_ids) | Q(organizacao_id__in=org_ids)
            ).values_list("pk", flat=True)
        )
        trilha_ids = list(
            Trilha.objects.filter(
                Q(creator_id__in=user_ids) | Q(organizacao_id__in=org_ids)
            ).values_list("pk", flat=True)
        )
        enquete_ids = list(
            Enquete.objects.filter(
                Q(creator_id__in=user_ids) | Q(organizacao_id__in=org_ids)
            ).values_list("pk", flat=True)
        )

        not_demo = ~Q(user_id__in=user_ids)
        bloqueios = {
            "membros reais nas escolas demo": Membership.objects.filter(
                not_demo, organizacao_id__in=org_ids
            ),
            "submissões de utilizadores reais em quizzes demo": QuizSubmission.objects.filter(
                not_demo, quiz_id__in=quiz_ids
            ),
            "XP de utilizadores reais nas escolas demo": XPEvent.objects.filter(
                not_demo, organizacao_id__in=org_ids
            ),
            "votos de utilizadores reais em enquetes demo": EnqueteVoto.objects.filter(
                not_demo, enquete_id__in=enquete_ids
            ),
            "progresso de utilizadores reais em trilhas demo": TrilhaProgresso.objects.filter(
                not_demo, item__trilha_id__in=trilha_ids
            ),
            "notificações de utilizadores reais nas escolas demo": Notificacao.objects.filter(
                not_demo, organizacao_id__in=org_ids
            ),
            "conversões de utilizadores reais nas escolas demo": ConversaoMarketplace.objects.filter(
                not_demo, organizacao_id__in=org_ids
            ),
            "trilhas reais com passos demo": TrilhaItem.objects.filter(
                Q(content_id__in=content_ids)
                | Q(quiz_id__in=quiz_ids)
                | Q(enquete_id__in=enquete_ids)
            ).exclude(trilha_id__in=trilha_ids),
            "trilhas reais com exame final demo": Trilha.objects.filter(
                final_exam_id__in=quiz_ids
            ).exclude(pk__in=trilha_ids),
            "conteúdos de autores reais nas escolas demo": Content.objects.filter(
                organizacao_id__in=org_ids
            ).exclude(creator_id__in=user_ids),
            "trilhas de autores reais nas escolas demo": Trilha.objects.filter(
                organizacao_id__in=org_ids
            ).exclude(creator_id__in=user_ids),
            "enquetes de autores reais nas escolas demo": Enquete.objects.filter(
                organizacao_id__in=org_ids
            ).exclude(creator_id__in=user_ids),
        }
        encontrados = {k: qs.count() for k, qs in bloqueios.items()}
        encontrados = {k: n for k, n in encontrados.items() if n}
        if encontrados:
            detalhe = "; ".join(f"{n} {k}" for k, n in encontrados.items())
            raise CommandError(
                f"Há dados reais ligados aos de demonstração ({detalhe}). "
                "Nada foi apagado."
            )

        user_q = Q(user_id__in=user_ids)
        org_q = Q(organizacao_id__in=org_ids)
        with transaction.atomic():
            TrilhaProgresso.objects.filter(
                user_q | Q(item__trilha_id__in=trilha_ids)
            ).delete()
            Trilha.objects.filter(pk__in=trilha_ids).delete()
            Notificacao.objects.filter(user_q | org_q).delete()
            EnqueteVoto.objects.filter(user_q | Q(enquete_id__in=enquete_ids)).delete()
            Enquete.objects.filter(pk__in=enquete_ids).delete()
            XPEvent.objects.filter(user_q | org_q).delete()
            QuizSubmission.objects.filter(
                user_q | org_q | Q(quiz_id__in=quiz_ids)
            ).delete()
            Quiz.objects.filter(pk__in=quiz_ids).delete()
            Content.objects.filter(pk__in=content_ids).delete()
            ConversaoMarketplace.objects.filter(user_q | org_q).delete()
            ProvisionamentoLote.objects.filter(organizacao_id__in=org_ids).delete()
            AuditoriaMembro.objects.filter(organizacao_id__in=org_ids).delete()
            CustomUser.objects.filter(pk__in=user_ids).delete()
            Organizacao.objects.filter(pk__in=org_ids).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Removidos os dados de demonstração: {len(user_ids)} contas, "
                f"{len(org_ids)} organizações, {len(content_ids)} conteúdos, "
                f"{len(trilha_ids)} trilhas, {len(enquete_ids)} enquetes."
            )
        )
