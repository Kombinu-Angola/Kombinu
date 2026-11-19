"""Perfil académico e onboarding (K1)."""

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Instituicao, PerfilEstudante
from .perfil_serializers import (
    InstituicaoSerializer,
    PerfilSerializer,
    PerfilUpdateSerializer,
)


def _perfil_of(user, for_update=False):
    """Perfil do próprio utilizador, criado no primeiro acesso."""
    PerfilEstudante.objects.get_or_create(user=user)
    queryset = PerfilEstudante.objects.select_related(
        "user", "instituicao", "cadeira_foco"
    )
    if for_update:
        queryset = queryset.select_for_update()
    return queryset.get(user=user)


class MeView(APIView):
    """
    Perfil académico de quem faz o pedido. Não há id no URL: um utilizador só
    lê e altera o seu próprio perfil.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: PerfilSerializer})
    def get(self, request):
        return Response(PerfilSerializer(_perfil_of(request.user)).data)

    @extend_schema(request=PerfilUpdateSerializer, responses={200: PerfilSerializer})
    def patch(self, request):
        with transaction.atomic():
            perfil = _perfil_of(request.user, for_update=True)
            serializer = PerfilUpdateSerializer(perfil, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        return Response(PerfilSerializer(_perfil_of(request.user)).data)


class InstituicaoListView(generics.ListAPIView):
    """Catálogo de instituições, sem paginação (lista para um seletor)."""

    queryset = Instituicao.objects.all()
    serializer_class = InstituicaoSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
