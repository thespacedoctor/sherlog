from django import forms

from apps.sherlock.classifications import SHERLOCK_CLASSIFICATIONS
from apps.vetting.models import (
    OTHER_REASON,
    VERDICT_CHOICES,
    VERDICT_INCORRECT,
    WRONG_CLASSIFICATION,
    WRONG_RANK,
    VettingReason,
)


class VettingForm(forms.Form):
    """*a person's verdict on one transient for one Sherlock version*

    The verdict itself comes from which submit button was pressed, so it is
    validated here rather than rendered as a widget.

    Every field but the verdict is optional at field level, because which ones
    apply depends on the answers given: a "correct" verdict needs nothing else,
    while "incorrect" needs a reason, and some reasons need one more answer
    still. ``clean`` enforces that chain, and the template reveals exactly the
    same fields in the same order — so the rules hold whether or not JavaScript
    is running.

    **Usage:**

    ```python
    form = VettingForm(request.POST, transient=transient, version="v0.0.0")
    if form.is_valid():
        vetting.sherlock_correct = form.cleaned_data["sherlock_correct"]
    ```
    """

    verdict = forms.ChoiceField(choices=VERDICT_CHOICES)
    user_comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Anything worth noting? (optional)"}),
        label="Comment",
    )
    incorrect_reason = forms.ChoiceField(
        required=False,
        label="Why is it wrong?",
    )
    new_reason = forms.CharField(
        required=False,
        max_length=100,
        label="What is the reason?",
        help_text="Kept for this Sherlock version and offered to everyone vetting it.",
    )
    sherlock_correct_host = forms.ChoiceField(
        required=False,
        label="Rank of the correct host",
        help_text="Which of Sherlock's ranked crossmatches was the real host.",
    )
    corrected_classification = forms.ChoiceField(
        required=False,
        choices=[("", "---------"), *SHERLOCK_CLASSIFICATIONS],
        label="What should it have been?",
    )

    def __init__(self, *args, transient=None, version=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.transient = transient
        self.version = version

        # BOTH DROPDOWNS ARE POPULATED PER TRANSIENT AND PER RUN, SO THEY CANNOT
        # BE DECLARED ON THE CLASS.
        self.fields["incorrect_reason"].choices = [
            ("", "---------"),
            *(VettingReason.choices_for(version) if version else []),
        ]
        self.fields["sherlock_correct_host"].choices = [("", "---------"), *self.host_rank_choices()]

    def host_rank_choices(self):
        """*the ranks Sherlock gave this transient's candidate hosts*

        **Return:**

        - ``choices`` -- (rank, label) pairs, best-ranked first

        **Usage:**

        ```python
        self.fields["sherlock_correct_host"].choices = form.host_rank_choices()
        ```
        """
        if self.transient is None:
            return []
        return [
            (str(lead.rank), f"{lead.rank} — {lead.catalogue_object_id or 'unnamed'} ({lead.catalogue_table_name})")
            for lead, matches in self.transient.crossmatch_tree()
        ]

    def clean_sherlock_correct_host(self):
        """*the host rank as an integer, since the widget hands back a string*"""
        rank = self.cleaned_data.get("sherlock_correct_host")
        return int(rank) if rank else None

    def clean(self):
        cleanedData = super().clean()
        verdict = cleanedData.get("verdict")
        # THE MODEL FIELD STORES THE VERDICT STRING DIRECTLY.
        cleanedData["sherlock_correct"] = verdict or None

        chosen = cleanedData.get("incorrect_reason") or ""
        typed = (cleanedData.get("new_reason") or "").strip()
        # "other" IS A SENTINEL, NOT A REASON — WHAT WAS TYPED REPLACES IT.
        reason = typed if chosen == OTHER_REASON else chosen
        cleanedData["reason"] = reason

        # ONLY AN INCORRECT VERDICT ASKS FURTHER QUESTIONS. CORRECT AND
        # AMBIGUOUS BOTH STOP HERE.
        if verdict != VERDICT_INCORRECT:
            return cleanedData

        # EACH ANSWER DECIDES WHETHER THERE IS A NEXT QUESTION, MIRRORING WHAT
        # THE TEMPLATE REVEALS.
        if not chosen:
            self.add_error("incorrect_reason", "Say why Sherlock got this wrong.")
        elif chosen == OTHER_REASON and not typed:
            self.add_error("new_reason", "Give the reason.")
        elif chosen == WRONG_RANK and not cleanedData.get("sherlock_correct_host"):
            self.add_error("sherlock_correct_host", "Choose which rank was the correct host.")
        elif chosen == WRONG_CLASSIFICATION and not cleanedData.get("corrected_classification"):
            self.add_error("corrected_classification", "Choose what the classification should have been.")

        return cleanedData
