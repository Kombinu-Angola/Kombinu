from django.contrib import admin

from .models import Cadeira


@admin.register(Cadeira)
class CadeiraAdmin(admin.ModelAdmin):
    list_display = ("nome", "curso")
    list_filter = ("curso",)
    search_fields = ("nome", "curso")
