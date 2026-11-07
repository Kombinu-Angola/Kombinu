import hashlib

from rest_framework.throttling import SimpleRateThrottle


class IPRateThrottle(SimpleRateThrottle):
    """Limita por IP de origem, com ou sem utilizador autenticado."""

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class LoginRateThrottle(IPRateThrottle):
    scope = "login"


class RegisterRateThrottle(IPRateThrottle):
    scope = "register"


class TokenRefreshRateThrottle(IPRateThrottle):
    scope = "token_refresh"


class LoginIdentifierRateThrottle(SimpleRateThrottle):
    """
    Limita tentativas de login por conta (email), independentemente do IP.
    O email entra na chave de cache só como hash.
    """

    scope = "login_identifier"

    def get_cache_key(self, request, view):
        email = request.data.get("email") if hasattr(request.data, "get") else None
        if not isinstance(email, str) or not email.strip():
            return None
        digest = hashlib.sha256(email.strip().lower().encode()).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": digest}
