from django.contrib import admin

from apps.vetting.models import SherlockVetting


@admin.register(SherlockVetting)
class SherlockVettingAdmin(admin.ModelAdmin):
    """*admin listing for vetting rows*"""

    list_display = ("transient", "sherlock_version", "sherlock_correct", "user", "updated_at")
    list_filter = ("sherlock_version", "sherlock_correct")
    search_fields = ("transient__name", "user_comment")
    raw_id_fields = ("transient",)
    readonly_fields = ("created_at", "updated_at")
