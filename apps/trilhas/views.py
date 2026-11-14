from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy.scoping import WorkspaceScopedMixin, can_create_in

from . import services
from .models import Trilha, TrilhaItem
from .serializers import (
    LearningTrailSerializer,
    TrilhaItemReorderSerializer,
    TrilhaItemUpdateSerializer,
    TrilhaItemWriteSerializer,
    TrilhaWriteSerializer,
)


def _visible_trilhas(view):
    """
    Trilhas do workspace activo: publicadas e não arquivadas, mais todas as do
    criador (rascunhos e arquivadas incluídos).
    """
    qs = view.scope(Trilha.objects.all())
    return qs.filter(
        Q(is_published=True, archived_at__isnull=True) | Q(creator=view.request.user)
    )


def _trilhas_for(view):
    items = TrilhaItem.objects.select_related("content", "quiz", "enquete").order_by(
        "order"
    )
    return (
        _visible_trilhas(view)
        .select_related("final_exam")
        .prefetch_related(Prefetch("items", queryset=items))
    )


def _trail_response(view, trilha_id, code=status.HTTP_200_OK):
    trilha = _trilhas_for(view).get(pk=trilha_id)
    data = LearningTrailSerializer(trilha, context={"request": view.request}).data
    return Response(data, status=code)


def _error(exc):
    return Response(exc.as_response_data(), status=exc.status)


class _AuthoringMixin(WorkspaceScopedMixin):
    """
    Autoria (B1): só o criador da trilha a altera. Uma trilha que o utilizador
    não vê (rascunho de outro, outro contexto) dá 404; uma que vê mas não é
    dele dá 403.
    """

    permission_classes = [IsAuthenticated]

    def get_own_trilha(self, trilha_id):
        trilha = get_object_or_404(_visible_trilhas(self), pk=trilha_id)
        if trilha.creator_id != self.request.user.pk:
            raise PermissionDenied("Só o criador pode alterar esta trilha.")
        return trilha


class TrilhaListView(_AuthoringMixin, generics.ListCreateAPIView):
    def get_serializer_class(self):
        if self.request.method == "POST":
            return TrilhaWriteSerializer
        return LearningTrailSerializer

    def get_queryset(self):
        return _trilhas_for(self).order_by("-created_at")

    @extend_schema(
        request=TrilhaWriteSerializer, responses={201: LearningTrailSerializer}
    )
    def post(self, request, *args, **kwargs):
        if not can_create_in(request.user, self.workspace):
            raise PermissionDenied("Sem permissão para criar trilhas neste workspace.")
        serializer = TrilhaWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        try:
            final_exam = services.resolve_final_exam(
                data.pop("finalExamId", None), self.workspace
            )
        except services.TrilhaError as exc:
            return _error(exc)
        trilha = Trilha.objects.create(
            **data,
            final_exam=final_exam,
            organizacao=self.workspace,
            creator=request.user,
            is_published=False,
        )
        return _trail_response(self, trilha.pk, status.HTTP_201_CREATED)


class TrilhaDetailView(_AuthoringMixin, generics.RetrieveAPIView):
    serializer_class = LearningTrailSerializer

    def get_queryset(self):
        return _trilhas_for(self)

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["id"])

    @extend_schema(
        request=TrilhaWriteSerializer, responses={200: LearningTrailSerializer}
    )
    def patch(self, request, id):
        trilha = self.get_own_trilha(id)
        serializer = TrilhaWriteSerializer(trilha, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        if "finalExamId" in data:
            try:
                trilha.final_exam = services.resolve_final_exam(
                    data.pop("finalExamId"), trilha.organizacao
                )
            except services.TrilhaError as exc:
                return _error(exc)
        for field, value in data.items():
            setattr(trilha, field, value)
        trilha.save()
        return _trail_response(self, trilha.pk)

    @extend_schema(responses={204: None})
    def delete(self, request, id):
        trilha = self.get_own_trilha(id)
        try:
            services.delete_trilha(trilha)
        except services.TrilhaError as exc:
            return _error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrilhaPublishView(_AuthoringMixin, APIView):
    @extend_schema(request=None, responses={200: LearningTrailSerializer})
    def post(self, request, id):
        trilha = self.get_own_trilha(id)
        try:
            services.publish_trilha(trilha)
        except services.TrilhaError as exc:
            return _error(exc)
        return _trail_response(self, trilha.pk)


class TrilhaArchiveView(_AuthoringMixin, APIView):
    archive = True

    @extend_schema(request=None, responses={200: LearningTrailSerializer})
    def post(self, request, id):
        trilha = self.get_own_trilha(id)
        services.set_archived(trilha, self.archive)
        return _trail_response(self, trilha.pk)


class TrilhaUnarchiveView(TrilhaArchiveView):
    archive = False


class TrilhaItemCreateView(_AuthoringMixin, APIView):
    @extend_schema(
        request=TrilhaItemWriteSerializer, responses={201: LearningTrailSerializer}
    )
    def post(self, request, id):
        trilha = self.get_own_trilha(id)
        serializer = TrilhaItemWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.add_item(trilha, request.user, serializer.validated_data)
        except services.TrilhaError as exc:
            return _error(exc)
        return _trail_response(self, trilha.pk, status.HTTP_201_CREATED)


class TrilhaItemDetailView(_AuthoringMixin, APIView):
    def get_item(self, id, item_id):
        trilha = self.get_own_trilha(id)
        return get_object_or_404(TrilhaItem.objects.filter(trilha=trilha), pk=item_id)

    @extend_schema(
        request=TrilhaItemUpdateSerializer, responses={200: LearningTrailSerializer}
    )
    def patch(self, request, id, item_id):
        item = self.get_item(id, item_id)
        serializer = TrilhaItemUpdateSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return _trail_response(self, item.trilha_id)

    @extend_schema(responses={204: None})
    def delete(self, request, id, item_id):
        item = self.get_item(id, item_id)
        try:
            services.remove_item(item)
        except services.TrilhaError as exc:
            return _error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrilhaItemReorderView(_AuthoringMixin, APIView):
    @extend_schema(
        request=TrilhaItemReorderSerializer, responses={200: LearningTrailSerializer}
    )
    def post(self, request, id):
        trilha = self.get_own_trilha(id)
        serializer = TrilhaItemReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.reorder_items(trilha, serializer.validated_data["itemIds"])
        except services.TrilhaError as exc:
            return _error(exc)
        return _trail_response(self, trilha.pk)


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
