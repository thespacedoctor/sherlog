from django.db import models

from apps.transients.models import Transient

# THE ORDER SHERLOCK ITSELF PREFERS FILTERS IN WHEN IT PICKS THE ONE MAGNITUDE
# TO QUOTE FOR A SOURCE — SEE `filterPreference` IN sherlock's
# transient_classifier.py. THE FIRST ENTRY WITH A VALUE WINS. THE UNDERSCORED
# NAMES ARE THE SDSS/PanSTARRS FILTERS, WHOSE COLUMNS ARE LITERALLY `_r`, `_g`…
FILTER_PREFERENCE = (
    "R",
    "_r",
    "G",
    "V",
    "_g",
    "B",
    "I",
    "_i",
    "_z",
    "J",
    "H",
    "K",
    "U",
    "_u",
    "_y",
    "W1",
    "unkMag",
)

# classificationReliability IS STORED AS 1/2/3; SHERLOCK RENDERS THOSE AS WORDS
# WHEN IT WRITES AN ANNOTATION, SO THE SAME WORDS ARE USED HERE.
RELIABILITY_LABELS = {1: "synonym", 2: "association", 3: "annotation"}

# best_distance_flag RECORDS WHICH KIND OF DISTANCE WON.
DISTANCE_FLAG_LABELS = {
    "dd": "direct",
    "sz": "spec-z",
    "pz": "photo-z",
}


class SherlockCrossmatch(models.Model):
    """*one candidate host source Sherlock matched against a transient*

    A read-only mirror of Sherlock's own ``sherlock_crossmatches`` table.
    Sherlock creates and populates it; Django only ever selects from it, which
    is why the model is unmanaged and the foreign key carries no database
    constraint.

    Rows come in two kinds:

    - a **lead** row has ``rank`` set and ``merged_rank`` NULL. It is one
      distinct astrophysical source, ranked 1 (best) upwards.
    - a **child** row has ``rank`` NULL and ``merged_rank`` equal to its lead's
      ``rank``. It is one catalogue's individual match, merged into that lead.

    Sherlock merges entries lying within 2.5 arcsec of each other, and marks the
    resulting lead with ``catalogue_object_subtype = "multiple"``. Leads that
    merged nothing keep their catalogue's real subtype and have no children.

    **Usage:**

    ```python
    leads = SherlockCrossmatch.objects.filter(transient=transient, rank__isnull=False)
    ```
    """

    id = models.BigAutoField(primary_key=True)
    # NO REAL FOREIGN KEY EXISTS IN THE DATABASE — SHERLOCK WRITES THE TABLE
    # WITHOUT ONE — SO db_constraint=False STOPS DJANGO ASSUMING OTHERWISE, AND
    # DO_NOTHING STOPS IT CASCADING INTO A TABLE IT DOES NOT OWN.
    transient = models.ForeignKey(
        Transient,
        on_delete=models.DO_NOTHING,
        db_column="transient_object_id",
        related_name="crossmatches",
        db_constraint=False,
        null=True,
    )

    rank = models.IntegerField(null=True)
    merged_rank = models.IntegerField(null=True)
    rank_score = models.FloatField(db_column="rankScore", null=True)

    catalogue_object_id = models.CharField(max_length=200, null=True)
    catalogue_table_name = models.CharField(max_length=100, null=True)
    catalogue_object_type = models.CharField(max_length=45, null=True)
    catalogue_object_subtype = models.CharField(max_length=45, null=True)
    association_type = models.CharField(max_length=45, null=True)
    classification_reliability = models.IntegerField(
        db_column="classificationReliability", null=True
    )

    separation_arcsec = models.FloatField(db_column="separationArcsec", null=True)
    north_separation_arcsec = models.FloatField(db_column="northSeparationArcsec", null=True)
    east_separation_arcsec = models.FloatField(db_column="eastSeparationArcsec", null=True)
    physical_separation_kpc = models.FloatField(null=True)
    sm_axis_arcsec = models.FloatField(null=True)

    z = models.FloatField(null=True)
    photo_z = models.FloatField(db_column="photoZ", null=True)
    direct_distance = models.FloatField(null=True)
    best_distance = models.FloatField(null=True)
    best_distance_flag = models.CharField(max_length=100, null=True)
    best_distance_source = models.CharField(max_length=100, null=True)
    transient_abs_mag = models.FloatField(db_column="transientAbsMag", null=True)

    ra_deg = models.FloatField(db_column="raDeg", null=True)
    dec_deg = models.FloatField(db_column="decDeg", null=True)

    # THE PHOTOMETRY COLUMNS SHERLOCK CONSULTS WHEN IT QUOTES A MAGNITUDE.
    # DJANGO REJECTS FIELD NAMES STARTING WITH AN UNDERSCORE, SO THE SDSS/PS1
    # FILTERS ARE RENAMED AND POINTED BACK AT THEIR REAL COLUMNS.
    mag_R = models.FloatField(db_column="R", null=True)
    mag_r = models.FloatField(db_column="_r", null=True)
    mag_G = models.FloatField(db_column="G", null=True)
    mag_V = models.FloatField(db_column="V", null=True)
    mag_g = models.FloatField(db_column="_g", null=True)
    mag_B = models.FloatField(db_column="B", null=True)
    mag_I = models.FloatField(db_column="I", null=True)
    mag_i = models.FloatField(db_column="_i", null=True)
    mag_z = models.FloatField(db_column="_z", null=True)
    mag_J = models.FloatField(db_column="J", null=True)
    mag_H = models.FloatField(db_column="H", null=True)
    mag_K = models.FloatField(db_column="K", null=True)
    mag_U = models.FloatField(db_column="U", null=True)
    mag_u = models.FloatField(db_column="_u", null=True)
    mag_y = models.FloatField(db_column="_y", null=True)
    mag_W1 = models.FloatField(db_column="W1", null=True)
    mag_unk = models.FloatField(db_column="unkMag", null=True)

    class Meta:
        managed = False
        db_table = "sherlock_crossmatches"
        ordering = ["rank", "merged_rank", "id"]
        verbose_name_plural = "sherlock crossmatches"

    def __str__(self):
        return f"{self.catalogue_object_id} ({self.catalogue_table_name})"

    @property
    def is_merged(self):
        """*whether this lead row merges more than one catalogue entry*

        **Return:**

        - ``is_merged`` -- True when Sherlock marked the row "multiple"

        **Usage:**

        ```django
        {% if match.is_merged %}…{% endif %}
        ```
        """
        return self.catalogue_object_subtype == "multiple"

    @property
    def best_magnitude(self):
        """*the one magnitude worth quoting, and the filter it came from*

        Walks Sherlock's own filter preference order and returns the first
        filter carrying a value, so a single column can stand in for the 34
        magnitude and error columns on the table.

        **Return:**

        - ``best_magnitude`` -- a ``(filter, value)`` pair, or ``None``

        **Usage:**

        ```django
        {% with best=match.best_magnitude %}{{ best.0 }}={{ best.1 }}{% endwith %}
        ```
        """
        for filterName in FILTER_PREFERENCE:
            value = getattr(self, MAGNITUDE_FIELDS[filterName])
            if value is not None:
                return (filterName.lstrip("_"), value)
        return None

    @property
    def reliability_label(self):
        """*classificationReliability as the word Sherlock uses for it*

        **Return:**

        - ``reliability_label`` -- "synonym", "association", "annotation" or ""

        **Usage:**

        ```django
        {{ match.reliability_label }}
        ```
        """
        return RELIABILITY_LABELS.get(self.classification_reliability, "")

    @property
    def best_distance_label(self):
        """*which kind of distance ``best_distance`` was taken from*

        **Return:**

        - ``best_distance_label`` -- "direct", "spec-z", "photo-z" or ""

        **Usage:**

        ```django
        {{ match.best_distance_label }}
        ```
        """
        return DISTANCE_FLAG_LABELS.get(self.best_distance_flag, "")


# FILTER NAME -> THE MODEL FIELD HOLDING IT. DECLARED AFTER THE MODEL SO IT CAN
# NAME THE FIELDS ABOVE, AND USED BY best_magnitude.
MAGNITUDE_FIELDS = {filterName: f"mag_{filterName.lstrip('_')}" for filterName in FILTER_PREFERENCE}
MAGNITUDE_FIELDS["unkMag"] = "mag_unk"


class SherlockClassification(models.Model):
    """*Sherlock's verdict on one transient*

    A read-only mirror of Sherlock's ``sherlock_classifications`` table, which
    holds exactly one row per transient — the transient's id is its primary key.

    **Usage:**

    ```python
    classification = SherlockClassification.objects.get(transient=transient)
    ```
    """

    transient = models.OneToOneField(
        Transient,
        primary_key=True,
        on_delete=models.DO_NOTHING,
        db_column="transient_object_id",
        related_name="sherlock_result",
        db_constraint=False,
    )
    classification = models.CharField(max_length=45, null=True)
    # SHERLOCK WRITES THIS AS A SENTENCE OF HTML, LINKING THE MATCHED SOURCE TO
    # ITS CATALOGUE PAGE — SO THE TEMPLATE HAS TO RENDER IT UNESCAPED.
    annotation = models.TextField(null=True)
    summary = models.CharField(max_length=50, null=True)
    separation_arcsec = models.FloatField(db_column="separationArcsec", null=True)
    match_verified = models.IntegerField(db_column="matchVerified", null=True)

    class Meta:
        managed = False
        db_table = "sherlock_classifications"

    def __str__(self):
        return f"{self.transient_id}: {self.classification}"
