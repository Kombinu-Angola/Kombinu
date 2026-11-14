import secrets

from django.db import migrations

# Cópia local do alfabeto: a migração não deve depender de código que mude.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def preencher_codigos(apps, schema_editor):
    Organizacao = apps.get_model("tenancy", "Organizacao")
    usados = set(
        Organizacao.objects.exclude(code__isnull=True).values_list("code", flat=True)
    )
    for org in Organizacao.objects.filter(code__isnull=True):
        code = "".join(secrets.choice(ALPHABET) for _ in range(6))
        while code in usados:
            code = "".join(secrets.choice(ALPHABET) for _ in range(6))
        usados.add(code)
        org.code = code
        org.save(update_fields=["code"])


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0002_auth_institucional_campos"),
    ]

    operations = [
        migrations.RunPython(preencher_codigos, migrations.RunPython.noop),
    ]
