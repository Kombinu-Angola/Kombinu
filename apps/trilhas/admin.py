from django.contrib import admin

from .models import Trilha, TrilhaItem


class TrilhaItemInline(admin.TabularInline):
    model = TrilhaItem
    extra = 0
    ordering = ("order",)


@admin.register(Trilha)
class TrilhaAdmin(admin.ModelAdmin):
    list_display = ("title", "subject", "organizacao", "is_published", "created_at")
    list_filter = ("organizacao", "is_published")
    inlines = [TrilhaItemInline]
