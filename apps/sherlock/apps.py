from django.apps import AppConfig


class SherlockConfig(AppConfig):
    """*app config for the read-only mirrors of Sherlock's own tables*"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sherlock"
    label = "sherlock"
    verbose_name = "Sherlock"
