import uuid as uuidlib

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django_fundamentals.models import TimeStampedModel


class Transient(TimeStampedModel):
    """*an astronomical transient, as reported by an alert broker*

    The primary key is a UUID rather than an auto-increment integer so records
    can be created in more than one place (an import, the API, a future
    crossmatch job) without colliding.

    **Usage:**

    ```python
    transient = Transient.objects.create(
        name="313853517460144141",
        origin="lasair",
        ra=148.61201,
        decl=1.609392,
        url="https://lasair.lsst.ac.uk/objects/313853517460144141",
    )
    ```
    """

    uuid = models.UUIDField(primary_key=True, default=uuidlib.uuid4, editable=False)
    # RA IS IN DECIMAL DEGREES 0-360, DEC IN DECIMAL DEGREES -90 TO +90. THE
    # VALIDATORS RUN ON full_clean() AND IN DRF SERIALIZERS, NOT ON A BARE
    # .save(), SO THE IMPORTER CALLS full_clean() EXPLICITLY.
    ra = models.FloatField(
        "RA",
        validators=[MinValueValidator(0.0), MaxValueValidator(360.0)],
        help_text="Right ascension in decimal degrees.",
    )
    decl = models.FloatField(
        "Dec",
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)],
        help_text="Declination in decimal degrees.",
    )
    name = models.CharField(max_length=30, help_text="Broker-assigned object name or ID.")
    origin = models.CharField(
        max_length=75,
        help_text="Where the transient came from — a broker name or the URL of the filter that selected it.",
    )
    url = models.URLField(max_length=200, blank=True, help_text="Object page at the origin broker.")
    # NULL WHEN SHERLOCK HAS NOT CLASSIFIED THE TRANSIENT, SO "NOT RUN YET" IS
    # DISTINCT FROM ANY CLASSIFICATION IT COULD RETURN. blank=True KEEPS THE
    # FIELD OPTIONAL IN FORMS AND THE ADMIN.
    sherlock_classification = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        default=None,
        help_text="Sherlock's classification code for this transient, e.g. SN, NT, VS, AGN.",
    )

    class Meta:
        db_table = "transients"
        ordering = ["name"]
        constraints = [
            # ONE ROW PER OBJECT PER BROKER. THIS IS WHAT MAKES THE IMPORTER
            # IDEMPOTENT — RE-RUNNING IT UPDATES RATHER THAN DUPLICATES.
            models.UniqueConstraint(fields=["name", "origin"], name="uniq_transient_name_origin"),
        ]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["origin"]),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        """*the UI detail page for this transient*

        **Return:**

        - ``url`` -- path to this transient's page

        **Usage:**

        ```django
        <a href="{{ transient.get_absolute_url }}">{{ transient.name }}</a>
        ```
        """
        return reverse("transient_detail", kwargs={"uuid": self.uuid})

    def crossmatch_tree(self):
        """*Sherlock's ranked matches, each carrying the matches merged into it*

        Sherlock records a source it matched in more than one catalogue as a
        single ranked "lead" row plus one child row per catalogue, the children
        pointing back at the lead through ``merged_rank``. This rebuilds that
        two-level shape in one query, so a template can list the ranked sources
        and reveal the individual matches behind any of them.

        Leads come back in rank order. A lead that merged nothing has an empty
        ``matches`` list.

        **Return:**

        - ``tree`` -- list of ``(lead, matches)`` pairs, best-ranked first

        **Usage:**

        ```django
        {% for lead, matches in transient.crossmatch_tree %}…{% endfor %}
        ```
        """
        # IMPORTED HERE, NOT AT MODULE LEVEL: apps.sherlock IMPORTS THIS MODULE,
        # SO IMPORTING IT BACK AT THE TOP WOULD BE A CIRCULAR IMPORT.
        from apps.sherlock.models import SherlockCrossmatch

        leads = []
        children = {}
        # ONE QUERY FOR EVERY ROW BELONGING TO THIS TRANSIENT — LEADS AND
        # CHILDREN TOGETHER — THEN SORTED OUT IN PYTHON, SO THE PAGE COSTS ONE
        # QUERY RATHER THAN ONE PER RANKED SOURCE.
        for match in SherlockCrossmatch.objects.filter(transient=self):
            if match.rank is not None:
                leads.append(match)
            elif match.merged_rank is not None:
                children.setdefault(match.merged_rank, []).append(match)

        leads.sort(key=lambda match: match.rank)
        return [(lead, children.get(lead.rank, [])) for lead in leads]
