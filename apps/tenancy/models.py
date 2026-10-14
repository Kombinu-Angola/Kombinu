import uuid

from django.conf import settings
from django.db import models


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
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organizacao"], name="unique_membership_user_org"
            )
        ]

    def __str__(self):
        return f"{self.user} @ {self.organizacao} ({self.role})"
