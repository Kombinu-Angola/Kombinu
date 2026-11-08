"""
Settings só para testes (pytest). Nunca usados em produção: o WSGI/ASGI e o
manage.py apontam para `core.settings`; só o `pytest.ini` aponta para aqui.
"""
from .settings import *  # noqa: F401,F403

# MD5 é inseguro para guardar passwords, mas nos testes as passwords são
# descartáveis e o PBKDF2 real tornava a suite dezenas de vezes mais lenta.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
