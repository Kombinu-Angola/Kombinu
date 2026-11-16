from rest_framework.permissions import BasePermission

from .scoping import can_create_in, resolve_workspace
from .services import is_org_admin


class IsWorkspaceAdmin(BasePermission):
    """Admin activo da organização do `X-Workspace` (o marketplace não tem)."""

    message = "Só um admin desta organização pode gerir membros."

    def has_permission(self, request, view):
        return is_org_admin(request.user, resolve_workspace(request))


class IsCreatorOrWorkspaceStaff(BasePermission):
    """
    Criador (`user_type` "creator") ou professor/admin activo no workspace do
    `X-Workspace` (K3). Um estudante, ou um learner sem papel, recebe 403.
    """

    message = "Só criadores, professores ou admins podem ver estas estatísticas."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.user_type == "creator":
            return True
        organizacao = resolve_workspace(request)
        return organizacao is not None and can_create_in(user, organizacao)
