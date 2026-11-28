from rest_framework import serializers
from .models import Cadeira, Content


class CreatorSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        from apps.accounts.models import CustomUser

        model = CustomUser
        fields = ("id", "name")

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.email


class CadeiraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cadeira
        fields = ("id", "nome", "curso")


class CadeiraField(serializers.PrimaryKeyRelatedField):
    """
    `cadeira` nos conteúdos, quizzes e trilhas (C-K4): escreve-se por id (ou
    `null`) e lê-se como `{id, nome, curso}`. O catálogo é global, por isso
    não há validação de workspace sobre a cadeira.
    """

    default_error_messages = {
        "does_not_exist": "Cadeira não encontrada.",
        "incorrect_type": "Indica a cadeira pelo id.",
    }

    def __init__(self, **kwargs):
        if not kwargs.get("read_only"):
            kwargs.setdefault("queryset", Cadeira.objects.all())
        kwargs.setdefault("allow_null", True)
        kwargs.setdefault("required", False)
        super().__init__(**kwargs)

    def use_pk_only_optimization(self):
        return False

    def to_representation(self, value):
        return CadeiraSerializer(value).data


class ContentSerializer(serializers.ModelSerializer):
    creator = CreatorSerializer(read_only=True)
    cadeira = CadeiraField()
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
