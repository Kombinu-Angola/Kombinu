"""
Autenticação institucional (D1, D10): código da escola + número de aluno +
password. As contas sem email próprio têm um email técnico não entregável
(`<aluno>@<escola>.kombinu.invalid`) que nunca sai da API.
"""
from django.utils import timezone

from apps.tenancy.codes import normalize_org_code, normalize_student_code
from apps.tenancy.models import Membership

from .models import CustomUser

TECHNICAL_EMAIL_DOMAIN = "kombinu.invalid"


def is_technical_email(email):
    return (email or "").lower().endswith("." + TECHNICAL_EMAIL_DOMAIN)


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
    if (
        user.must_change_password
        and user.temp_password_expires_at is not None
        and user.temp_password_expires_at < timezone.now()
    ):
        return None
    return user
