from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser

from .consentimento import CONSENTIMENTO_CHOICES


class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ("creator", "Creator"),
        ("learner", "Learner"),
    )

    email = models.EmailField(unique=True, blank=False)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)
    # Auth institucional (D5–D7): troca obrigatória da password temporária e
    # invalidação dos tokens emitidos antes da última troca.
    must_change_password = models.BooleanField(default=False)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    temp_password_expires_at = models.DateTimeField(null=True, blank=True)
    # Consentimento e idade (K3). Gravados no registo público; as contas
    # anteriores e as provisionadas pelas escolas ficam a null.
    ano_nascimento = models.PositiveSmallIntegerField(null=True, blank=True)
    termos_versao = models.CharField(max_length=20, null=True, blank=True)
    termos_aceites_em = models.DateTimeField(null=True, blank=True)
    marketing_opt_in = models.BooleanField(default=False)
    consentimento_encarregado = models.CharField(
        max_length=20, choices=CONSENTIMENTO_CHOICES, null=True, blank=True
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

    def set_password(self, raw_password):
        # Qualquer troca numa conta existente (API, admin, reset) invalida os
        # tokens anteriores quando gravada. A criação da conta não conta como
        # troca, e o rehash automático no login grava só `password`
        # (update_fields), por isso não revoga sessões.
        super().set_password(raw_password)
        if self.pk is not None:
            self.password_changed_at = timezone.now()


# --- Perfil académico (K1) ----------------------------------------------------

# As 21 províncias da divisão político-administrativa de 2024.
PROVINCIA_CHOICES = (
    ("bengo", "Bengo"),
    ("benguela", "Benguela"),
    ("bie", "Bié"),
    ("cabinda", "Cabinda"),
    ("cuando", "Cuando"),
    ("cuanza_norte", "Cuanza Norte"),
    ("cuanza_sul", "Cuanza Sul"),
    ("cubango", "Cubango"),
    ("cunene", "Cunene"),
    ("huambo", "Huambo"),
    ("huila", "Huíla"),
    ("icolo_e_bengo", "Icolo e Bengo"),
    ("luanda", "Luanda"),
    ("lunda_norte", "Lunda Norte"),
    ("lunda_sul", "Lunda Sul"),
    ("malanje", "Malanje"),
    ("moxico", "Moxico"),
    ("moxico_leste", "Moxico Leste"),
    ("namibe", "Namibe"),
    ("uige", "Uíge"),
    ("zaire", "Zaire"),
)


class Instituicao(models.Model):
    """Catálogo de instituições de ensino superior. Preenche-se pelo admin."""

    nome = models.CharField(max_length=200, unique=True)
    sigla = models.CharField(max_length=30, blank=True, default="")
    provincia = models.CharField(max_length=20, choices=PROVINCIA_CHOICES)

    class Meta:
        ordering = ["nome"]
        verbose_name = "instituição"
        verbose_name_plural = "instituições"

    def __str__(self):
        return f"{self.sigla} - {self.nome}" if self.sigla else self.nome


class PerfilEstudante(models.Model):
    """
    Perfil académico do próprio utilizador (onboarding). Criado de forma
    preguiçosa no primeiro acesso a `/api/me/`. É global: não depende do
    workspace activo.
    """

    INTENT_CHOICES = (
        ("exam_prep", "Preparar exames"),
        ("explore", "Explorar"),
    )
    MINUTOS_CHOICES = ((5, "5 min"), (15, "15 min"), (30, "30 min"), (60, "60 min"))

    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="perfil"
    )
    intent = models.CharField(
        max_length=20, choices=INTENT_CHOICES, null=True, blank=True
    )
    instituicao = models.ForeignKey(
        Instituicao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="perfis",
    )
    instituicao_outra = models.CharField(max_length=200, blank=True, default="")
    curso = models.CharField(max_length=120, blank=True, default="")
    ano = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(6)],
    )
    cadeira_foco = models.ForeignKey(
        "contents.Cadeira",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="perfis_em_foco",
    )
    minutos_por_dia = models.PositiveSmallIntegerField(
        choices=MINUTOS_CHOICES, null=True, blank=True
    )
    provincia = models.CharField(
        max_length=20, choices=PROVINCIA_CHOICES, blank=True, default=""
    )
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "perfil de estudante"
        verbose_name_plural = "perfis de estudante"

    def __str__(self):
        return f"Perfil de {self.user}"
