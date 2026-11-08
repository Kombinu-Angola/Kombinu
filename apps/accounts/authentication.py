"""
Revogação de sessões por troca de password (D7): um token (access ou refresh)
emitido antes de `password_changed_at` deixa de valer. Sem tabelas novas.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

REVOKED_MESSAGE = "Token emitido antes da última troca de password."


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
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if issued_before_password_change(user, validated_token):
            raise InvalidToken(REVOKED_MESSAGE)
        return user

