from django.contrib import admin

from apps.transients.models import Transient


@admin.register(Transient)
class TransientAdmin(admin.ModelAdmin):
    """*admin listing for transients*"""

    list_display = ("name", "origin", "ra", "decl", "created_at")
    list_filter = ("origin",)
    search_fields = ("name", "origin")
    ordering = ("name",)
    readonly_fields = ("uuid", "created_at", "updated_at")
