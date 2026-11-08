from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser


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
