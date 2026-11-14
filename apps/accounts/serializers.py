from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.tenancy.models import Membership

from .institutional import is_reserved_email, is_technical_email
from .models import CustomUser


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    user_type = serializers.ChoiceField(choices=CustomUser.USER_TYPE_CHOICES)
    email = serializers.EmailField(required=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    class Meta:
        model = CustomUser
        fields = ("email", "password", "user_type", "first_name", "last_name")

    def validate_email(self, value):
        # O domínio técnico é reservado às contas institucionais (D1/D12).
        if is_reserved_email(value):
            raise serializers.ValidationError("Enter a valid email address.")
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        user = CustomUser.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
            user_type=validated_data["user_type"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )
        return user


class MembershipSummarySerializer(serializers.Serializer):
    organizacao_id = serializers.UUIDField(source="organizacao.id")
    name = serializers.CharField(source="organizacao.name")
    code = serializers.CharField(
        source="organizacao.code",
        help_text="Código curto da escola (6 caracteres), usado no login institucional.",
    )
    role = serializers.ChoiceField(choices=Membership.ROLE_CHOICES)


class UserProfileSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField()
    first_name = serializers.SerializerMethodField()
    nome = serializers.SerializerMethodField()
    pontos = serializers.SerializerMethodField()
    nivel = serializers.SerializerMethodField()
    memberships = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = (
            "id",
            "email",
            "user_type",
            "first_name",
            "last_name",
            "nome",
            "pontos",
            "nivel",
            "must_change_password",
            "memberships",
        )
        read_only_fields = fields

    @staticmethod
    def _student_code(obj):
        membership = (
            obj.memberships.exclude(student_code__isnull=True)
            .order_by("joined_at")
            .first()
        )
        return membership.student_code if membership else None

    @extend_schema_field(serializers.EmailField(allow_null=True))
    def get_email(self, obj):
        # O email técnico das contas institucionais nunca sai da API (S10).
        return None if is_technical_email(obj.email) else obj.email

    @extend_schema_field(serializers.CharField())
    def get_first_name(self, obj):
        if obj.first_name or not is_technical_email(obj.email):
            return obj.first_name
        return self._student_code(obj) or ""

    @extend_schema_field(serializers.CharField())
    def get_nome(self, obj):
        nome = f"{self.get_first_name(obj)} {obj.last_name}".strip()
        return nome or self.get_email(obj) or f"Utilizador {obj.pk}"

    @extend_schema_field(serializers.IntegerField())
    def get_pontos(self, obj):
        # Carteira global: XP de todos os contextos (fonte: XPEvent).
        from apps.rankings.selectors import xp_total
        return xp_total(obj)

    @extend_schema_field(serializers.IntegerField())
    def get_nivel(self, obj):
        from apps.rankings.selectors import level_for
        return level_for(self.get_pontos(obj))

    @extend_schema_field(MembershipSummarySerializer(many=True))
    def get_memberships(self, obj):
        """Só as activas, em organizações activas (D13)."""
        memberships = (
            obj.memberships.filter(is_active=True, organizacao__is_active=True)
            .select_related("organizacao")
            .order_by("joined_at")
        )
        return MembershipSummarySerializer(memberships, many=True).data


class LoginResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    user = UserProfileSerializer()


class TokenPairResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()


class InstitutionalLoginSerializer(serializers.Serializer):
    school_code = serializers.CharField(
        max_length=20,
        help_text=(
            "Código curto da escola (`Organizacao.code`, 6 caracteres, ex.: "
            "K7M2QX). Não é o UUID da organização."
        ),
    )
    student_code = serializers.CharField(
        max_length=40, help_text="Número de aluno atribuído pela escola."
    )
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_current_password(self, value):
        if not self.context["user"].check_password(value):
            raise serializers.ValidationError("A password actual está errada.")
        return value

    def validate(self, attrs):
        user = self.context["user"]
        if attrs["new_password"] == attrs["current_password"]:
            raise serializers.ValidationError(
                {"new_password": ["A nova password tem de ser diferente da actual."]}
            )
        try:
            validate_password(attrs["new_password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})
        return attrs
