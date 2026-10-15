from django.contrib import admin

from .models import Membership, Organizacao


@admin.register(Organizacao)
class OrganizacaoAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "org_type", "is_active", "created_at")
    search_fields = ("name", "slug", "domain")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organizacao", "role", "is_active", "joined_at")
    list_filter = ("organizacao", "role", "is_active")
    search_fields = ("user__email",)
