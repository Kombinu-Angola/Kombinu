from django.db import IntegrityError
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from . import services
from .scoping import WorkspaceScopedMixin
from .serializers import (
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
