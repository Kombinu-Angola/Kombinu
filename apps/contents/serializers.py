from rest_framework import serializers
from .models import Content


class CreatorSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        from apps.accounts.models import CustomUser

        model = CustomUser
        fields = ("id", "name")

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.email


class ContentSerializer(serializers.ModelSerializer):
    creator = CreatorSerializer(read_only=True)
    has_quiz = serializers.BooleanField(read_only=True)
    quiz_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Content
        fields = "__all__"
        # `organizacao` vem sempre do workspace activo (perform_create) e nunca
        # do corpo do pedido: editá-la movia o conteúdo para outro tenant.
        read_only_fields = (
            "id",
            "creator",
            "organizacao",
            "created_at",
            "has_quiz",
            "quiz_id",
        )


class ContentListSerializer(ContentSerializer):
    pass
