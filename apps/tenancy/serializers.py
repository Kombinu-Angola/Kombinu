from django.conf import settings
from rest_framework import serializers

from .models import Membership


class ProvisionRowSerializer(serializers.Serializer):
    student_code = serializers.CharField(
        max_length=60,
        help_text="Número de aluno atribuído pela escola; normalizado (maiúsculas, sem espaços).",
    )
    first_name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
        default="",
        help_text="Se vier vazio, o nome de exibição é o número de aluno.",
    )
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    role = serializers.ChoiceField(choices=Membership.ROLE_CHOICES, default="student")
    academic_year = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    faculty = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    course = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        allow_null=True,
        default=None,
        help_text="Opcional. Email real (login por email); sem ele, a conta só entra pelo login institucional.",
    )


class ProvisionBatchSerializer(serializers.Serializer):
    dry_run = serializers.BooleanField(
        default=False, help_text="Só valida e devolve os erros por linha; não cria nada."
    )
    rows = ProvisionRowSerializer(many=True, allow_empty=False)

    def validate_rows(self, value):
        limit = settings.PROVISIONING_MAX_ROWS
        if len(value) > limit:
            raise serializers.ValidationError(f"No máximo {limit} linhas por lote.")
        return value


class ProvisionRowErrorSerializer(serializers.Serializer):
    row = serializers.IntegerField(help_text="Índice da linha no pedido (a começar em 0).")
    student_code = serializers.CharField()
    errors = serializers.DictField(child=serializers.ListField(child=serializers.CharField()))


class ProvisionDryRunResponseSerializer(serializers.Serializer):
    dry_run = serializers.BooleanField()
    rows = serializers.IntegerField()
    errors = ProvisionRowErrorSerializer(many=True)


class ProvisionErrorResponseSerializer(serializers.Serializer):
    errors = ProvisionRowErrorSerializer(many=True)


class ProvisionedAccountSerializer(serializers.Serializer):
    student_code = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    role = serializers.CharField()
    email = serializers.EmailField(allow_null=True)
    temporary_password = serializers.CharField(
        help_text="Mostrada só nesta resposta. Não é guardada em claro nem pode ser recuperada."
    )
    expires_at = serializers.DateTimeField()


class ProvisionResponseSerializer(serializers.Serializer):
    lote_id = serializers.UUIDField()
    created = serializers.IntegerField()
    accounts = ProvisionedAccountSerializer(many=True)
