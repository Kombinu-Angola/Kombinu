from django.contrib import admin

from .models import Enquete, EnqueteOpcao


class EnqueteOpcaoInline(admin.TabularInline):
    model = EnqueteOpcao
    extra = 0


@admin.register(Enquete)
class EnqueteAdmin(admin.ModelAdmin):
    list_display = ("question", "kind", "state", "organizacao", "created_at")
    list_filter = ("state", "kind", "organizacao")
    inlines = [EnqueteOpcaoInline]
