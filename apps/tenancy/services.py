"""
Provisionamento institucional (D3 = P2, D4, D5, D12): um admin da organização
cria contas em lote, cada uma com a sua Membership, numa só transacção.

As passwords temporárias só existem em memória durante o pedido e vão na
resposta uma única vez; nunca são registadas em logs nem gravadas em claro.
"""
from django.db import transaction
from django.utils import timezone

from apps.accounts.institutional import (
    TEMP_PASSWORD_VALIDITY,
    generate_temporary_password,
    is_technical_email,
    technical_email,
)
from apps.accounts.models import CustomUser

from .codes import is_valid_student_code, normalize_student_code
from .models import Membership, ProvisionamentoLote


class ProvisioningError(Exception):
    """Lote recusado: nenhuma conta foi criada. `errors` traz o detalhe por linha."""

    def __init__(self, errors):
        super().__init__("Lote recusado.")
        self.errors = errors


def is_org_admin(user, organizacao):
    return (
        organizacao is not None
        and Membership.objects.filter(
            user=user, organizacao=organizacao, role="admin", is_active=True
        ).exists()
    )


def _normalized_rows(rows):
    """Normaliza antes de qualquer validação ou escrita (nunca depende do save)."""
    normalized = []
    for row in rows:
        email = (row.get("email") or "").strip().lower()
        normalized.append(
            {
                **row,
                "student_code": normalize_student_code(row.get("student_code")),
                "email": email or None,
                "first_name": (row.get("first_name") or "").strip(),
                "last_name": (row.get("last_name") or "").strip(),
            }
        )
    return normalized


def validate_batch(organizacao, rows):
    """Devolve a lista de erros por linha (vazia se o lote é válido)."""
    rows = _normalized_rows(rows)
    codes = [r["student_code"] for r in rows]
    seen_codes, seen_emails = set(), set()
    existing_codes = set(
        Membership.objects.filter(
            organizacao=organizacao, student_code__in=codes
        ).values_list("student_code", flat=True)
    )

    errors = []
    for index, row in enumerate(rows):
        code = row["student_code"]
        row_errors = {}
        if not is_valid_student_code(code):
            row_errors["student_code"] = [
                "Número de aluno inválido: use letras, números, '-', '_', '/' ou '.'."
            ]
        elif code in seen_codes:
            row_errors["student_code"] = ["Número de aluno repetido neste lote."]
        elif code in existing_codes:
            row_errors["student_code"] = ["Já existe um membro com este número de aluno."]

        email = row["email"]
        if email:
            if is_technical_email(email):
                row_errors["email"] = ["Domínio de email reservado."]
            elif email in seen_emails:
                row_errors["email"] = ["Email repetido neste lote."]
            elif CustomUser.objects.filter(email__iexact=email).exists():
                # D12: nunca anexar uma Membership a uma conta existente.
                row_errors["email"] = ["Já existe uma conta com este email."]
        elif "student_code" not in row_errors and CustomUser.objects.filter(
            email__iexact=technical_email(code, organizacao)
        ).exists():
            row_errors["student_code"] = ["Já existe uma conta para este número de aluno."]

        seen_codes.add(code)
        if email:
            seen_emails.add(email)
        if row_errors:
            errors.append({"row": index, "student_code": code, "errors": row_errors})
    return errors


def provision_batch(*, organizacao, admin, rows):
    """
    Tudo ou nada (D4). Levanta ProvisioningError sem criar nada se alguma
    linha for inválida. Devolve o lote e as contas com a password temporária.
    """
    errors = validate_batch(organizacao, rows)
    if errors:
        raise ProvisioningError(errors)

    rows = _normalized_rows(rows)
    now = timezone.now()
    expires_at = now + TEMP_PASSWORD_VALIDITY
    accounts = []
    with transaction.atomic():
        lote = ProvisionamentoLote.objects.create(
            organizacao=organizacao, created_by=admin, accounts_created=len(rows)
        )
        for row in rows:
            code = row["student_code"]
            email = row["email"] or technical_email(code, organizacao)
            password = generate_temporary_password()
            user = CustomUser(
                username=email,
                email=email,
                # Nome de exibição sempre presente (contrato aprovado).
                first_name=row["first_name"] or code,
                last_name=row["last_name"],
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
                role=row.get("role") or "student",
                student_code=code,
                academic_year=row.get("academic_year", ""),
                faculty=row.get("faculty", ""),
                course=row.get("course", ""),
                provisioned_by=admin,
                provisioned_at=now,
            )
            accounts.append(
                {
                    "student_code": code,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": row.get("role") or "student",
                    "email": row["email"],
                    "temporary_password": password,
                    "expires_at": expires_at,
                }
            )
    return lote, accounts
