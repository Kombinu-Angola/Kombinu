import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.tenancy.querysets import OrganizacaoQuerySet


class Trilha(models.Model):
    """
    Sequência ordenada de conteúdos/quizzes/enquetes (LearningTrail do
    frontend). Sem TrilhaMista (D4) e sem campos de AdaptiveTrail (D5).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizacao = models.ForeignKey(
        "tenancy.Organizacao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="trilhas",
        help_text="NULL = marketplace (B2C).",
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="trilhas"
    )
    title = models.CharField(max_length=255)
    headline = models.CharField(max_length=255, blank=True, default="")
    subject = models.CharField(max_length=120)
    year = models.CharField(max_length=30, blank=True, default="")
    semester = models.CharField(max_length=30, blank=True, default="")
    final_exam = models.ForeignKey(
        "quizzes.Quiz",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    is_sequential = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OrganizacaoQuerySet.as_manager()

    def __str__(self):
        return self.title


class TrilhaItem(models.Model):
    KIND_CHOICES = (
        ("conteudo", "Conteúdo"),
        ("quiz", "Quiz"),
        ("enquete", "Enquete"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trilha = models.ForeignKey(Trilha, on_delete=models.CASCADE, related_name="items")
    order = models.PositiveIntegerField()
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    content = models.ForeignKey(
        "contents.Content",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="trilha_items",
    )
    quiz = models.ForeignKey(
        "quizzes.Quiz",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="trilha_items",
    )
    enquete = models.ForeignKey(
        "enquetes.Enquete",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="trilha_items",
    )
    title_override = models.CharField(max_length=255, blank=True, default="")
    summary = models.TextField(blank=True, default="")
    minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    xp_reward = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["trilha", "order"],
                name="unique_trilhaitem_order",
                deferrable=models.Deferrable.DEFERRED,
            ),
            # Exactamente um alvo, coerente com `kind`.
            models.CheckConstraint(
                name="trilhaitem_single_target_matches_kind",
                check=(
                    Q(
                        kind="conteudo",
                        content__isnull=False,
                        quiz__isnull=True,
                        enquete__isnull=True,
                    )
                    | Q(
                        kind="quiz",
                        quiz__isnull=False,
                        content__isnull=True,
                        enquete__isnull=True,
                    )
                    | Q(
                        kind="enquete",
                        enquete__isnull=False,
                        content__isnull=True,
                        quiz__isnull=True,
                    )
                ),
            ),
        ]

    @property
    def target(self):
        return self.content or self.quiz or self.enquete

    def __str__(self):
        return f"{self.trilha_id}#{self.order} ({self.kind})"


class TrilhaProgresso(models.Model):
    """Estado por utilizador; origem de TrailNode.status e .stars."""

    STATE_CHOICES = (
        ("em_curso", "Em curso"),
        ("concluido", "Concluído"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trilha_progress"
    )
    item = models.ForeignKey(
        TrilhaItem, on_delete=models.CASCADE, related_name="progress"
    )
    submission = models.ForeignKey(
        "quizzes.QuizSubmission",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    state = models.CharField(max_length=10, choices=STATE_CHOICES, default="em_curso")
    stars = models.PositiveSmallIntegerField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "item"], name="unique_trilhaprogresso_user_item"
            )
        ]
