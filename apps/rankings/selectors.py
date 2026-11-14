"""
Leitura de XP e ranking. Fonte única: o ledger `XPEvent` (nunca
`QuizSubmission.score`). Tudo calculado na base de dados.

`organizacao` segue a convenção da tenancy: `None` = marketplace, uma
`Organizacao` = esse workspace. `ALL` soma todos os contextos (carteira
digital única do utilizador, SLA §2 Ponto Cego 1).
"""
from django.db.models import F, Sum, Window
from django.db.models.functions import Rank

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
