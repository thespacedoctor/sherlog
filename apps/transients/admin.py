from django.contrib import admin

from apps.transients.models import Transient


@admin.register(Transient)
class TransientAdmin(admin.ModelAdmin):
    """*admin listing for transients*"""

    list_display = ("name", "origin", "sherlock_classification", "ra", "decl", "created_at")
    list_filter = ("origin", "sherlock_classification")
    search_fields = ("name", "origin", "sherlock_classification")
    ordering = ("name",)
    readonly_fields = ("uuid", "created_at", "updated_at")
