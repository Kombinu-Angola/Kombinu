from django.contrib import admin

from .models import Instituicao, PerfilEstudante


@admin.register(Instituicao)
class InstituicaoAdmin(admin.ModelAdmin):
    list_display = ("nome", "sigla", "provincia")
    list_filter = ("provincia",)
    search_fields = ("nome", "sigla")


@admin.register(PerfilEstudante)
class PerfilEstudanteAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "intent",
        "instituicao",
        "curso",
        "ano",
        "provincia",
        "onboarding_completed_at",
    )
    list_filter = ("intent", "provincia", "instituicao")
    search_fields = ("user__email", "curso")
    raw_id_fields = ("user", "cadeira_foco")
