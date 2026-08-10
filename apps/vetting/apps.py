from django.apps import AppConfig


class VettingConfig(AppConfig):
    """*app config for the human vetting workflow*"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.vetting"
    label = "vetting"
    verbose_name = "Vetting"
