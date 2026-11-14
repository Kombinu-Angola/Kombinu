"""Códigos usados no login institucional (D2): escola e aluno."""
import re
import secrets

# Sem caracteres ambíguos quando ditados ou escritos à mão (0/O, 1/I).
ORG_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ORG_CODE_LENGTH = 6


def generate_org_code():
    return "".join(secrets.choice(ORG_CODE_ALPHABET) for _ in range(ORG_CODE_LENGTH))


def normalize_org_code(value):
    return re.sub(r"\s+", "", value or "").upper()


def normalize_student_code(value):
    """Maiúsculas e sem espaços, para evitar duplicados por formatação."""
    return re.sub(r"\s+", "", value or "").upper()


# Também é a parte local do email técnico: só caracteres seguros num email.
STUDENT_CODE_RE = re.compile(r"^[A-Z0-9](?:[A-Z0-9_/-]|\.(?!\.))*(?<!\.)$")


def is_valid_student_code(value):
    return bool(value) and len(value) <= 40 and bool(STUDENT_CODE_RE.match(value))
