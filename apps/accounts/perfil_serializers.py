"""Perfil académico e onboarding (K1): `GET/PATCH /api/me/`."""

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.contents.models import Cadeira

from .models import PROVINCIA_CHOICES, Instituicao, PerfilEstudante
from .serializers import UserProfileSerializer


class InstituicaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instituicao
        fields = ("id", "nome", "sigla", "provincia")


class CadeiraFocoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cadeira
        fields = ("id", "nome")


class PerfilSerializer(serializers.ModelSerializer):
    """Resposta do `GET /api/me/`. Sempre o perfil de quem faz o pedido."""

    id = serializers.IntegerField(source="user.id", read_only=True)
    nome = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    instituicao = InstituicaoSerializer(read_only=True, allow_null=True)
    cadeira_foco = CadeiraFocoSerializer(read_only=True, allow_null=True)
    ano_entrada = serializers.SerializerMethodField()

    class Meta:
        model = PerfilEstudante
        fields = (
            "id",
            "nome",
            "email",
            "intent",
            "instituicao",
            "instituicao_outra",
            "curso",
            "ano",
            "cadeira_foco",
            "minutos_por_dia",
            "provincia",
            "ano_entrada",
            "onboarding_completed_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_nome(self, obj):
        return UserProfileSerializer().get_nome(obj.user)

    @extend_schema_field(serializers.EmailField(allow_null=True))
    def get_email(self, obj):
        # O email técnico das contas institucionais nunca sai da API (S10).
        return UserProfileSerializer().get_email(obj.user)

    @extend_schema_field(serializers.IntegerField())
    def get_ano_entrada(self, obj):
        return timezone.localtime(obj.user.date_joined).year


def _text(max_length, label):
    return serializers.CharField(
        max_length=max_length,
        allow_blank=True,
        required=False,
        error_messages={
            "max_length": f"{label} pode ter no máximo {max_length} caracteres.",
            "null": f"{label} não pode ser nulo: usa um texto vazio.",
            "invalid": f"{label} tem de ser texto.",
        },
    )


class PerfilUpdateSerializer(serializers.ModelSerializer):
    """
    `PATCH /api/me/`: todos os campos opcionais. `instituicao` e
    `cadeira_foco` recebem ids. `concluir: true` grava a conclusão do
    onboarding, só da primeira vez.
    """

    intent = serializers.ChoiceField(
        choices=PerfilEstudante.INTENT_CHOICES,
        allow_null=True,
        required=False,
        error_messages={
            "invalid_choice": "Intenção inválida: usa exam_prep ou explore."
        },
    )
    instituicao = serializers.PrimaryKeyRelatedField(
        queryset=Instituicao.objects.all(),
        allow_null=True,
        required=False,
        error_messages={
            "does_not_exist": "Instituição não encontrada.",
            "incorrect_type": "Indica a instituição pelo id.",
        },
    )
    instituicao_outra = _text(200, "O nome da instituição")
    curso = _text(120, "O curso")
    ano = serializers.IntegerField(
        min_value=1,
        max_value=6,
        allow_null=True,
        required=False,
        error_messages={
            "min_value": "O ano tem de estar entre 1 e 6.",
            "max_value": "O ano tem de estar entre 1 e 6.",
            "invalid": "Indica o ano como um número entre 1 e 6.",
        },
    )
    cadeira_foco = serializers.PrimaryKeyRelatedField(
        queryset=Cadeira.objects.all(),
        allow_null=True,
        required=False,
        error_messages={
            "does_not_exist": "Cadeira não encontrada.",
            "incorrect_type": "Indica a cadeira pelo id.",
        },
    )
    minutos_por_dia = serializers.ChoiceField(
        choices=PerfilEstudante.MINUTOS_CHOICES,
        allow_null=True,
        required=False,
        error_messages={"invalid_choice": "Escolhe 5, 15, 30 ou 60 minutos por dia."},
    )
    provincia = serializers.ChoiceField(
        choices=PROVINCIA_CHOICES,
        allow_blank=True,
        required=False,
        error_messages={
            "invalid_choice": "Província inválida.",
            "null": "A província não pode ser nula: usa um texto vazio.",
        },
    )
    concluir = serializers.BooleanField(
        required=False,
        write_only=True,
        error_messages={"invalid": "`concluir` tem de ser true ou false."},
    )

    class Meta:
        model = PerfilEstudante
        fields = (
            "intent",
            "instituicao",
            "instituicao_outra",
            "curso",
            "ano",
            "cadeira_foco",
            "minutos_por_dia",
            "provincia",
            "concluir",
        )

    def update(self, instance, validated_data):
        concluir = validated_data.pop("concluir", False)
        instituicao = validated_data.get("instituicao", instance.instituicao)
        # Instituição nova e sem província no pedido: a província é a dela.
        if (
            "instituicao" in validated_data
            and "provincia" not in validated_data
            and instituicao is not None
            and instituicao.pk != instance.instituicao_id
        ):
            validated_data["provincia"] = instituicao.provincia
        if concluir and instance.onboarding_completed_at is None:
            validated_data["onboarding_completed_at"] = timezone.now()
        return super().update(instance, validated_data)
