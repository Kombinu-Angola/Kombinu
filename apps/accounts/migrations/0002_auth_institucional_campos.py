from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="must_change_password",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="customuser",
            name="password_changed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customuser",
            name="temp_password_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
