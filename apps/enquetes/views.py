from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy.scoping import WorkspaceScopedMixin, can_create_in

from . import services
from .models import Enquete
from .serializers import (
    EnqueteOwnerSerializer,
    EnqueteVoterSerializer,
    SurveyDraftSerializer,
    VoteSerializer,
)

ERROR_STATUS = {
    "invalid": status.HTTP_400_BAD_REQUEST,
    "closed": status.HTTP_409_CONFLICT,
    "duplicate": status.HTTP_409_CONFLICT,
}


class _EnqueteBase(WorkspaceScopedMixin):
    permission_classes = [IsAuthenticated]

    def get_enquete(self, enquete_id):
        qs = self.scope(Enquete.objects.prefetch_related("options"))
        return get_object_or_404(qs, pk=enquete_id)


class EnqueteListCreateView(_EnqueteBase, generics.ListCreateAPIView):
    """
    GET: enquetes activas do workspace (mais as do próprio criador).
    POST: cria uma enquete a partir de SurveyDraft; fica `activa`.
    """

    def get_serializer_class(self):
        if self.request.method == "POST":
            return SurveyDraftSerializer
        return EnqueteVoterSerializer

    def get_queryset(self):
        qs = self.scope(Enquete.objects.prefetch_related("options"))
        return qs.filter(Q(state="activa") | Q(creator=self.request.user)).order_by(
            "-created_at"
        )

    def create(self, request, *args, **kwargs):
        if not can_create_in(request.user, self.workspace):
            raise PermissionDenied("Sem permissão para criar enquetes neste workspace.")
        serializer = SurveyDraftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enquete = services.create_enquete(
            creator=request.user,
            organizacao=self.workspace,
            data=serializer.validated_data,
        )
        out = EnqueteOwnerSerializer(enquete, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)


class EnqueteDetailView(_EnqueteBase, APIView):
    def get(self, request, id):
        enquete = self.get_enquete(id)
        cls = (
            EnqueteOwnerSerializer
            if enquete.creator_id == request.user.pk
            else EnqueteVoterSerializer
        )
        return Response(cls(enquete, context={"request": request}).data)


class EnqueteVoteView(_EnqueteBase, APIView):
    def post(self, request, id):
        enquete = self.get_enquete(id)
        serializer = VoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.cast_vote(
                user=request.user,
                enquete=enquete,
                opcao_id=serializer.validated_data["optionId"],
                organizacao=self.workspace,
            )
        except services.EnqueteError as exc:
            return Response({"error": str(exc)}, status=ERROR_STATUS[exc.code])
        return Response(
            {"message": "Voto registado.", "xpEarned": services.ENQUETE_VOTE_XP},
            status=status.HTTP_201_CREATED,
        )


class EnqueteShownView(_EnqueteBase, APIView):
    def post(self, request, id):
        services.mark_shown(user=request.user, enquete=self.get_enquete(id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class EnqueteDismissView(_EnqueteBase, APIView):
    def post(self, request, id):
        services.dismiss(user=request.user, enquete=self.get_enquete(id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class EnqueteResultsView(_EnqueteBase, APIView):
    """Resultados agregados (SurveyResult). Só o criador; sem identidades."""

    def get(self, request, id):
        enquete = self.get_enquete(id)
        if enquete.creator_id != request.user.pk:
            raise PermissionDenied("Só o criador vê os resultados.")
        return Response(services.compute_results(enquete))
