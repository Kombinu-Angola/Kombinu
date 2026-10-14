from .models import XPEvent


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
