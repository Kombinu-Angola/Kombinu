from django.contrib import admin

from .models import Notificacao


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "organizacao", "category", "read_at", "created_at")
    list_filter = ("category", "tone")
    search_fields = ("title",)
    raw_id_fields = ("user", "organizacao")

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in Notificacao._meta.fields]

    def has_add_permission(self, request):
        return False
