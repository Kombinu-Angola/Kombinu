"""
Consentimento e idade no registo (K3). Regra num só sítio: mudar o limite de
idade é mudar `IDADE_LIMITE_CONSENTIMENTO`.

Só se regista o estado. O fluxo de pedir a autorização ao encarregado (link,
token) ainda não existe.
"""

from django.utils import timezone

# Termos de utilização em vigor (versão 3.0, de 12 Nov 2026).
TERMOS_VERSAO_ACTUAL = "3.0"

ANO_MINIMO_NASCIMENTO = 1900

# Idade calculada só pelo ano: ano actual - ano de nascimento. Abaixo deste
# limite, o consentimento do encarregado fica `pendente`.
IDADE_LIMITE_CONSENTIMENTO = 18

NAO_NECESSARIO = "nao_necessario"
PENDENTE = "pendente"
CONCEDIDO = "concedido"
CONSENTIMENTO_CHOICES = (
    (NAO_NECESSARIO, "Não necessário"),
    (PENDENTE, "Pendente"),
    (CONCEDIDO, "Concedido"),
)


def ano_actual():
    """Ano corrente na hora local (Africa/Luanda)."""
    return timezone.localdate().year


def idade_por_ano(ano_nascimento, ano=None):
    return (ano or ano_actual()) - ano_nascimento


def estado_consentimento(ano_nascimento, ano=None):
    """`pendente` abaixo do limite de idade; `nao_necessario` a partir dele."""
    if idade_por_ano(ano_nascimento, ano) < IDADE_LIMITE_CONSENTIMENTO:
        return PENDENTE
    return NAO_NECESSARIO
