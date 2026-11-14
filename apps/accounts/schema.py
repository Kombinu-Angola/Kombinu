from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme


class PasswordAwareJWTScheme(SimpleJWTScheme):
    """Esquema Bearer JWT no OpenAPI para a subclasse de autenticação."""

    target_class = "apps.accounts.authentication.PasswordAwareJWTAuthentication"
