from django.conf import settings
from django.db import models
from django.urls import reverse
from django_fundamentals.models import TimeStampedModel

from apps.transients.models import Transient

# THE FIVE VIEWS OF A RUN, IN THE ORDER THEY APPEAR AS TABS. THE VALUE IS THE
# URL SEGMENT; THE LABEL IS THE TAB'S TEXT.
TABS = (
    ("all", "All transients"),
    ("unvetted", "Unvetted"),
    ("correct", "Correct"),
    ("incorrect", "Incorrect"),
    ("ambiguous", "Ambiguous"),
)

# THE THREE VERDICTS A VETTER CAN GIVE. NULL ON sherlock_correct IS A FOURTH,
# IMPLICIT STATE — "UNVETTED" — SO IT IS NEVER ONE OF THESE STRINGS.
VERDICT_CORRECT = "correct"
VERDICT_INCORRECT = "incorrect"
VERDICT_AMBIGUOUS = "ambiguous"
VERDICT_CHOICES = [
    (VERDICT_CORRECT, "Correct"),
    (VERDICT_INCORRECT, "Incorrect"),
    (VERDICT_AMBIGUOUS, "Ambiguous"),
]

# THE TWO REASONS THAT MUST ALWAYS BE OFFERED. A CONSTANT RATHER THAN SEEDED
# ROWS, SO THEY ARE THERE FOR EVERY SHERLOCK VERSION — INCLUDING ONE NOBODY HAS
# VETTED YET — AND CANNOT BE DELETED OUT OF THE TABLE BY ACCIDENT. BOTH DRIVE
# EXTRA FIELDS ON THE FORM, SO THE STRINGS ARE NAMED AND COMPARED, NEVER TYPED
# OUT TWICE.
WRONG_RANK = "wrong rank"
WRONG_CLASSIFICATION = "correct association - incorrect classification"
# A SENTINEL, NOT A REASON: PICKING IT REVEALS A TEXT BOX, AND WHAT IS TYPED
# THERE IS WHAT GETS STORED AND OFFERED TO EVERYONE ELSE. IT IS NEVER SAVED.
OTHER_REASON = "other"
DEFAULT_REASONS = (WRONG_RANK, WRONG_CLASSIFICATION)


class SherlockVetting(TimeStampedModel):
    """*one person's verdict on how Sherlock classified one transient*

    There is a row per transient per Sherlock version, created up front by
    ``create_vetting_run`` with ``sherlock_correct`` left NULL. "Unvetted" is
    therefore a value rather than a missing row, which is what lets a version
    exist — and be listed and counted — before anyone has judged anything.

    **Usage:**

    ```python
    vetting = SherlockVetting.objects.get(transient=transient, sherlock_version="v0.0.0")
    vetting.sherlock_correct = VERDICT_CORRECT
    vetting.save()
    ```
    """

    # db_column KEEPS THE PHYSICAL COLUMNS AS SPECIFIED — transients_uuid AND
    # user — RATHER THAN DJANGO'S DEFAULT transient_id / user_id.
    transient = models.ForeignKey(
        Transient,
        on_delete=models.CASCADE,
        db_column="transients_uuid",
        related_name="vettings",
    )
    sherlock_version = models.CharField(max_length=15)
    # NULL MEANS "NOT YET VETTED", WHICH IS WHY THERE IS NO default.
    sherlock_correct = models.CharField(
        max_length=10, null=True, blank=True, choices=VERDICT_CHOICES, default=None
    )
    sherlock_correct_host = models.IntegerField(
        null=True,
        blank=True,
        help_text="Rank of the correct host among Sherlock's crossmatches.",
    )
    # WHY THE VERDICT WAS "incorrect". FREE TEXT RATHER THAN choices= BECAUSE THE
    # LIST GROWS AS VETTERS ADD TO IT — SEE VettingReason.
    incorrect_reason = models.CharField(
        max_length=100,
        blank=True,
        help_text="Why Sherlock got this transient wrong.",
    )
    corrected_classification = models.CharField(
        max_length=10,
        blank=True,
        help_text="What the classification should have been, when the association was right.",
    )
    # SET_NULL, NOT CASCADE: DELETING AN ACCOUNT MUST NOT DELETE ITS JUDGEMENTS.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="user",
        related_name="vettings",
    )
    user_comment = models.TextField(blank=True)

    class Meta:
        db_table = "sherlock_vetting"
        ordering = ["transient__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["transient", "sherlock_version"],
                name="uniq_vetting_transient_version",
            ),
        ]
        indexes = [
            # EVERY TAB QUERY FILTERS ON THIS PAIR
            models.Index(fields=["sherlock_version", "sherlock_correct"]),
        ]

    def __str__(self):
        return f"{self.transient.name} @ {self.sherlock_version}"

    @property
    def verdict(self):
        """*the vetting state as a short string*

        **Return:**

        - ``verdict`` -- "correct", "incorrect", "ambiguous" or "unvetted"

        **Usage:**

        ```django
        {{ vetting.verdict }}
        ```
        """
        return self.sherlock_correct or "unvetted"

    def get_absolute_url(self):
        """*the page where this transient is vetted for this version*

        **Return:**

        - ``url`` -- path to the vetting page

        **Usage:**

        ```django
        <a href="{{ vetting.get_absolute_url }}">vet</a>
        ```
        """
        return reverse(
            "vetting_transient",
            kwargs={"version": self.sherlock_version, "uuid": self.transient_id},
        )


class VettingReason(TimeStampedModel):
    """*a reason for rejecting a classification, offered to everyone vetting a version*

    Vetters type a reason once and it joins the dropdown for every transient in
    that run, for every user — so a team converges on a shared vocabulary rather
    than each person phrasing the same objection differently.

    Scoped to one Sherlock version on purpose: what goes wrong changes between
    releases, and a reason that mattered for one version is noise in the next.
    ``DEFAULT_REASONS`` are *not* stored here; they are always offered on top of
    whatever this table holds.

    **Usage:**

    ```python
    VettingReason.objects.get_or_create(sherlock_version="v0.0.0", reason="host is a star")
    ```
    """

    sherlock_version = models.CharField(max_length=15)
    reason = models.CharField(max_length=100)
    # SET_NULL, NOT CASCADE: DELETING AN ACCOUNT MUST NOT TAKE A REASON OTHERS
    # ARE NOW USING WITH IT.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vetting_reasons",
    )

    class Meta:
        db_table = "sherlock_vetting_reasons"
        ordering = ["reason"]
        constraints = [
            # ONE ROW PER REASON PER VERSION, WHICH IS WHAT LETS THE FORM SAVE
            # WITH get_or_create AND NEVER DUPLICATE.
            models.UniqueConstraint(
                fields=["sherlock_version", "reason"],
                name="uniq_vetting_reason_version",
            ),
        ]
        indexes = [
            models.Index(fields=["sherlock_version"]),
        ]

    def __str__(self):
        return f"{self.reason} @ {self.sherlock_version}"

    @classmethod
    def choices_for(cls, version):
        """*every reason offerable for a version, defaults first*

        **Key Arguments:**

        - ``version`` -- the Sherlock version being vetted

        **Return:**

        - ``choices`` -- list of (value, label) pairs for a ChoiceField

        **Usage:**

        ```python
        form.fields["incorrect_reason"].choices = VettingReason.choices_for("v0.0.0")
        ```
        """
        stored = cls.objects.filter(sherlock_version=version).values_list("reason", flat=True)
        # THE DEFAULTS LEAD, AND A STORED ROW THAT DUPLICATES ONE IS DROPPED
        # RATHER THAN SHOWN TWICE.
        reasons = list(DEFAULT_REASONS) + [reason for reason in stored if reason not in DEFAULT_REASONS]
        # "other" ALWAYS COMES LAST — IT IS THE WAY OUT OF THE LIST, NOT A MEMBER
        # OF IT.
        return [(reason, reason) for reason in reasons] + [(OTHER_REASON, "other…")]
