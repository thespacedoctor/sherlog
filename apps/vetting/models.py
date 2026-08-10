from django.conf import settings
from django.db import models
from django.urls import reverse
from django_fundamentals.models import TimeStampedModel

from apps.transients.models import Transient

# THE FOUR VIEWS OF A RUN, IN THE ORDER THEY APPEAR AS TABS. THE VALUE IS THE
# URL SEGMENT; THE LABEL IS THE TAB'S TEXT.
TABS = (
    ("all", "All transients"),
    ("unvetted", "Unvetted"),
    ("correct", "Correct"),
    ("incorrect", "Incorrect"),
)


class SherlockVetting(TimeStampedModel):
    """*one person's verdict on how Sherlock classified one transient*

    There is a row per transient per Sherlock version, created up front by
    ``create_vetting_run`` with ``sherlock_correct`` left NULL. "Unvetted" is
    therefore a value rather than a missing row, which is what lets a version
    exist — and be listed and counted — before anyone has judged anything.

    **Usage:**

    ```python
    vetting = SherlockVetting.objects.get(transient=transient, sherlock_version="v0.0.0")
    vetting.sherlock_correct = True
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
    # NULL MEANS "NOT YET VETTED", WHICH IS WHY THERE IS NO default=False.
    sherlock_correct = models.BooleanField(null=True, default=None)
    sherlock_correct_host = models.IntegerField(
        null=True,
        blank=True,
        help_text="Rank of the correct host among Sherlock's crossmatches.",
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

        - ``verdict`` -- "correct", "incorrect" or "unvetted"

        **Usage:**

        ```django
        {{ vetting.verdict }}
        ```
        """
        if self.sherlock_correct is None:
            return "unvetted"
        return "correct" if self.sherlock_correct else "incorrect"

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
