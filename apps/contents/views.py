from django.db.models import ProtectedError
from rest_framework import viewsets, filters, status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from apps.tenancy.scoping import WorkspaceScopedMixin, can_create_in
from .models import Content
from .serializers import ContentListSerializer, ContentSerializer
from .permissions import IsCreator, IsContentOwner


class ContentViewSet(WorkspaceScopedMixin, viewsets.ModelViewSet):
    queryset = Content.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["category", "creator"]
    search_fields = ["title", "description"]

    def get_serializer_class(self):
        if self.action == "list":
            return ContentListSerializer
        return ContentSerializer

    def get_permissions(self):
        """
        Instancia e retorna a lista de permissões que esta view requer
        """
        if self.action == "create":
            permission_classes = [IsCreator]
        elif self.action in ("update", "partial_update", "destroy"):
            permission_classes = [IsAuthenticated, IsContentOwner]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def destroy(self, request, *args, **kwargs):
        # R5: o histórico (submissões/XP) não se apaga em cascata.
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"error": "Este conteúdo já tem submissões e não pode ser apagado."},
                status=status.HTTP_409_CONFLICT,
            )

    def perform_create(self, serializer):
        if not can_create_in(self.request.user, self.workspace):
            raise PermissionDenied("Sem permissão para criar conteúdo neste workspace.")
        serializer.save(creator=self.request.user, organizacao=self.workspace)

    def get_queryset(self):
        queryset = self.scope(super().get_queryset())
        has_quiz_param = self.request.query_params.get("has_quiz", None)
        if has_quiz_param is not None:
            if has_quiz_param.lower() == "true":
                queryset = queryset.filter(quiz__isnull=False)
            elif has_quiz_param.lower() == "false":
                queryset = queryset.filter(quiz__isnull=True)
        return queryset
