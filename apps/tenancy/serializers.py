from django.conf import settings
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.institutional import is_technical_email

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


class MemberSerializer(serializers.ModelSerializer):
    """Membro da organização para o admin. O email técnico nunca sai da API."""

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    first_name = serializers.SerializerMethodField()
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    email = serializers.SerializerMethodField()
    must_change_password = serializers.BooleanField(
        source="user.must_change_password", read_only=True
    )

    class Meta:
        model = Membership
        fields = (
            "id",
            "user_id",
            "student_code",
            "first_name",
            "last_name",
            "email",
            "role",
            "academic_year",
            "faculty",
            "course",
            "is_active",
            "joined_at",
            "provisioned_at",
            "must_change_password",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_first_name(self, obj):
        return obj.user.first_name or obj.student_code or ""

    @extend_schema_field(serializers.EmailField(allow_null=True))
    def get_email(self, obj):
        return None if is_technical_email(obj.user.email) else obj.user.email


class PasswordResetResponseSerializer(serializers.Serializer):
    membership_id = serializers.UUIDField()
    student_code = serializers.CharField(allow_null=True)
    temporary_password = serializers.CharField(
        help_text="Mostrada só nesta resposta. Não é guardada em claro nem pode ser recuperada."
    )
    expires_at = serializers.DateTimeField()
