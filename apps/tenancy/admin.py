from django.contrib import admin

from .models import AuditoriaMembro, Membership, Organizacao, ProvisionamentoLote


@admin.register(Organizacao)
class OrganizacaoAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "code", "org_type", "is_active", "created_at")
    search_fields = ("name", "slug", "code", "domain")
    readonly_fields = ("code",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organizacao", "role", "student_code", "is_active", "joined_at")
    list_filter = ("organizacao", "role", "is_active")
    search_fields = ("user__email", "student_code")
    readonly_fields = ("provisioned_by", "provisioned_at")


@admin.register(ProvisionamentoLote)
class ProvisionamentoLoteAdmin(admin.ModelAdmin):
    list_display = ("organizacao", "created_by", "accounts_created", "created_at")
    list_filter = ("organizacao",)
    readonly_fields = ("organizacao", "created_by", "accounts_created", "created_at")

    def has_add_permission(self, request):
        return False


@admin.register(AuditoriaMembro)
class AuditoriaMembroAdmin(admin.ModelAdmin):
    list_display = ("organizacao", "action", "actor", "membership", "created_at")
    list_filter = ("organizacao", "action")
    readonly_fields = ("organizacao", "action", "actor", "membership", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
