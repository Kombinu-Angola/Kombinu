from collections import defaultdict

from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from apps.rankings.models import XPEvent
from apps.rankings.services import record_xp
from apps.tenancy.models import Membership

from .models import Enquete, EnqueteExibicao, EnqueteOpcao, EnqueteVoto

# D13: XP simbólico por voto. Valor a confirmar pelo CTO (sugestão: 5).
ENQUETE_VOTE_XP = 5
NO_YEAR_LABEL = "Sem ano"


class EnqueteError(Exception):
    """Erro de regra de negócio; `code` mapeia para o HTTP status na view."""

    def __init__(self, message, code="invalid"):
        super().__init__(message)
        self.code = code


def create_enquete(*, creator, organizacao, data):
    with transaction.atomic():
        enquete = Enquete.objects.create(
            organizacao=organizacao,
            creator=creator,
            kind=data["kind"],
            question=data["question"],
            decision=data["decision"],
            faculty=data.get("faculty", ""),
            subject=data.get("subject", ""),
            trigger=data["trigger"],
            sample_target=data["sample_target"],
            segment_size=data.get("segment_size"),
            state="activa",
        )
        for index, label in enumerate(data["options"]):
            EnqueteOpcao.objects.create(
                enquete=enquete,
                label=label,
                order=index,
                # escala: valor numérico 1..n para permitir médias no futuro
                value=index + 1 if data["kind"] == "escala" else None,
            )
    return enquete


def _year_for(user, organizacao):
    if organizacao is None:
        return ""
    membership = Membership.objects.filter(
        user=user, organizacao=organizacao, is_active=True
    ).first()
    return membership.academic_year if membership else ""


def cast_vote(*, user, enquete, opcao_id, organizacao):
    """
    Regista o voto, a exibição `respondida`, o XP (D13) e fecha a enquete ao
    atingir `sample_target`. Um voto por utilizador (unique enquete+user).
    """
    if enquete.state != "activa":
        raise EnqueteError("Esta enquete não está activa.", code="closed")

    try:
        opcao = enquete.options.get(pk=opcao_id)
    except EnqueteOpcao.DoesNotExist:
        raise EnqueteError("Opção inválida para esta enquete.", code="invalid")

    try:
        with transaction.atomic():
            voto = EnqueteVoto.objects.create(
                enquete=enquete,
                opcao=opcao,
                user=user,
                year_snapshot=_year_for(user, organizacao),
            )
            EnqueteExibicao.objects.update_or_create(
                enquete=enquete, user=user, defaults={"outcome": "respondida"}
            )
            record_xp(
                user=user,
                amount=ENQUETE_VOTE_XP,
                source_type=XPEvent.SOURCE_ENQUETE_VOTO,
                source_id=voto.pk,
                organizacao=organizacao,
            )
            if enquete.votes.count() >= enquete.sample_target:
                enquete.state = "encerrada"
                enquete.closed_at = timezone.now()
                enquete.save(update_fields=["state", "closed_at"])
    except IntegrityError:
        raise EnqueteError("Já votaste nesta enquete.", code="duplicate")
    return voto


def mark_shown(*, user, enquete):
    exibicao, _ = EnqueteExibicao.objects.get_or_create(
        enquete=enquete, user=user, defaults={"outcome": "vista"}
    )
    return exibicao


def dismiss(*, user, enquete):
    exibicao, created = EnqueteExibicao.objects.get_or_create(
        enquete=enquete, user=user, defaults={"outcome": "dispensada"}
    )
    # Quem já votou não passa a "dispensada".
    if not created and exibicao.outcome == "vista":
        exibicao.outcome = "dispensada"
        exibicao.save(update_fields=["outcome", "updated_at"])
    return exibicao


def _pct(part, whole):
    return round(100.0 * part / whole, 1) if whole else 0


def compute_results(enquete):
    """
    Agregação para SurveyResult. Percentagens em 0–100 (D10). Nunca devolve
    identidade de votantes (D9).
    """
    options = list(enquete.options.all())  # ordenadas por `order`
    votes = list(enquete.votes.values_list("opcao_id", "year_snapshot"))
    answers = len(votes)

    per_option = defaultdict(int)
    per_year = defaultdict(lambda: defaultdict(int))
    for opcao_id, year in votes:
        per_option[opcao_id] += 1
        per_year[year or NO_YEAR_LABEL][opcao_id] += 1

    labels = {o.pk: o.label for o in options}
    order = {o.pk: o.order for o in options}

    distribution = [
        {"label": o.label, "value": _pct(per_option[o.pk], answers)} for o in options
    ]

    by_year = []
    for year in sorted(per_year):
        counts = per_year[year]
        year_answers = sum(counts.values())
        top_id = sorted(counts, key=lambda pk: (-counts[pk], order[pk]))[0]
        by_year.append(
            {
                "year": year,
                "answers": year_answers,
                "topChoice": labels[top_id],
                "share": _pct(counts[top_id], year_answers),
            }
        )

    exib = dict(
        enquete.exibicoes.values("outcome")
        .annotate(n=Count("id"))
        .values_list("outcome", "n")
    )
    return {
        "question": enquete.question,
        "decision": enquete.decision,
        "subject": enquete.subject,
        "closedAt": enquete.closed_at.isoformat() if enquete.closed_at else None,
        "answers": answers,
        "dismissed": exib.get("dispensada", 0),
        "shown": sum(exib.values()),
        "distribution": distribution,
        "byYear": by_year,
    }
