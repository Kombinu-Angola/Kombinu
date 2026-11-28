"""OpenAPI do `CadeiraField`: id no pedido, `{id, nome, curso}` na resposta."""

from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from drf_spectacular.plumbing import build_basic_type
from drf_spectacular.types import OpenApiTypes


class CadeiraFieldExtension(OpenApiSerializerFieldExtension):
    target_class = "apps.contents.serializers.CadeiraField"

    def map_serializer_field(self, auto_schema, direction):
        if direction == "request":
            schema = build_basic_type(OpenApiTypes.INT)
            schema["description"] = "Id da cadeira (catálogo global) ou null."
            schema["nullable"] = True
            return schema
        from .serializers import CadeiraSerializer

        component = auto_schema.resolve_serializer(CadeiraSerializer, direction)
        return {"allOf": [component.ref], "nullable": True}
