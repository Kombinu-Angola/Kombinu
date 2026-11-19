from django.db import models
from apps.accounts.models import CustomUser
from apps.tenancy.querysets import OrganizacaoQuerySet
import uuid


class Cadeira(models.Model):
    """
    Catálogo global de cadeiras (K2). Não tem FK de organização: a mesma
    cadeira serve o marketplace e todas as escolas. O isolamento continua nos
    objectos que a referem (conteúdos, quizzes e trilhas), sempre por
    `for_context()`.
    """

    nome = models.CharField(max_length=160)
    curso = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        unique_together = ("nome", "curso")
        ordering = ["nome", "curso"]
        verbose_name = "cadeira"
        verbose_name_plural = "cadeiras"

    def __str__(self):
        return f"{self.nome} ({self.curso})" if self.curso else self.nome


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
        CustomUser, on_delete=models.PROTECT, related_name="created_contents"
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
    cadeira = models.ForeignKey(
        Cadeira,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contents",
    )

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
