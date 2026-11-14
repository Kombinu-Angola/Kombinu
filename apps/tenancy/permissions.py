from rest_framework.permissions import BasePermission

from .scoping import resolve_workspace
from .services import is_org_admin


class IsWorkspaceAdmin(BasePermission):
    """Admin activo da organização do `X-Workspace` (o marketplace não tem)."""

    message = "Só um admin desta organização pode gerir membros."

    def has_permission(self, request, view):
        return is_org_admin(request.user, resolve_workspace(request))
