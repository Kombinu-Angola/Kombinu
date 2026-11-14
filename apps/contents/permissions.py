from rest_framework.permissions import BasePermission, IsAuthenticated

from apps.tenancy.scoping import can_create_in, resolve_workspace


class IsCreator(IsAuthenticated):
    """
    Pode criar no workspace activo (D11): no marketplace, `user_type`
    "creator"; numa organização, papel `teacher` ou `admin` na Membership.
    """

    def has_permission(self, request, view):
        return super().has_permission(request, view) and can_create_in(
            request.user, resolve_workspace(request)
        )


class IsContentOwner(BasePermission):
    """Só o criador do conteúdo pode alterá-lo ou apagá-lo."""

    def has_object_permission(self, request, view, obj):
        return obj.creator_id == request.user.pk
