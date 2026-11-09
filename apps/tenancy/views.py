from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from . import services
from .models import Membership
from .permissions import IsWorkspaceAdmin
from .scoping import WorkspaceScopedMixin
from .serializers import (
    MemberSerializer,
    PasswordResetResponseSerializer,
    ProvisionBatchSerializer,
    ProvisionDryRunResponseSerializer,
    ProvisionErrorResponseSerializer,
    ProvisionResponseSerializer,
)


class ProvisioningRateThrottle(UserRateThrottle):
    scope = "provisioning"


class ProvisionMembersView(WorkspaceScopedMixin, APIView):
    """Criação de contas em lote pelo admin da organização activa (`X-Workspace`)."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ProvisioningRateThrottle]

    @extend_schema(
        summary="Provisionar membros em lote",
        description=(
            "Só um admin da organização do `X-Workspace` activo. Tudo ou nada: "
            "se alguma linha falhar, nada é criado e a resposta traz os erros "
            "por linha. Com `dry_run`, só valida. As passwords temporárias "
            "(válidas 7 dias, troca obrigatória no 1.º acesso) só aparecem "
            "nesta resposta."
        ),
        request=ProvisionBatchSerializer,
        responses={
            201: ProvisionResponseSerializer,
            200: ProvisionDryRunResponseSerializer,
            400: ProvisionErrorResponseSerializer,
            403: OpenApiResponse(description="Sem papel de admin nesta organização."),
            409: OpenApiResponse(description="Conflito concorrente; repetir o pedido."),
        },
        tags=["Organizações"],
    )
    def post(self, request):
        organizacao = self.workspace
        if not services.is_org_admin(request.user, organizacao):
            raise PermissionDenied("Só um admin desta organização pode provisionar membros.")

        serializer = ProvisionBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rows = serializer.validated_data["rows"]

        if serializer.validated_data["dry_run"]:
            errors = services.validate_batch(organizacao, rows)
            return Response({"dry_run": True, "rows": len(rows), "errors": errors})

        try:
            lote, accounts = services.provision_batch(
                organizacao=organizacao, admin=request.user, rows=rows
            )
        except services.ProvisioningError as exc:
            return Response({"errors": exc.errors}, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError:
            return Response(
                {"error": "Conflito ao criar as contas. Repita o pedido."},
                status=status.HTTP_409_CONFLICT,
            )

        response = Response(
            {"lote_id": lote.id, "created": len(accounts), "accounts": accounts},
            status=status.HTTP_201_CREATED,
        )
        # Contém passwords temporárias: nunca guardar em cache intermédia.
        response["Cache-Control"] = "no-store"
        return response


class MemberListView(WorkspaceScopedMixin, generics.ListAPIView):
    """Membros da organização do `X-Workspace`, só para o admin dela."""

    serializer_class = MemberSerializer
    permission_classes = [IsAuthenticated, IsWorkspaceAdmin]

    @extend_schema(
        summary="Listar membros da organização",
        parameters=[
            OpenApiParameter("role", str, enum=["student", "teacher", "admin"]),
            OpenApiParameter("is_active", bool),
            OpenApiParameter("search", str, description="Número de aluno ou nome."),
        ],
        tags=["Organizações"],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = (
            Membership.objects.filter(organizacao=self.workspace)
            .select_related("user")
            .order_by("joined_at", "id")
        )
        params = self.request.query_params
        if params.get("role"):
            qs = qs.filter(role=params["role"])
        if params.get("is_active") in ("true", "false"):
            qs = qs.filter(is_active=params["is_active"] == "true")
        search = (params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(student_code__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
            )
        return qs


class _MemberActionView(WorkspaceScopedMixin, APIView):
    permission_classes = [IsAuthenticated, IsWorkspaceAdmin]

    def get_membership(self, membership_id):
        # Pertença de outra organização → 404 (não revela que existe).
        return get_object_or_404(
            Membership.objects.select_related("user", "organizacao"),
            pk=membership_id,
            organizacao=self.workspace,
        )

    @staticmethod
    def _error(exc):
        return Response({"error": str(exc)}, status=exc.status)


class MemberDeactivateView(_MemberActionView):
    @extend_schema(
        summary="Desactivar membro",
        description=(
            "A conta e o XP mantêm-se (D13); a pessoa perde o acesso a esta "
            "organização. Um admin não se desactiva a si próprio e a "
            "organização mantém sempre um admin activo."
        ),
        request=None,
        responses={200: MemberSerializer, 400: OpenApiResponse(description="Regra do admin.")},
        tags=["Organizações"],
    )
    def post(self, request, id):
        membership = self.get_membership(id)
        try:
            membership = services.deactivate_member(admin=request.user, membership=membership)
        except services.MemberActionError as exc:
            return self._error(exc)
        return Response(MemberSerializer(membership).data)


class MemberReactivateView(_MemberActionView):
    @extend_schema(
        summary="Reactivar membro",
        request=None,
        responses={200: MemberSerializer},
        tags=["Organizações"],
    )
    def post(self, request, id):
        membership = services.reactivate_member(
            admin=request.user, membership=self.get_membership(id)
        )
        return Response(MemberSerializer(membership).data)


class MemberPasswordResetView(_MemberActionView):
    throttle_classes = [ProvisioningRateThrottle]

    @extend_schema(
        summary="Reset da password de um membro",
        description=(
            "Gera uma password temporária nova (válida 7 dias, troca obrigatória) "
            "e revoga as sessões da conta. Só para contas provisionadas por esta "
            "organização e sem pertença a outra. A password só aparece nesta resposta."
        ),
        request=None,
        responses={
            200: PasswordResetResponseSerializer,
            400: OpenApiResponse(description="O admin não pode fazer reset a si próprio."),
            403: OpenApiResponse(description="Conta não gerida só por esta organização."),
        },
        tags=["Organizações"],
    )
    def post(self, request, id):
        membership = self.get_membership(id)
        try:
            password, expires_at = services.reset_member_password(
                admin=request.user, membership=membership
            )
        except services.MemberActionError as exc:
            return self._error(exc)
        response = Response(
            {
                "membership_id": membership.id,
                "student_code": membership.student_code,
                "temporary_password": password,
                "expires_at": expires_at,
            }
        )
        response["Cache-Control"] = "no-store"
        return response


class MarketplaceVisitRateThrottle(UserRateThrottle):
    scope = "marketplace_visit"


class MarketplaceVisitView(APIView):
    """
    Chamado pelo seletor de workspace ao mudar para o marketplace (B4). Regista
    a conversão B2B -> B2C por escola de origem. Responde sempre 204, incluindo
    para quem não pertence a nenhuma escola, para não revelar nada.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [MarketplaceVisitRateThrottle]

    @extend_schema(
        summary="Registar entrada no marketplace",
        request=None,
        responses={204: OpenApiResponse(description="Registado (ou nada a registar).")},
    )
    def post(self, request):
        services.record_marketplace_visit(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
