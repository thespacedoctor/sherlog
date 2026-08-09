from django.apps import AppConfig


class TransientsConfig(AppConfig):
    """*app config for the transients domain app*"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.transients"
    # WITHOUT THIS THE APP LABEL WOULD BE DERIVED FROM THE DOTTED PATH'S LAST
    # SEGMENT ANYWAY, BUT DECLARING IT KEEPS MIGRATION AND TABLE NAMES STABLE IF
    # THE PACKAGE EVER MOVES.
    label = "transients"
    verbose_name = "Transients"
