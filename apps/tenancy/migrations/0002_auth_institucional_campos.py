import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="organizacao",
            name="code",
            field=models.CharField(
                editable=False,
                help_text="Código curto da escola usado no login institucional (D2).",
                max_length=6,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="membership",
            name="student_code",
            field=models.CharField(
                blank=True,
                help_text="Número de aluno atribuído pela escola; único por organização.",
                max_length=40,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="membership",
            name="provisioned_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="membership",
            name="provisioned_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="membership",
            constraint=models.UniqueConstraint(
                fields=("organizacao", "student_code"),
                name="unique_membership_org_student_code",
            ),
        ),
        migrations.CreateModel(
            name="ProvisionamentoLote",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("accounts_created", models.PositiveIntegerField(default=0)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organizacao",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="provisionamentos",
                        to="tenancy.organizacao",
                    ),
                ),
            ],
            options={
                "verbose_name": "lote de provisionamento",
                "verbose_name_plural": "lotes de provisionamento",
                "ordering": ["-created_at"],
            },
        ),
    ]
