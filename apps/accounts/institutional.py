"""
Autenticação institucional (D1, D10): código da escola + número de aluno +
password. As contas sem email próprio têm um email técnico não entregável
(`<aluno>@<escola>.kombinu.invalid`) que nunca sai da API.
"""
import secrets
from datetime import timedelta

from django.utils import timezone

from apps.tenancy.codes import normalize_org_code, normalize_student_code
from apps.tenancy.models import Membership

from .models import CustomUser

TECHNICAL_EMAIL_DOMAIN = "kombinu.invalid"
# Contas do `manage.py seed_demo`. Reservado: nenhum caminho público cria
# contas neste domínio, para ninguém se antecipar ao seed e herdar um papel.
DEMO_EMAIL_DOMAIN = "demo.kombinu.com"

# D5: password temporária de uso único, sem caracteres ambíguos (0/O, 1/l/I).
TEMP_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
TEMP_PASSWORD_LENGTH = 10
TEMP_PASSWORD_VALIDITY = timedelta(days=7)


def generate_temporary_password():
    return "".join(
        secrets.choice(TEMP_PASSWORD_ALPHABET) for _ in range(TEMP_PASSWORD_LENGTH)
    )


def technical_email(student_code, organizacao):
    """Email não entregável e único por construção (RFC 2606, `.invalid`)."""
    return f"{student_code.lower()}@{organizacao.slug}.{TECHNICAL_EMAIL_DOMAIN}"


def is_technical_email(email):
    return (email or "").strip().lower().endswith("." + TECHNICAL_EMAIL_DOMAIN)


def is_demo_email(email):
    email = (email or "").strip().lower()
    return email.endswith("@" + DEMO_EMAIL_DOMAIN) or email.endswith(
        "." + DEMO_EMAIL_DOMAIN
    )


def is_reserved_email(email):
    """Domínios que só o sistema usa: técnico (institucional) e demonstração."""
    return is_technical_email(email) or is_demo_email(email)


def temp_password_expired(user):
    """Regra única (D5), aplicada aos dois logins."""
    return (
        user.must_change_password
        and user.temp_password_expires_at is not None
        and user.temp_password_expires_at < timezone.now()
    )


def authenticate_institutional(school_code, student_code, password):
    """
    Devolve o utilizador ou None. Todas as falhas são indistinguíveis para o
    cliente (S2): escola inexistente ou inactiva, aluno inexistente, password
    errada, conta inactiva ou password temporária expirada. Quando não há
    conta, o hash corre na mesma para o tempo de resposta não a denunciar.
    """
    school = normalize_org_code(school_code)
    student = normalize_student_code(student_code)
    membership = None
    if school and student:
        membership = (
            Membership.objects.select_related("user")
            .filter(
                organizacao__code=school,
                organizacao__is_active=True,
                student_code=student,
            )
            .first()
        )
    if membership is None:
        CustomUser().set_password(password or "")
        return None

    user = membership.user
    if not user.check_password(password or "") or not user.is_active:
        return None
    if temp_password_expired(user):
        return None
    return user
