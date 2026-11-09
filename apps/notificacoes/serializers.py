from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Notificacao


class NotificationTargetSerializer(serializers.Serializer):
    kind = serializers.CharField()
    id = serializers.UUIDField()


class NotificationSerializer(serializers.ModelSerializer):
    """Forma de `AppNotification` (sem `icon` e `action`, derivados no frontend)."""

    at = serializers.DateTimeField(source="created_at", read_only=True)
    read = serializers.SerializerMethodField()
    target = serializers.SerializerMethodField()

    class Meta:
        model = Notificacao
        fields = ("id", "category", "tone", "title", "body", "at", "read", "target")

    def get_read(self, obj) -> bool:
        return obj.read_at is not None

    @extend_schema_field(NotificationTargetSerializer(allow_null=True))
    def get_target(self, obj):
        if not obj.target_type or obj.target_id is None:
            return None
        return {"kind": obj.target_type, "id": str(obj.target_id)}


class UnreadCountSerializer(serializers.Serializer):
    count = serializers.IntegerField()


class ReadAllSerializer(serializers.Serializer):
    updated = serializers.IntegerField()
