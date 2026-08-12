"""*the classification codes Sherlock can give a transient*

**This list is maintained by hand and there is no way around that.** Sherlock has
no single constant to import or mirror: the codes are free-text values of the
``synonym``/``association``/``annotation`` keys on each catalogue search module in
its ``advanced_settings.yaml``, with ``ORPHAN`` hard-coded in Python and no
code-to-English mapping anywhere in the package. A site running a modified
settings file can invent codes Sherlock core has never seen, which is why
anything reading a stored classification must tolerate one that is not here —
see ``classification_label``.

Checked against sherlock 3.1.0. Watch its ``CHANGES.md`` on upgrade: ``HPMS``
arrived in a point release, and ``UNCLEAR`` changed reliability band in another.
"""

# CODE -> WHAT IT MEANS, IN THE ORDER A VETTER IS LIKELIEST TO WANT THEM.
SHERLOCK_CLASSIFICATIONS = (
    ("SN", "SN — supernova"),
    ("NT", "NT — nuclear transient"),
    ("AGN", "AGN — active galactic nucleus"),
    ("VS", "VS — variable star"),
    ("CV", "CV — cataclysmic variable"),
    ("BS", "BS — bright-star artefact"),
    ("HPMS", "HPMS — high proper motion star"),
    ("UNCLEAR", "UNCLEAR — matched, but the source type is ambiguous"),
    ("ORPHAN", "ORPHAN — no catalogued match"),
)

CLASSIFICATION_LABELS = dict(SHERLOCK_CLASSIFICATIONS)


def classification_label(code):
    """*the human-readable name for a classification code*

    Falls back to the code itself, because Sherlock's vocabulary lives in a
    user-editable settings file and can grow without this module knowing.

    **Key Arguments:**

    - ``code`` -- a Sherlock classification code, e.g. "SN"

    **Return:**

    - ``label`` -- the readable name, or the code unchanged

    **Usage:**

    ```python
    classification_label("SN")
    ```
    """
    return CLASSIFICATION_LABELS.get(code, code or "")
