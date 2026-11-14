import uuid

from django.conf import settings
from django.db import models


class XPEvent(models.Model):
    """
    Ledger único de XP: uma linha por concessão. Fonte da carteira, do nível e
    (nas próximas fases) dos rankings global e por organização.

    `source_type` + `source_id` identificam a origem (ex.: a QuizSubmission);
    a combinação é única, o que torna a concessão idempotente.
    """

    SOURCE_QUIZ_SUBMISSION = "quiz_submission"
    SOURCE_ENQUETE_VOTO = "enquete_voto"
    SOURCE_CHOICES = (
        (SOURCE_QUIZ_SUBMISSION, "Quiz submission"),
        (SOURCE_ENQUETE_VOTO, "Enquete voto"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="xp_events"
    )
    organizacao = models.ForeignKey(
        "tenancy.Organizacao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="xp_events",
        help_text="NULL = XP do marketplace (B2C).",
    )
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    source_id = models.CharField(max_length=64)
    amount = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "source_id"], name="unique_xpevent_source"
            )
        ]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["organizacao", "user"]),
        ]

    def __str__(self):
        return f"{self.user_id} +{self.amount} ({self.source_type}:{self.source_id})"
