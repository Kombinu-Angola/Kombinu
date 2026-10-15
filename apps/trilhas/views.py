from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy.scoping import WorkspaceScopedMixin

from . import services
from .models import Trilha, TrilhaItem
from .serializers import LearningTrailSerializer


def _visible_trilhas(view):
    """Trilhas do workspace activo: publicadas, mais os rascunhos do criador."""
    qs = view.scope(Trilha.objects.all())
    return qs.filter(Q(is_published=True) | Q(creator=view.request.user))


def _trilhas_for(view):
    items = TrilhaItem.objects.select_related("content", "quiz", "enquete").order_by(
        "order"
    )
    return (
        _visible_trilhas(view)
        .select_related("final_exam")
        .prefetch_related(Prefetch("items", queryset=items))
    )


class TrilhaListView(WorkspaceScopedMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LearningTrailSerializer

    def get_queryset(self):
        return _trilhas_for(self).order_by("-created_at")


class TrilhaDetailView(WorkspaceScopedMixin, generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LearningTrailSerializer
    lookup_field = "id"
    lookup_url_kwarg = "id"

    def get_queryset(self):
        return _trilhas_for(self)

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["id"])


class TrilhaItemCompleteView(WorkspaceScopedMixin, APIView):
    """Conclusão explícita de itens `conteudo` (quiz/enquete concluem-se sozinhos)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        qs = self.scope_items()
        item = get_object_or_404(qs, pk=id)
        if item.kind != "conteudo":
            return Response(
                {"error": "Só itens de conteúdo se concluem manualmente."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if services.item_status(item, request.user) == "bloqueado":
            return Response(
                {"error": "Conclui primeiro os passos anteriores."},
                status=status.HTTP_409_CONFLICT,
            )
        services.complete_content_item(request.user, item)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def scope_items(self):
        visible = _visible_trilhas(self).values("pk")
        return TrilhaItem.objects.select_related("trilha", "content").filter(
            trilha__in=visible
        )
