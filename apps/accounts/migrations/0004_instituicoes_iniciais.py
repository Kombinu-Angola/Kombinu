"""
Catálogo inicial de instituições (K1): as nove de Luanda aprovadas para o
onboarding. As restantes entram pelo admin.
"""

from django.db import migrations

INSTITUICOES = [
    ("Universidade Agostinho Neto", "UAN"),
    ("Universidade Católica de Angola", "UCAN"),
    ("Instituto Superior Politécnico de Tecnologias e Ciências", "ISPTEC"),
    ("Universidade Gregório Semedo", "UGS"),
    ("Universidade Metodista de Angola", "UMA"),
    ("Universidade Óscar Ribas", "UOR"),
    ("Universidade Lusíada de Angola", "Lusíada"),
    ("Universidade Jean Piaget de Angola", "Jean Piaget"),
    ("Instituto Superior de Ciências da Educação de Luanda", "ISCED Luanda"),
]


def criar(apps, schema_editor):
    Instituicao = apps.get_model("accounts", "Instituicao")
    for nome, sigla in INSTITUICOES:
        Instituicao.objects.get_or_create(
            nome=nome, defaults={"sigla": sigla, "provincia": "luanda"}
        )


def remover(apps, schema_editor):
    Instituicao = apps.get_model("accounts", "Instituicao")
    Instituicao.objects.filter(nome__in=[nome for nome, _ in INSTITUICOES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_perfil_academico"),
    ]

    operations = [
        migrations.RunPython(criar, remover),
    ]
