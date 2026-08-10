"""*routes for the per-version vetting workflow*"""

from django.urls import path, re_path

from apps.vetting.views import VettingRunView, VetTransientView

# A SHERLOCK VERSION IS A SHORT STRING LIKE v0.0.0 — LETTERS, DIGITS, DOTS,
# DASHES AND UNDERSCORES, UP TO THE COLUMN'S 15 CHARACTERS.
VERSION_PATTERN = r"(?P<version>[\w.\-]{1,15})"

urlpatterns = [
    re_path(rf"^vetting/{VERSION_PATTERN}/$", VettingRunView.as_view(), name="vetting_run"),
    path(
        "vetting/<str:version>/transient/<uuid:uuid>/",
        VetTransientView.as_view(),
        name="vetting_transient",
    ),
    re_path(
        rf"^vetting/{VERSION_PATTERN}/(?P<tab>unvetted|correct|incorrect)/$",
        VettingRunView.as_view(),
        name="vetting_run_tab",
    ),
]
