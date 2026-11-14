from .models import XPEvent

# D12: XP por resposta certa num quiz, concedido só na 1.ª tentativa.
QUIZ_XP_PER_CORRECT = 10


def quiz_submission_xp(correct_count, attempt):
    """XP de uma submissão de quiz. Regra única (view e seed_demo)."""
    return correct_count * QUIZ_XP_PER_CORRECT if attempt == 1 else 0


def record_xp(*, user, amount, source_type, source_id, organizacao=None):
    """
    Regista uma concessão de XP no ledger. Idempotente por (source_type,
    source_id). Não regista concessões de 0 XP. Devolve o evento ou None.
    """
    if amount <= 0:
        return None
    event, _ = XPEvent.objects.get_or_create(
        source_type=source_type,
        source_id=str(source_id),
        defaults={"user": user, "organizacao": organizacao, "amount": amount},
    )
    return event


def record_xp_many(grants):
    """
    Versão em lote de `record_xp`, com as mesmas regras: ignora concessões de
    0 XP e é idempotente por (source_type, source_id). `grants` é uma lista de
    dicts com os argumentos de `record_xp`. Uma única consulta. Devolve o
    número de concessões consideradas.
    """
    events = [
        XPEvent(
            user=grant["user"],
            organizacao=grant.get("organizacao"),
            source_type=grant["source_type"],
            source_id=str(grant["source_id"]),
            amount=grant["amount"],
        )
        for grant in grants
        if grant["amount"] > 0
    ]
    XPEvent.objects.bulk_create(events, ignore_conflicts=True)
    return len(events)
