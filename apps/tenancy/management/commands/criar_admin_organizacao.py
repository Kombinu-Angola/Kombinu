"""
Bootstrap do 1.º admin de uma organização (D3: P1 só para este passo).

O admin entra pelo login por email e tem de trocar a password temporária no
1.º acesso. A password é escrita uma única vez na saída deste comando, para
quem o corre a entregar por canal seguro; não é registada em logs.
"""
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.institutional import (
    TEMP_PASSWORD_VALIDITY,
    generate_temporary_password,
    is_technical_email,
)
from apps.accounts.models import CustomUser
from apps.tenancy.codes import normalize_org_code
from apps.tenancy.models import Membership, Organizacao, ProvisionamentoLote


class Command(BaseCommand):
    help = "Cria o primeiro admin de uma organização, com password temporária."

    def add_arguments(self, parser):
        parser.add_argument("organizacao", help="Slug ou código (6 caracteres) da organização.")
        parser.add_argument("--email", required=True, help="Email real do admin.")
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")

    def handle(self, *args, **options):
        ref = options["organizacao"].strip()
        organizacao = Organizacao.objects.filter(
            Q(slug=ref) | Q(code=normalize_org_code(ref)), is_active=True
        ).first()
        if organizacao is None:
            raise CommandError("Organização activa não encontrada.")

        email = options["email"].strip().lower()
        try:
            validate_email(email)
        except ValidationError:
            raise CommandError("Email inválido.")
        if is_technical_email(email):
            raise CommandError("Domínio de email reservado.")
        if CustomUser.objects.filter(email__iexact=email).exists():
            # D12: não anexar a uma conta existente sem consentimento.
            raise CommandError("Já existe uma conta com este email.")

        password = generate_temporary_password()
        now = timezone.now()
        expires_at = now + TEMP_PASSWORD_VALIDITY
        with transaction.atomic():
            user = CustomUser(
                username=email,
                email=email,
                first_name=options["first_name"].strip(),
                last_name=options["last_name"].strip(),
                user_type="learner",
                must_change_password=True,
                temp_password_expires_at=expires_at,
            )
            user.set_password(password)
            user.password_changed_at = now
            user.save()
            Membership.objects.create(
                user=user,
                organizacao=organizacao,
                role="admin",
                provisioned_at=now,
            )
            ProvisionamentoLote.objects.create(
                organizacao=organizacao, created_by=None, accounts_created=1
            )

        self.stdout.write(f"Admin criado em {organizacao.name} ({organizacao.code}): {email}")
        self.stdout.write(f"Password temporária (mostrada só agora): {password}")
        self.stdout.write(f"Expira em: {expires_at:%Y-%m-%d %H:%M} UTC")
