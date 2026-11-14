"""
Dados de demonstração: duas escolas, contas, conteúdos, quizzes com
submissões, trilhas, enquetes com votos e notificações.

Tudo o que este comando cria é identificável: contas em `@demo.kombinu.com` e
organizações com slug `demo-*`. É idempotente (correr de novo não duplica) e
`--limpar` apaga só esses dados. Se houver dados reais ligados aos de
demonstração (ex.: um utilizador real respondeu a um quiz demo), o `--limpar`
recusa e não apaga nada.

Pensado para correr contra uma base remota (cada consulta pode custar 100 a
300 ms): lê tudo em poucas consultas, calcula em memória e escreve em lote. As
submissões, os votos e o progresso seguem as mesmas regras da API e usam as
mesmas funções (`quiz_submission_xp`, `record_xp_many`, `stars_for`,
`ENQUETE_VOTE_XP`); a criação e a publicação de enquetes e a publicação de
trilhas passam pelos serviços normais, que validam e notificam.
"""

import getpass
import os
import random
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.institutional import generate_temporary_password
from apps.accounts.models import CustomUser
from apps.contents.models import Content
from apps.enquetes import services as enquete_services
from apps.enquetes.models import Enquete, EnqueteExibicao, EnqueteVoto
from apps.enquetes.services import ENQUETE_VOTE_XP
from apps.notificacoes.models import Notificacao
from apps.notificacoes.services import notify_members
from apps.quizzes.models import Option, Question, Quiz, QuizAnswer, QuizSubmission
from apps.rankings.models import XPEvent
from apps.rankings.services import quiz_submission_xp, record_xp_many
from apps.tenancy.codes import normalize_student_code
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
# Valor de `--set-password` quando a opção vem sem valor: pedir com getpass.
PROMPT = object()
DEMO_SLUGS = [o["slug"] for o in dados.ORGANIZACOES.values()]
STUDENT_KEYS = list(dados.APTIDAO)
# Submissões por lote: dá progresso visível sem multiplicar as consultas.
SUBMISSION_BATCH = 60
TARGET_FIELD = {"conteudo": "content", "quiz": "quiz", "enquete": "enquete"}


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
        parser.add_argument(
            "--set-password",
            nargs="?",
            const=PROMPT,
            default=None,
            metavar="PASSWORD",
            help=(
                "Usa esta password em todas as contas demo, incluindo as que já "
                "existem. Sem valor, é pedida sem eco (recomendado)."
            ),
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

        # Prioridade: --set-password > SEED_DEMO_PASSWORD > gerada com secrets.
        fixed_password, source = self._chosen_password(options["set_password"]), "set"
        if fixed_password is None:
            fixed_password, source = os.environ.get(PASSWORD_ENV) or None, "env"
            if fixed_password is not None and len(fixed_password) < MIN_PASSWORD_LENGTH:
                raise CommandError(
                    f"{PASSWORD_ENV} tem de ter pelo menos {MIN_PASSWORD_LENGTH} caracteres."
                )
        if fixed_password is None:
            source = None

        self._check_orgs_are_demo()
        self._check_no_preexisting_demo_accounts()
        # Com --set-password, as contas demo que já existem também ficam com ela.
        reset = options["redefinir_passwords"] or source == "set"
        with transaction.atomic():
            credenciais = self.seed(fixed_password, reset)
        self._print_summary(credenciais, source)

    def _chosen_password(self, value):
        if value is None:
            return None
        if value is PROMPT:
            password = getpass.getpass("Password para as contas demo: ")
            if password != getpass.getpass("Repita a password: "):
                raise CommandError("As passwords não coincidem. Nada foi alterado.")
        else:
            password = value
            self.stderr.write(
                "Aviso: a password passada em --set-password=<valor> fica no histórico "
                "da shell. Prefira --set-password sem valor."
            )
        if not password:
            raise CommandError("A password não pode ser vazia. Nada foi alterado.")
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError(
                "Password recusada: " + " ".join(exc.messages) + " Nada foi alterado."
            )
        return password

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

    def _check_no_preexisting_demo_accounts(self):
        """
        Antes da 1.ª execução não pode haver contas no domínio demo: seriam
        contas criadas por outra via, que o seed reutilizaria e às quais daria
        papéis (ex.: admin de uma escola demo).
        """
        if demo_orgs().count() == len(DEMO_SLUGS):
            return
        n = demo_users().count()
        if n:
            raise CommandError(
                f"Já existem {n} contas @{dados.DEMO_EMAIL_DOMAIN} sem as escolas "
                "de demonstração, ou seja, criadas fora deste comando. Reveja-as "
                "no admin antes de continuar. Nada foi alterado."
            )

    # -------------------------------------------------------------------- seed
    @contextmanager
    def _fase(self, label):
        """Uma linha por fase, para haver progresso visível contra uma base remota."""
        self.stdout.write(f"{label}…", ending=" ")
        self.stdout.flush()
        start = time.monotonic()
        yield
        self.stdout.write(f"ok ({time.monotonic() - start:.1f} s)")

    def seed(self, fixed_password, reset_passwords):
        self.now = timezone.now()
        with self._fase("Escolas e contas"):
            credenciais = self._seed_accounts(fixed_password, reset_passwords)
        with self._fase("Conteúdos e quizzes"):
            self._seed_contents()
        with self._fase("Enquetes"):
            self._seed_enquetes()
        with self._fase("Trilhas"):
            self._seed_trilhas()
        self._seed_submissions()
        with self._fase("Progresso nos conteúdos"):
            self._seed_content_progress()
        with self._fase("Votos"):
            self._seed_votes()
        with self._fase("Visitas ao marketplace"):
            self._seed_marketplace_visits()
        return credenciais

    def _org(self, key):
        return self.orgs[key] if key else None

    def _seed_accounts(self, fixed_password, reset_passwords):
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

        existing = {u.email.lower(): u for u in demo_users()}
        credenciais, new_users, reset_users, to_hash = [], [], [], []
        self.users = {}
        for key, first, last, user_type in dados.UTILIZADORES:
            email = demo_email(key)
            user = existing.get(email)
            password = None
            if user is None:
                password = fixed_password or generate_temporary_password()
                user = CustomUser(
                    username=email,
                    email=email,
                    first_name=first,
                    last_name=last,
                    user_type=user_type,
                    password_changed_at=self.now,
                    must_change_password=False,
                )
                new_users.append(user)
                to_hash.append((user, password))
            elif reset_passwords:
                password = fixed_password or generate_temporary_password()
                to_hash.append((user, password))
                # Invalida os tokens emitidos antes desta reposição.
                user.password_changed_at = self.now
                user.must_change_password = False
                user.temp_password_expires_at = None
                reset_users.append(user)
            self.users[key] = user
            papel = ", ".join(sorted(roles.get(key, set()))) or (
                "criador marketplace"
                if user_type == "creator"
                else "estudante marketplace"
            )
            credenciais.append((email, papel, password))

        self._hash_passwords(to_hash, fixed_password)
        if new_users:
            CustomUser.objects.bulk_create(new_users)
            if any(u.pk is None for u in new_users):
                # Bases sem RETURNING no bulk_create: recarregar os ids.
                ids = dict(
                    CustomUser.objects.filter(
                        email__in=[u.email for u in new_users]
                    ).values_list("email", "pk")
                )
                for u in new_users:
                    u.pk = u.id = ids[u.email]
        if reset_users:
            CustomUser.objects.bulk_update(
                reset_users,
                [
                    "password",
                    "password_changed_at",
                    "must_change_password",
                    "temp_password_expires_at",
                ],
            )

        existing_members = set(
            Membership.objects.filter(organizacao__in=self.orgs.values()).values_list(
                "user_id", "organizacao_id"
            )
        )
        Membership.objects.bulk_create(
            [
                Membership(
                    user=self.users[user_key],
                    organizacao=self.orgs[org_key],
                    role=role,
                    academic_year=year,
                    faculty=faculty,
                    course=course,
                    # O bulk_create não chama Membership.save(): normalizar aqui.
                    student_code=normalize_student_code(code) or None,
                )
                for user_key, org_key, role, year, faculty, course, code in dados.MEMBROS
                if (self.users[user_key].pk, self.orgs[org_key].pk)
                not in existing_members
            ]
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
        return credenciais

    def _hash_passwords(self, to_hash, fixed_password):
        """
        O PBKDF2 é propositadamente lento (cerca de 0,5 a 3 s por hash). Uma
        password escolhida é igual em todas as contas: basta um hash. As
        geradas têm um hash cada, calculados em paralelo (o `pbkdf2_hmac`
        liberta o GIL).
        """
        if not to_hash:
            return
        if fixed_password:
            hashed = make_password(fixed_password)
            hashes = [hashed] * len(to_hash)
        else:
            workers = max(1, min(8, os.cpu_count() or 1))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                hashes = list(pool.map(make_password, [p for _, p in to_hash]))
        for (user, _), hashed in zip(to_hash, hashes):
            user.password = hashed

    def _seed_contents(self):
        users = list(self.users.values())
        existing = {
            (c.title, c.creator_id, c.organizacao_id): c
            for c in Content.objects.filter(creator__in=users)
        }
        self.contents, new_contents = {}, []
        for key, d in dados.CONTEUDOS.items():
            creator, org = self.users[d["creator"]], self._org(d["org"])
            content = existing.get((d["title"], creator.pk, org.pk if org else None))
            if content is None:
                content = Content(
                    title=d["title"],
                    creator=creator,
                    organizacao=org,
                    description=d["description"],
                    category=d["category"],
                    level=d["level"],
                    duration=d["duration"],
                    tags=d["tags"],
                    text_content="\n\n".join(d["paragraphs"]),
                    type="text",
                )
                new_contents.append(content)
            self.contents[key] = content
        Content.objects.bulk_create(new_contents)

        with_quiz = {
            q.content_id
            for q in Quiz.objects.filter(content__in=self.contents.values()).only(
                "content_id"
            )
        }
        quizzes, questions, options = [], [], []
        for key, d in dados.CONTEUDOS.items():
            content = self.contents[key]
            if not d["questions"] or content.pk in with_quiz:
                continue
            quiz = Quiz(
                title=f"Quiz: {content.title}",
                content=content,
                organizacao=content.organizacao,
            )
            quizzes.append(quiz)
            for q in d["questions"]:
                question = Question(quiz=quiz, question_text=q["question"])
                questions.append(question)
                options.extend(
                    Option(question=question, text=text, is_correct=i == q["correct"])
                    for i, text in enumerate(q["options"])
                )
        Quiz.objects.bulk_create(quizzes)
        Question.objects.bulk_create(questions)
        Option.objects.bulk_create(options)

        by_content = {
            quiz.content_id: quiz
            for quiz in Quiz.objects.filter(
                content__in=self.contents.values()
            ).prefetch_related("questions__options")
        }
        self.quizzes = {
            key: by_content[content.pk]
            for key, content in self.contents.items()
            if content.pk in by_content
        }

    def _seed_enquetes(self):
        users = list(self.users.values())
        existing = {
            (e.question, e.creator_id, e.organizacao_id): e
            for e in Enquete.objects.filter(creator__in=users)
        }
        self.enquetes = {}
        for d in dados.ENQUETES:
            creator, org = self.users[d["creator"]], self._org(d["org"])
            enquete = existing.get((d["question"], creator.pk, org.pk if org else None))
            if enquete is None:
                # Poucas enquetes: o serviço normal valida e notifica a escola.
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

    def _target(self, kind, key):
        if kind == "conteudo":
            return self.contents[key]
        if kind == "quiz":
            return self.quizzes[key]
        return self.enquetes[key]

    def _seed_trilhas(self):
        users = list(self.users.values())
        existing = {
            (t.title, t.creator_id, t.organizacao_id): t
            for t in Trilha.objects.filter(creator__in=users)
        }
        new_trilhas, new_items, self.trilhas = [], [], []
        for d in dados.TRILHAS:
            creator, org = self.users[d["creator"]], self._org(d["org"])
            trilha = existing.get((d["title"], creator.pk, org.pk if org else None))
            if trilha is None:
                trilha = Trilha(
                    title=d["title"],
                    creator=creator,
                    organizacao=org,
                    headline=d["headline"],
                    subject=d["subject"],
                    year=d["year"],
                    semester=d["semester"],
                    is_sequential=d["is_sequential"],
                )
                new_trilhas.append(trilha)
                for order, (kind, key) in enumerate(d["items"], start=1):
                    target = self._target(kind, key)
                    # Mesma regra do `resolve_target`: o alvo é do contexto da trilha.
                    if target.organizacao_id != trilha.organizacao_id:
                        raise CommandError(f"Passo fora do contexto em {d['title']}.")
                    new_items.append(
                        TrilhaItem(
                            trilha=trilha,
                            order=order,
                            kind=kind,
                            **{TARGET_FIELD[kind]: target},
                        )
                    )
            self.trilhas.append((d, trilha))
        Trilha.objects.bulk_create(new_trilhas)
        TrilhaItem.objects.bulk_create(new_items)
        for trilha in new_trilhas:
            # Publicação pelo serviço: valida os passos e notifica os alunos.
            trilha_services.publish_trilha(trilha)

        items = TrilhaItem.objects.filter(
            trilha__in=[t for _, t in self.trilhas]
        ).order_by("order")
        self.items_by_trilha = {}
        for item in items:
            self.items_by_trilha.setdefault(item.trilha_id, []).append(item)

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

    def _progress_rows(self, items_by_ctx, key, user, submission=None, stars=None):
        """TrilhaProgresso concluído para os itens (publicados, mesmo contexto)."""
        return [
            TrilhaProgresso(
                user=user,
                item_id=item_id,
                state="concluido",
                completed_at=self.now,
                submission=submission,
                stars=stars,
            )
            for item_id in items_by_ctx.get(key, ())
        ]

    def _published_items(self, kind, field, targets):
        """
        Itens `kind` de trilhas publicadas que apontam para `targets`, por
        (alvo, contexto), como em `on_quiz_submitted`/`on_enquete_voted`.
        """
        index = {}
        rows = TrilhaItem.objects.filter(
            kind=kind,
            trilha__is_published=True,
            **{f"{field}__in": targets},
        ).values_list("pk", f"{field}_id", "trilha__organizacao_id")
        for item_id, target_id, org_id in rows:
            index.setdefault((target_id, org_id), []).append(item_id)
        return index

    def _seed_submissions(self):
        """
        Mesmas regras da `QuizSubmissionView`, em lote: XP pela
        `quiz_submission_xp` e pelo ledger (`record_xp_many`), workspace = o
        contexto do quiz, e o progresso de `on_quiz_submitted` (estrelas por
        `stars_for`). Uma submissão por (aluno, quiz), por isso é a 1.ª tentativa.
        """
        student_keys = {self.users[k].pk: k for k in STUDENT_KEYS}
        done = set(
            QuizSubmission.objects.filter(
                quiz__in=self.quizzes.values(), user__in=self.users.values()
            ).values_list("user_id", "quiz_id")
        )
        quiz_items = self._published_items("quiz", "quiz", list(self.quizzes.values()))

        planned = []
        for content_key, d in dados.CONTEUDOS.items():
            quiz = self.quizzes.get(content_key)
            if quiz is None:
                continue
            questions = list(quiz.questions.all())
            for user in self._eligible_students(d["org"]):
                key = student_keys[user.pk]
                rng = random.Random(f"{key}:{content_key}")
                if rng.random() > 0.75 or (user.pk, quiz.pk) in done:
                    continue
                picks = []
                for question in questions:
                    options = list(question.options.all())
                    correct = [o for o in options if o.is_correct]
                    wrong = [o for o in options if not o.is_correct]
                    picks.append(
                        correct[0]
                        if rng.random() < dados.APTIDAO[key] or not wrong
                        else rng.choice(wrong)
                    )
                planned.append((user, quiz, questions, picks))

        total = len(planned)
        self.stdout.write(f"Submissões 0/{total}…")
        for start in range(0, total, SUBMISSION_BATCH):
            batch = planned[start : start + SUBMISSION_BATCH]
            submissions = []
            for user, quiz, questions, picks in batch:
                correct_count = sum(1 for o in picks if o.is_correct)
                xp = quiz_submission_xp(correct_count, attempt=1)
                submissions.append(
                    QuizSubmission(
                        user=user,
                        quiz=quiz,
                        attempt=1,
                        score=xp,
                        xp_awarded=xp,
                        correct_count=correct_count,
                        total_questions=len(questions),
                        organizacao_id=quiz.organizacao_id,
                    )
                )
            QuizSubmission.objects.bulk_create(submissions)
            if any(s.pk is None for s in submissions):
                ids = {
                    (u, q): pk
                    for u, q, pk in QuizSubmission.objects.filter(
                        quiz__in={s.quiz_id for s in submissions},
                        user__in={s.user_id for s in submissions},
                        attempt=1,
                    ).values_list("user_id", "quiz_id", "pk")
                }
                for s in submissions:
                    s.pk = s.id = ids[(s.user_id, s.quiz_id)]

            answers, grants, progress = [], [], []
            for submission, (user, quiz, questions, picks) in zip(submissions, batch):
                answers.extend(
                    QuizAnswer(submission=submission, question=q, selected_option=o)
                    for q, o in zip(questions, picks)
                )
                grants.append(
                    {
                        "user": user,
                        "amount": submission.xp_awarded,
                        "source_type": XPEvent.SOURCE_QUIZ_SUBMISSION,
                        "source_id": submission.pk,
                        "organizacao": quiz.organizacao,
                    }
                )
                progress.extend(
                    self._progress_rows(
                        quiz_items,
                        (quiz.pk, quiz.organizacao_id),
                        user,
                        submission=submission,
                        stars=trilha_services.stars_for(
                            submission.correct_count, submission.total_questions
                        ),
                    )
                )
            QuizAnswer.objects.bulk_create(answers)
            record_xp_many(grants)
            TrilhaProgresso.objects.bulk_create(progress, ignore_conflicts=True)
            self.stdout.write(f"Submissões {start + len(batch)}/{total}…")
        self.stdout.write("Submissões… ok")

    def _seed_content_progress(self):
        content_items = {
            item.pk
            for _, trilha in self.trilhas
            for item in self.items_by_trilha.get(trilha.pk, [])
            if item.kind == "conteudo"
        }
        existing = {
            (p.user_id, p.item_id): p
            for p in TrilhaProgresso.objects.filter(item_id__in=content_items)
        }
        new, to_complete = [], []
        for d, trilha in self.trilhas:
            for user in self._eligible_students(d["org"]):
                rng = random.Random(f"{user.email}:{d['key']}")
                for item in self.items_by_trilha.get(trilha.pk, []):
                    if item.kind != "conteudo" or rng.random() >= 0.6:
                        continue
                    progress = existing.get((user.pk, item.pk))
                    if progress is None:
                        new.append(
                            TrilhaProgresso(
                                user=user,
                                item=item,
                                state="concluido",
                                completed_at=self.now,
                            )
                        )
                    elif progress.state != "concluido":
                        progress.state = "concluido"
                        progress.completed_at = progress.completed_at or self.now
                        to_complete.append(progress)
        TrilhaProgresso.objects.bulk_create(new, ignore_conflicts=True)
        TrilhaProgresso.objects.bulk_update(to_complete, ["state", "completed_at"])

    def _seed_votes(self):
        """
        Mesmas regras de `cast_vote`, em lote: um voto por pessoa, exibição
        `respondida`, XP (`ENQUETE_VOTE_XP`) no ledger, progresso dos passos
        `enquete` e fecho ao atingir `sample_target`.
        """
        enquetes = {
            e.pk: e
            for e in Enquete.objects.filter(
                pk__in=[e.pk for e in self.enquetes.values()]
            ).prefetch_related("options")
        }
        voted = set(
            EnqueteVoto.objects.filter(enquete__in=enquetes.values()).values_list(
                "enquete_id", "user_id"
            )
        )
        vote_counts = {}
        for enquete_id, _ in voted:
            vote_counts[enquete_id] = vote_counts.get(enquete_id, 0) + 1
        years = {
            (self.users[u].pk, self.orgs[o].pk): year
            for u, o, _, year, *_ in dados.MEMBROS
        }
        enquete_items = self._published_items("enquete", "enquete", list(enquetes))

        votes, grants, progress, to_close = [], [], [], []
        for d in dados.ENQUETES:
            enquete = enquetes[self.enquetes[d["key"]].pk]
            options = list(enquete.options.all())
            count = vote_counts.get(enquete.pk, 0)
            for user in self._members_of(d["org"]):
                if enquete.state != Enquete.STATE_PUBLISHED:
                    break
                rng = random.Random(f"{user.email}:{d['key']}")
                if rng.random() > 0.85 or (enquete.pk, user.pk) in voted:
                    continue
                # Preferência ligeira pelas primeiras opções, para os
                # resultados não ficarem uniformes.
                weights = [len(options) - i for i in range(len(options))]
                voto = EnqueteVoto(
                    enquete=enquete,
                    opcao=rng.choices(options, weights=weights)[0],
                    user=user,
                    year_snapshot=years.get((user.pk, enquete.organizacao_id), ""),
                )
                votes.append(voto)
                grants.append(
                    {
                        "user": user,
                        "amount": ENQUETE_VOTE_XP,
                        "source_type": XPEvent.SOURCE_ENQUETE_VOTO,
                        "source_id": voto.pk,
                        "organizacao": enquete.organizacao,
                    }
                )
                progress.extend(
                    self._progress_rows(
                        enquete_items, (enquete.pk, enquete.organizacao_id), user
                    )
                )
                count += 1
                if count >= enquete.sample_target:
                    enquete.state = Enquete.STATE_CLOSED
                    enquete.closed_at = self.now
                    to_close.append(enquete)

        EnqueteVoto.objects.bulk_create(votes)
        voters = {(v.enquete_id, v.user_id) for v in votes}
        shown = {
            (x.enquete_id, x.user_id): x
            for x in EnqueteExibicao.objects.filter(
                enquete__in=enquetes.values(), user__in=self.users.values()
            )
        }
        to_answer = []
        for pair in voters & set(shown):
            shown[pair].outcome = "respondida"
            to_answer.append(shown[pair])
        EnqueteExibicao.objects.bulk_update(to_answer, ["outcome"])
        EnqueteExibicao.objects.bulk_create(
            [
                EnqueteExibicao(enquete_id=e, user_id=u, outcome="respondida")
                for e, u in voters - set(shown)
            ]
        )
        record_xp_many(grants)
        TrilhaProgresso.objects.bulk_create(progress, ignore_conflicts=True)
        Enquete.objects.bulk_update(to_close, ["state", "closed_at"])

        for d in dados.ENQUETES:
            enquete = enquetes[self.enquetes[d["key"]].pk]
            if d["close"] and enquete.state == Enquete.STATE_PUBLISHED:
                enquete_services.close(enquete)

    def _seed_marketplace_visits(self):
        """Como `record_marketplace_visit`: uma linha por escola de origem."""
        rows = []
        for user_key in sorted({m[0] for m in dados.MEMBROS if m[2] == "student"}):
            user = self.users[user_key]
            if random.Random(f"{user.email}:visita").random() >= 0.6:
                continue
            rows.extend(
                ConversaoMarketplace(user=user, organizacao=self.orgs[org_key])
                for u, org_key, *_ in dados.MEMBROS
                if u == user_key
            )
        ConversaoMarketplace.objects.bulk_create(rows, ignore_conflicts=True)

    def _print_summary(self, credenciais, source):
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
        if source == "set":
            out.write(
                f"{len(novas)} contas com a password escolhida em --set-password:"
            )
        elif source == "env":
            out.write(f"{len(novas)} contas com a password definida em {PASSWORD_ENV}:")
        else:
            out.write("Credenciais (mostradas só agora; guarde-as num local seguro):")
        width = max(len(c[0]) for c in novas)
        for email, papel, password in novas:
            # Uma password escolhida (opção ou variável) nunca é impressa.
            shown = "" if source else password
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
