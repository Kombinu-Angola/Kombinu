"""
Geração de notificações (B3). Síncrona, dentro da transacção de quem publica:
serve para o MVP (um INSERT em lote por evento). Se as escolas crescerem,
passa para uma fila. No marketplace não há difusão (seria notificar todos os
utilizadores).
"""

from apps.tenancy.models import Membership

from .models import Notificacao


def notify_members(
    *,
    organizacao,
    source_key,
    category,
    title,
    body="",
    tone="informativo",
    target_type="",
    target_id=None,
    roles=None,
    exclude_user=None,
):
    """
    Cria uma notificação por membro activo de `organizacao` (opcionalmente só
    com os papéis `roles`). Idempotente por (user, source_key). Devolve o
    número de destinatários considerados.
    """
    if organizacao is None:
        return 0
    members = Membership.objects.filter(organizacao=organizacao, is_active=True)
    if roles:
        members = members.filter(role__in=roles)
    if exclude_user is not None:
        members = members.exclude(user=exclude_user)
    user_ids = list(members.values_list("user_id", flat=True).distinct())
    Notificacao.objects.bulk_create(
        [
            Notificacao(
                user_id=user_id,
                organizacao=organizacao,
                category=category,
                tone=tone,
                title=title,
                body=body,
                target_type=target_type,
                target_id=target_id,
                source_key=source_key,
            )
            for user_id in user_ids
        ],
        ignore_conflicts=True,
    )
    return len(user_ids)


def notify_trilha_published(trilha):
    """Trilha publicada numa escola: avisa os alunos activos, excepto o criador."""
    return notify_members(
        organizacao=trilha.organizacao,
        source_key=f"trilha_publicada:{trilha.pk}",
        category="conteudo",
        title=f"Nova trilha: {trilha.title}"[:200],
        body=trilha.headline or trilha.subject,
        target_type="trilha",
        target_id=trilha.pk,
        roles=["student"],
        exclude_user=trilha.creator,
    )


def notify_enquete_published(enquete):
    """Enquete publicada numa escola: avisa todos os membros activos, excepto o criador."""
    return notify_members(
        organizacao=enquete.organizacao,
        source_key=f"enquete_publicada:{enquete.pk}",
        category="conteudo",
        title="Nova enquete para responder",
        body=enquete.question[:500],
        target_type="enquete",
        target_id=enquete.pk,
        exclude_user=enquete.creator,
    )
