import uuid

from django.conf import settings
from django.db import models

from .codes import generate_org_code, normalize_org_code, normalize_student_code


class Organizacao(models.Model):
    """
    Escola ou cliente corporativo (B2B). O isolamento é lógico: as entidades
    ligam-se por FK `organizacao`; `NULL` significa marketplace (B2C).
    """

    TYPE_CHOICES = (
        ("escola", "Escola"),
        ("empresa", "Empresa"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=80, unique=True)
    code = models.CharField(
        max_length=6,
        unique=True,
        editable=False,
        help_text="Código curto da escola usado no login institucional (D2).",
    )
    domain = models.CharField(
        max_length=255, unique=True, null=True, blank=True,
        help_text="Domínio de email para adesão automática (opcional).",
    )
    org_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="escola")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "organização"
        verbose_name_plural = "organizações"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.code = normalize_org_code(self.code)
        if not self.code:
            self.code = generate_org_code()
            while Organizacao.objects.filter(code=self.code).exists():
                self.code = generate_org_code()
        super().save(*args, **kwargs)


class Membership(models.Model):
    """Pivô utilizador × organização. O marketplace não tem Membership."""

    ROLE_CHOICES = (
        ("student", "Student"),
        ("teacher", "Teacher"),
        ("admin", "Admin"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    organizacao = models.ForeignKey(
        Organizacao, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="student")
    academic_year = models.CharField(max_length=30, blank=True, default="")
    faculty = models.CharField(max_length=120, blank=True, default="")
    course = models.CharField(max_length=120, blank=True, default="")
    student_code = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        help_text="Número de aluno atribuído pela escola; único por organização.",
    )
    provisioned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    provisioned_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organizacao"], name="unique_membership_user_org"
            ),
            models.UniqueConstraint(
                fields=["organizacao", "student_code"],
                name="unique_membership_org_student_code",
            ),
        ]

    def __str__(self):
        return f"{self.user} @ {self.organizacao} ({self.role})"

    def save(self, *args, **kwargs):
        self.student_code = normalize_student_code(self.student_code) or None
        super().save(*args, **kwargs)


class ProvisionamentoLote(models.Model):
    """Trilho de auditoria de cada lote de contas criado por um admin (D3/S6)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizacao = models.ForeignKey(
        Organizacao, on_delete=models.PROTECT, related_name="provisionamentos"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accounts_created = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "lote de provisionamento"
        verbose_name_plural = "lotes de provisionamento"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organizacao} — {self.accounts_created} contas ({self.created_at:%Y-%m-%d})"


class AuditoriaMembro(models.Model):
    """Acções de gestão de um admin sobre membros da organização (D9)."""

    ACTION_CHOICES = (
        ("reset_password", "Reset de password"),
        ("deactivate", "Desactivar"),
        ("reactivate", "Reactivar"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizacao = models.ForeignKey(
        Organizacao, on_delete=models.PROTECT, related_name="auditoria_membros"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    membership = models.ForeignKey(
        Membership, on_delete=models.SET_NULL, null=True, related_name="auditoria"
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "auditoria de membro"
        verbose_name_plural = "auditoria de membros"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organizacao} — {self.action} ({self.created_at:%Y-%m-%d %H:%M})"


class ConversaoMarketplace(models.Model):
    """
    Primeira entrada no marketplace (B2C) de um membro de uma escola (B4).
    Uma linha por (utilizador, organização de origem), criada pelo endpoint
    explícito que o seletor de workspace chama. Só leitura no admin; não é
    exposta ao admin da escola (privacidade, D14).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversoes_marketplace",
    )
    organizacao = models.ForeignKey(
        Organizacao, on_delete=models.PROTECT, related_name="conversoes_marketplace"
    )
    first_visit_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "conversão para o marketplace"
        verbose_name_plural = "conversões para o marketplace"
        ordering = ["-first_visit_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organizacao"], name="unique_conversao_user_org"
            )
        ]

    def __str__(self):
        return f"{self.user_id} de {self.organizacao} ({self.first_visit_at:%Y-%m-%d})"
