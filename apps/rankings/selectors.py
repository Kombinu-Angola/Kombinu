"""
Leitura de XP e ranking. Fonte única: o ledger `XPEvent` (nunca
`QuizSubmission.score`). Tudo calculado na base de dados.

`organizacao` segue a convenção da tenancy: `None` = marketplace, uma
`Organizacao` = esse workspace. `ALL` soma todos os contextos (carteira
digital única do utilizador, SLA §2 Ponto Cego 1).
"""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.db.models import F, Sum, Window
from django.db.models.functions import Rank, TruncDate
from django.utils import timezone

from .models import XPEvent

ALL = object()


def _events(organizacao):
    qs = XPEvent.objects.all()
    if organizacao is ALL:
        return qs
    return qs.filter(organizacao=organizacao)


def xp_total(user, organizacao=ALL):
    """XP do utilizador num contexto, ou na carteira global com `ALL`."""
    return _events(organizacao).filter(user=user).aggregate(t=Sum("amount"))["t"] or 0


def level_for(total_xp):
    """Regra única de nível: 100 XP por nível, começando em 1."""
    return (total_xp // 100) + 1


def ranking_queryset(organizacao):
    """
    Uma linha por utilizador com XP no contexto, ordenada por XP desc. A
    posição vem de RANK() calculado na BD: empates partilham posição.
    Índice usado: XPEvent(organizacao, user).
    """
    return (
        _events(organizacao)
        .values("user_id", "user__first_name", "user__last_name")
        .annotate(total_score=Sum("amount"))
        .annotate(
            position=Window(expression=Rank(), order_by=F("total_score").desc())
        )
        .order_by("-total_score", "user_id")
    )


def user_standing(user, organizacao):
    """
    Posição e total do utilizador, coerentes com RANK(): 1 + nº de
    utilizadores com mais XP. Uma agregação com HAVING, sem trazer a lista.
    """
    total = xp_total(user, organizacao)
    ahead = (
        _events(organizacao)
        .values("user_id")
        .annotate(t=Sum("amount"))
        .filter(t__gt=total)
        .count()
    )
    return {"position": ahead + 1, "total_score": total}


# --- Gamificação do próprio utilizador (K4) -----------------------------------

STREAK_TZ = ZoneInfo("Africa/Luanda")
ONE_DAY = timedelta(days=1)


def activity_days(user):
    """Dias distintos (data em Africa/Luanda) com XP na carteira global, por ordem."""
    return list(
        XPEvent.objects.filter(user=user)
        .annotate(day=TruncDate("created_at", tzinfo=STREAK_TZ))
        .values_list("day", flat=True)
        .distinct()
        .order_by("day")
    )


def streaks(days, today):
    """
    (streak, best_streak) a partir de dias ordenados e sem repetidos. A ofensiva
    actual termina hoje ou ontem: quem ainda não fez nada hoje não a perde. Se o
    último dia com XP for anterior a ontem, vale 0.
    """
    best = run = 0
    previous = None
    for day in days:
        run = run + 1 if previous is not None and day - previous == ONE_DAY else 1
        best = max(best, run)
        previous = day
    current = run if previous is not None and today - previous <= ONE_DAY else 0
    return current, best


def gamification_summary(user, workspace_events):
    """
    Resumo para `GET /api/rankings/me/`. `workspace_events` é o queryset de
    `XPEvent` já limitado ao workspace activo (`for_context`), vindo da view.
    """
    total = xp_total(user)
    days = activity_days(user)
    streak, best_streak = streaks(days, timezone.localdate(timezone=STREAK_TZ))
    return {
        "xp_total": total,
        "xp_workspace": workspace_events.filter(user=user).aggregate(t=Sum("amount"))[
            "t"
        ]
        or 0,
        "level": level_for(total),
        "streak": streak,
        "best_streak": best_streak,
        "last_activity_date": days[-1] if days else None,
    }
