from django.apps import AppConfig


class ContentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.contents"

    def ready(self):
        from . import schema  # noqa: F401  (regista o esquema do CadeiraField)
