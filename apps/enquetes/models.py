import uuid

from django.conf import settings
from django.db import models

from apps.tenancy.querysets import OrganizacaoQuerySet


class Enquete(models.Model):
    """
    Pergunta única sem resposta certa (SurveyDraft/SurveyResult do frontend).
    `organizacao` NULL = enquete pública (marketplace).
    """

    KIND_CHOICES = (
        ("escala", "Escala"),
        ("escolha", "Escolha"),
        ("binaria", "Binária"),
    )
    TRIGGER_CHOICES = (
        ("fim-simulado", "Fim de simulado"),
        ("fim-leitura", "Fim de leitura"),
        ("fim-modulo", "Fim de módulo"),
    )
    STATE_CHOICES = (
        ("rascunho", "Rascunho"),
        ("activa", "Activa"),
        ("encerrada", "Encerrada"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizacao = models.ForeignKey(
        "tenancy.Organizacao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="enquetes",
        help_text="NULL = marketplace (B2C).",
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="enquetes"
    )
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    question = models.TextField()
    # Decisão de negócio que a enquete informa. Interno: nunca vai ao votante.
    decision = models.TextField()
    faculty = models.CharField(max_length=120, blank=True, default="")
    subject = models.CharField(max_length=120, blank=True, default="")
    trigger = models.CharField(max_length=15, choices=TRIGGER_CHOICES)
    sample_target = models.PositiveIntegerField()
    # Semântica a confirmar com o frontend (universo elegível, relatório §2.3).
    segment_size = models.PositiveIntegerField(null=True, blank=True)
    state = models.CharField(max_length=12, choices=STATE_CHOICES, default="activa")
    # D9: validação legal pendente. A API nunca expõe a identidade do votante.
    anonymous = models.BooleanField(default=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OrganizacaoQuerySet.as_manager()

    def __str__(self):
        return self.question[:60]


class EnqueteOpcao(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enquete = models.ForeignKey(
        Enquete, on_delete=models.CASCADE, related_name="options"
    )
    label = models.CharField(max_length=200)
    order = models.PositiveSmallIntegerField()
    value = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["enquete", "order"], name="unique_enqueteopcao_order"
            )
        ]

    def __str__(self):
        return self.label


class EnqueteVoto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enquete = models.ForeignKey(
        Enquete, on_delete=models.CASCADE, related_name="votes"
    )
    opcao = models.ForeignKey(
        EnqueteOpcao, on_delete=models.PROTECT, related_name="votes"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="enquete_votes"
    )
    # Cópia de Membership.academic_year no momento do voto (agregação byYear).
    year_snapshot = models.CharField(max_length=30, blank=True, default="")
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["enquete", "user"], name="unique_enquetevoto_enquete_user"
            )
        ]

    def __str__(self):
        return f"voto {self.enquete_id}"


class EnqueteExibicao(models.Model):
    """Origem de SurveyResult.shown e .dismissed."""

    OUTCOME_CHOICES = (
        ("vista", "Vista"),
        ("respondida", "Respondida"),
        ("dispensada", "Dispensada"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enquete = models.ForeignKey(
        Enquete, on_delete=models.CASCADE, related_name="exibicoes"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+"
    )
    outcome = models.CharField(max_length=12, choices=OUTCOME_CHOICES, default="vista")
    first_shown_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["enquete", "user"], name="unique_enqueteexibicao_enquete_user"
            )
        ]
