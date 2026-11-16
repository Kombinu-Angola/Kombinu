"""Tratamento de excepções da API."""

import math

from rest_framework.exceptions import Throttled
from rest_framework.views import exception_handler as drf_exception_handler


def throttled_message(wait):
    """Texto próprio: a tradução PT do DRF tem erros ("diponível")."""
    if wait is None:
        return "Demasiadas tentativas. Tenta novamente mais tarde."
    seconds = max(1, math.ceil(wait))
    unit = "segundo" if seconds == 1 else "segundos"
    return f"Demasiadas tentativas. Tenta novamente dentro de {seconds} {unit}."


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None and isinstance(exc, Throttled):
        # Mantém o 429 e o Retry-After do DRF; só muda o texto.
        response.data = {"detail": throttled_message(exc.wait)}
    return response
