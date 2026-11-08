import hashlib

from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle

from apps.tenancy.codes import normalize_org_code, normalize_student_code


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


class InstitutionalLoginIdentifierRateThrottle(SimpleRateThrottle):
    """Limite por conta no login institucional: par (escola, aluno), em hash."""

    scope = "login_identifier"

    def get_cache_key(self, request, view):
        data = request.data if hasattr(request.data, "get") else {}
        school = data.get("school_code")
        student = data.get("student_code")
        if not isinstance(school, str) or not isinstance(student, str):
            return None
        ident = f"{normalize_org_code(school)}:{normalize_student_code(student)}"
        if ident == ":":
            return None
        digest = hashlib.sha256(ident.encode()).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": digest}


class PasswordChangeRateThrottle(UserRateThrottle):
    scope = "password_change"
