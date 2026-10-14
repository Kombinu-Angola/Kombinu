from django.db import models
from apps.accounts.models import CustomUser
from apps.tenancy.querysets import OrganizacaoQuerySet
import uuid


class Content(models.Model):
    CATEGORY_CHOICES = (
        ("tecnologia", "Tecnologia"),
        ("negocios", "Negócios"),
        ("design", "Design"),
    )

    LEVEL_CHOICES = (
        ("Iniciante", "Iniciante"),
        ("Intermediário", "Intermediário"),
        ("Avançado", "Avançado"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField()
    creator = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="created_contents"
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    organizacao = models.ForeignKey(
        "tenancy.Organizacao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contents",
        help_text="NULL = marketplace (B2C).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Campos adicionados para suportar o formulário de criação de conteúdo
    thumbnail = models.URLField(blank=True, default="")
    video_url = models.URLField(blank=True, default="")
    text_content = models.TextField(blank=True, default="")
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default="Iniciante")
    duration = models.CharField(max_length=20, blank=True, default="")
    # Tags armazenadas como CSV para simplicidade no MVP
    tags = models.TextField(blank=True, default="")
    type = models.CharField(max_length=20, default="text")

    objects = OrganizacaoQuerySet.as_manager()

    def __str__(self):
        return self.title

    @property
    def has_quiz(self):
        return hasattr(self, "quiz")

    @property
    def quiz_id(self):
        if self.has_quiz:
            return self.quiz.id
        return None

    @property
    def tags_list(self):
        """Retorna as tags como lista Python."""
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]
