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
        origin_name="lasair filter",
        origin_url="https://lasair.lsst.ac.uk/filters/1254/",
        ra=148.61201,
        decl=1.609392,
        url="https://lasair.lsst.ac.uk/objects/313853517460144141",
    )
    ```
    """

    # FILLED IN BY crossmatch_tree() THE FIRST TIME IT RUNS, SO THE TABLE AND THE
    # SKY VIEW SHARE ONE QUERY RATHER THAN REPEATING IT. KEYED BY VERSION, SO A
    # PAGE CANNOT BE SERVED ONE VERSION'S TREE FROM A CACHE ANOTHER FILLED.
    _crossmatch_tree = None
    _crossmatch_tree_version = None
    # SET BY THE VETTING VIEW TO PIN THE PAGE TO ITS RUN'S SHERLOCK VERSION. LEFT
    # UNSET ELSEWHERE, WHERE THE NEWEST VERSION PRESENT IS THE RIGHT ANSWER.
    crossmatch_version = None

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
    # WHERE THE TRANSIENT CAME FROM, SPLIT IN TWO: THE URL IDENTIFIES THE BROKER
    # FILTER EXACTLY AND IS WHAT ROWS ARE MADE UNIQUE ON, WHILE THE NAME IS THE
    # ONLY PART WORTH SHOWING A HUMAN.
    origin_name = models.CharField(
        max_length=75,
        blank=True,
        help_text="Human-readable name for where the transient came from, e.g. 'lasair filter'.",
    )
    origin_url = models.URLField(
        max_length=200,
        blank=True,
        help_text="The broker filter or feed that selected this transient.",
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
            # ONE ROW PER OBJECT PER BROKER FILTER. THIS IS WHAT MAKES THE
            # IMPORTER IDEMPOTENT — RE-RUNNING IT UPDATES RATHER THAN DUPLICATES.
            models.UniqueConstraint(fields=["name", "origin_url"], name="uniq_transient_name_origin_url"),
        ]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["origin_name"]),
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

        version = self.crossmatch_version

        # THE PAGE ASKS FOR THIS TWICE — ONCE FOR THE TABLE, ONCE FOR THE SKY
        # VIEW'S CIRCLES — AND BOTH WANT THE SAME ROWS. THE KEY IS THE VERSION
        # *ASKED FOR*, NOT THE ONE RESOLVED: CACHING THE RESOLVED VALUE WOULD
        # MISS EVERY TIME, SINCE THE SECOND CALLER ASKS WITH None AGAIN.
        if self._crossmatch_tree is not None and self._crossmatch_tree_version == version:
            return self._crossmatch_tree
        requestedVersion = version

        # EVERY ROW FOR THIS TRANSIENT, WHATEVER ITS VERSION, IN ONE QUERY — THEN
        # THE VERSION IS PICKED AND THE ROWS SORTED IN PYTHON. FETCHING THE LOT
        # AND FILTERING HERE COSTS ONE QUERY WHERE ASKING THE DATABASE FOR THE
        # LATEST VERSION FIRST WOULD COST TWO, AND A TRANSIENT HAS AT MOST A FEW
        # DOZEN MATCHES.
        matches = list(SherlockCrossmatch.objects.filter(transient=self))
        if version is None and matches:
            # THE VERSION ON THE HIGHEST id — THE LAST ROW WRITTEN. NOT A SORT OF
            # THE VERSION STRINGS: v3.10.0 SORTS BELOW v3.1.0 ALPHABETICALLY.
            version = max(matches, key=lambda match: match.id).sherlock_version

        leads = []
        children = {}
        for match in matches:
            if match.sherlock_version != version:
                continue
            if match.rank is not None:
                leads.append(match)
            elif match.merged_rank is not None:
                children.setdefault(match.merged_rank, []).append(match)

        leads.sort(key=lambda match: match.rank)
        self._crossmatch_tree = [(lead, children.get(lead.rank, [])) for lead in leads]
        self._crossmatch_tree_version = requestedVersion
        return self._crossmatch_tree

    def crossmatch_overlays(self):
        """*the circles the sky view draws, one per matched source*

        Each record is a circle: where the source is, and the radius Sherlock
        searched to find it — so the circle is the association boundary the
        transient fell inside. ``lead`` records are the ranked sources; the
        others are the individual catalogue matches merged into them, which the
        sky view only shows when asked for all sources.

        **Return:**

        - ``overlays`` -- list of dicts, JSON-ready

        **Usage:**

        ```django
        {{ transient.crossmatch_overlays|json_script:"sky-view-crossmatches" }}
        ```
        """
        overlays = []
        for lead, matches in self.crossmatch_tree():
            # A MERGED LEAD HAS NO RADIUS OF ITS OWN — SHERLOCK OVERWROTE IT WITH
            # "multiple", WHICH LANDS IN THE double COLUMN AS 0 — SO THE TIGHTEST
            # OF THE SEARCHES THAT FOUND ITS PARTS STANDS IN FOR IT.
            childRadii = [match.original_search_radius_arcsec for match in matches if match.original_search_radius_arcsec]
            leadRadius = lead.original_search_radius_arcsec or (min(childRadii) if childRadii else None)

            circles = [(lead, True, leadRadius)]
            circles += [(match, False, match.original_search_radius_arcsec) for match in matches]

            for match, isLead, radius in circles:
                # EVERY COLUMN ON THE SHERLOCK MIRROR IS NULLABLE, AND A CIRCLE
                # WITH NO CENTRE OR NO RADIUS IS NOT A CIRCLE.
                if match.ra_deg is None or match.dec_deg is None or not radius:
                    continue
                overlays.append(
                    {
                        "rank": lead.rank,
                        "isLead": isLead,
                        "ra": match.ra_deg,
                        "dec": match.dec_deg,
                        "radiusArcsec": radius,
                        # THE SOURCE'S OWN EXTENT, DRAWN DASHED. OFTEN ABSENT —
                        # ONLY GALAXY CATALOGUES CARRY A SEMI-MAJOR AXIS.
                        "smAxisArcsec": match.sm_axis_arcsec,
                        "colourToken": lead.rank_colour_token,
                        "label": match.catalogue_object_id or "",
                        "catalogue": match.catalogue_table_name or "",
                    }
                )
        return overlays
