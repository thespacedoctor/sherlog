from django import forms

# THE SUBMIT BUTTONS SHARE ONE FORM AND ARE TOLD APART BY THIS FIELD'S VALUE.
VERDICTS = {"correct": True, "incorrect": False}


class VettingForm(forms.Form):
    """*a person's verdict on one transient for one Sherlock version*

    The verdict itself comes from which submit button was pressed, so it is
    validated here rather than rendered as a widget.

    **Usage:**

    ```python
    form = VettingForm(request.POST)
    if form.is_valid():
        vetting.sherlock_correct = form.cleaned_data["sherlock_correct"]
    ```
    """

    verdict = forms.ChoiceField(choices=[(key, key) for key in VERDICTS])
    user_comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Anything worth noting? (optional)"}),
        label="Comment",
    )
    sherlock_correct_host = forms.IntegerField(
        required=False,
        min_value=1,
        label="Rank of the correct host",
        help_text="Optional — which of Sherlock's ranked crossmatches was the real host.",
    )

    def clean(self):
        cleanedData = super().clean()
        verdict = cleanedData.get("verdict")
        if verdict:
            cleanedData["sherlock_correct"] = VERDICTS[verdict]
        return cleanedData
