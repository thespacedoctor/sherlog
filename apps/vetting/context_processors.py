"""*context processor feeding the sidebar's "Vetting runs" section*"""

from django.db.utils import DatabaseError, OperationalError, ProgrammingError
from django.urls import reverse


def vetting_runs(request):
    """*every Sherlock version with a vetting run, for the sidebar*

    The sidebar is otherwise driven by the static
    ``DJANGO_FUNDAMENTALS_SIDEBAR_NAV`` setting, which cannot express one entry
    per row in a table — hence this, plus the project's own copy of
    ``django_fundamentals/organisms/sidebar.html``.

    **Key Arguments:**

    - ``request`` -- the current request

    **Return:**

    - ``context`` -- dict with ``vetting_runs``: label/url dicts, one per version

    **Usage:**

    ```django
    {% for run in vetting_runs %}<a href="{{ run.url }}">{{ run.label }}</a>{% endfor %}
    ```
    """
    from apps.vetting.models import SherlockVetting

    try:
        versions = (
            SherlockVetting.objects.order_by("sherlock_version")
            .values_list("sherlock_version", flat=True)
            .distinct()
        )
        runs = [
            {"label": version, "url": reverse("vetting_run", kwargs={"version": version})}
            for version in versions
        ]
    except (DatabaseError, OperationalError, ProgrammingError):
        # THE SIDEBAR RENDERS ON EVERY PAGE, INCLUDING BEFORE THE FIRST migrate.
        # A MISSING TABLE MUST NOT 500 THE WHOLE SITE.
        runs = []

    return {"vetting_runs": runs}
