from rest_framework.permissions import BasePermission, IsAuthenticated


class IsCreator(IsAuthenticated):
    """
    Permissão customizada para permitir apenas usuários do tipo 'creator'.
    """

    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.user.user_type == "creator"
        )


class IsContentOwner(BasePermission):
    """Só o criador do conteúdo pode alterá-lo ou apagá-lo."""

    def has_object_permission(self, request, view, obj):
        return obj.creator_id == request.user.pk
