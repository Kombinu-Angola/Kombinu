"""
Revogação de sessões por troca de password (D7): um token (access ou refresh)
emitido antes de `password_changed_at` deixa de valer. Sem tabelas novas.

Gate de troca obrigatória (D6): enquanto `must_change_password` estiver
activo, só as views marcadas com `password_change_exempt = True` respondem.
"""
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

REVOKED_MESSAGE = "Token emitido antes da última troca de password."
PASSWORD_CHANGE_REQUIRED_CODE = "password_change_required"
PASSWORD_CHANGE_REQUIRED_MESSAGE = "É necessário trocar a password antes de continuar."


class PasswordChangeRequired(PermissionDenied):
    """403 `{detail, code}`, no mesmo formato dos erros do simplejwt."""

    default_code = PASSWORD_CHANGE_REQUIRED_CODE

    def __init__(self):
        super().__init__(
            {
                "detail": PASSWORD_CHANGE_REQUIRED_MESSAGE,
                "code": PASSWORD_CHANGE_REQUIRED_CODE,
            }
        )


def issued_before_password_change(user, token):
    """
    `iat` tem resolução de segundos; compara-se com o segundo da troca, para
    não rejeitar os tokens novos emitidos logo a seguir à troca.
    """
    changed_at = getattr(user, "password_changed_at", None)
    if changed_at is None:
        return False
    issued_at = token.payload.get("iat")
    if issued_at is None:
        return True
    return int(issued_at) < int(changed_at.timestamp())


class PasswordAwareJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user = result[0]
            view = (getattr(request, "parser_context", None) or {}).get("view")
            if user.must_change_password and not getattr(
                view, "password_change_exempt", False
            ):
                raise PasswordChangeRequired()
        return result

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if issued_before_password_change(user, validated_token):
            raise InvalidToken(REVOKED_MESSAGE)
        return user

