"""
Ponto único de scoping por contexto activo (workspace) — SLA §8.3.

O contexto activo vem do header `X-Workspace`:
  - ausente / vazio / "marketplace"  -> marketplace (organizacao = NULL)
  - UUID de uma Organizacao          -> esse workspace, se o utilizador tiver
                                        Membership activa nela

Qualquer view que devolva ou crie dados de conteúdo/quiz/submissão deve usar
`WorkspaceScopedMixin.scope()` em vez de filtrar por conta própria.
"""
import uuid

from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Membership, Organizacao

WORKSPACE_HEADER = "HTTP_X_WORKSPACE"
MARKETPLACE_VALUES = {"", "marketplace"}
CREATOR_ROLES = {"teacher", "admin"}


def resolve_workspace(request):
    """
    Devolve a Organizacao activa ou None (marketplace). Valida a pertença.

    Levanta ValidationError (400) para valor inválido e PermissionDenied (403)
    se o utilizador não tem Membership activa — inclusive quando a organização
    não existe, para não revelar quais organizações existem.
    """
    cached = getattr(request, "_workspace_resolved", None)
    if cached is not None:
        return cached[0]

    raw = (request.META.get(WORKSPACE_HEADER) or "").strip()
    if raw.lower() in MARKETPLACE_VALUES:
        organizacao = None
    else:
        try:
            org_id = uuid.UUID(raw)
        except ValueError:
            raise ValidationError({"workspace": "Identificador de workspace inválido."})

        membership = (
            Membership.objects.select_related("organizacao")
            .filter(
                user=request.user,
                organizacao_id=org_id,
                is_active=True,
                organizacao__is_active=True,
            )
            .first()
        )
        if membership is None:
            raise PermissionDenied("Sem acesso a este workspace.")
        organizacao = membership.organizacao

    request._workspace_resolved = (organizacao,)
    return organizacao


def can_create_in(user, organizacao):
    """Quem pode criar conteúdo/quizzes no contexto dado."""
    if organizacao is None:
        return user.user_type == "creator"
    return Membership.objects.filter(
        user=user,
        organizacao=organizacao,
        is_active=True,
        role__in=CREATOR_ROLES,
    ).exists()


class WorkspaceScopedMixin:
    """Mixin para views DRF: expõe `workspace` e `scope(queryset)`."""

    @property
    def workspace(self):
        return resolve_workspace(self.request)

    def scope(self, queryset):
        return queryset.for_context(self.workspace)
