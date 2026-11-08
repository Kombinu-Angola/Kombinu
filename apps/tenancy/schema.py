from drf_spectacular.openapi import AutoSchema
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter

from .scoping import WorkspaceScopedMixin

X_WORKSPACE_PARAMETER = OpenApiParameter(
    name="X-Workspace",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.HEADER,
    required=False,
    description=(
        "Contexto activo: UUID da organização (`organizacao_id` em "
        "`user.memberships`) ou `marketplace`. Ausente = marketplace. Exige "
        "Membership activa na organização: UUID inválido → 400; sem pertença "
        "→ 403; objectos de outro contexto → 404."
    ),
)


class WorkspaceAutoSchema(AutoSchema):
    """Documenta o header `X-Workspace` nas views com scoping por workspace."""

    def get_override_parameters(self):
        parameters = super().get_override_parameters()
        if isinstance(self.view, WorkspaceScopedMixin):
            parameters = [*parameters, X_WORKSPACE_PARAMETER]
        return parameters
