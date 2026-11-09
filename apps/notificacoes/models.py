import uuid

from django.conf import settings
from django.db import models

from apps.tenancy.querysets import OrganizacaoQuerySet


class Notificacao(models.Model):
    """
    Notificação de um utilizador num contexto (Ponto Cego 3): `organizacao`
    NULL = marketplace. Forma alinhada com `AppNotification` do frontend; o
    backend guarda o alvo (`target_type` + `target_id`) e o `href` fica no
    frontend, como nas trilhas.
    """

    CATEGORY_CHOICES = (
        ("gamificacao", "Gamificação"),
        ("conteudo", "Conteúdo"),
        ("conta", "Conta"),
    )
    TONE_CHOICES = (
        ("urgente", "Urgente"),
        ("informativo", "Informativo"),
        ("neutro", "Neutro"),
    )
    TARGET_CHOICES = (
        ("trilha", "Trilha"),
        ("enquete", "Enquete"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notificacoes"
    )
    organizacao = models.ForeignKey(
        "tenancy.Organizacao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="notificacoes",
        help_text="NULL = marketplace (B2C).",
    )
    category = models.CharField(max_length=12, choices=CATEGORY_CHOICES)
    tone = models.CharField(max_length=12, choices=TONE_CHOICES, default="informativo")
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default="")
    target_type = models.CharField(
        max_length=10, choices=TARGET_CHOICES, blank=True, default=""
    )
    target_id = models.UUIDField(null=True, blank=True)
    # Origem do evento (ex.: "trilha_publicada:<id>"); torna a geração idempotente.
    source_key = models.CharField(max_length=80)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OrganizacaoQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "source_key"], name="unique_notificacao_user_source"
            )
        ]
        indexes = [
            models.Index(
                fields=["user", "organizacao", "read_at"],
                name="notificacao_user_ctx_read",
            )
        ]

    def __str__(self):
        return f"{self.user_id}: {self.title[:40]}"
