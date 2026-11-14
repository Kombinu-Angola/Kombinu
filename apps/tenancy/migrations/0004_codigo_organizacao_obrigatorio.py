from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0003_preencher_codigo_organizacao"),
    ]

    operations = [
        migrations.AlterField(
            model_name="organizacao",
            name="code",
            field=models.CharField(
                editable=False,
                help_text="Código curto da escola usado no login institucional (D2).",
                max_length=6,
                unique=True,
            ),
        ),
    ]
