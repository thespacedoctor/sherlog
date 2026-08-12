"""*import transients from a broker CSV export*

**Usage:**

```bash
python manage.py import_transients                      # the bundled Lasair COSMOS sample
python manage.py import_transients other.csv --origin-name ztf
python manage.py import_transients --dry-run
```
"""

import csv
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.transients.models import Transient

# THE SAMPLE SHIPPED WITH THE APP, SO A FRESH CHECKOUT HAS SOMETHING TO BROWSE.
DEFAULT_CSV = Path(__file__).resolve().parents[2] / "data" / "sherlog_transient_sample.csv"
DEFAULT_ORIGIN_NAME = "lasair filter"

# MODEL FIELD -> CSV HEADERS THAT MAY SUPPLY IT, IN ORDER OF PREFERENCE. BROKER
# EXPORTS DISAGREE ON dec/decl AND url/uurl, SO BOTH SPELLINGS ARE ACCEPTED.
COLUMN_ALIASES = {
    "name": ("diaObjectId", "objectId", "name"),
    "ra": ("ra", "ramean"),
    "decl": ("decl", "dec", "decmean"),
    "url": ("uurl", "url"),
    # `origin` IS KEPT AS AN ALIAS FOR origin_url BECAUSE THAT IS WHAT THE
    # BUNDLED SAMPLE'S HEADER SAYS, AND ITS VALUES ARE ALREADY FILTER URLS.
    "origin_url": ("origin_url", "origin", "survey", "broker"),
    "origin_name": ("origin_name",),
}
# THE REST ARE OPTIONAL: url MAY BE BLANK, AND A MISSING OR EMPTY origin COLUMN
# FALLS BACK TO --origin-url / --origin-name, SO A ONE-FILTER EXPORT NEEDS
# NEITHER COLUMN.
REQUIRED_FIELDS = ("name", "ra", "decl")


class Command(BaseCommand):
    help = "Import transients from a broker CSV export (defaults to the bundled Lasair COSMOS sample)."

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_path",
            nargs="?",
            default=str(DEFAULT_CSV),
            help=f"CSV to import. Defaults to {DEFAULT_CSV.name}.",
        )
        parser.add_argument(
            "--origin-name",
            default=DEFAULT_ORIGIN_NAME,
            help=f"Name used for any row without one of its own. Default: {DEFAULT_ORIGIN_NAME}.",
        )
        parser.add_argument(
            "--origin-url",
            default="",
            help="URL used for any row without one of its own.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate the file, then roll back without writing.",
        )

    def handle(self, *args, **options):
        csvPath = Path(options["csv_path"])
        origins = {"origin_name": options["origin_name"], "origin_url": options["origin_url"]}
        dryRun = options["dry_run"]

        if not csvPath.is_file():
            raise CommandError(f"no such file: {csvPath}")
        for field, value in origins.items():
            maxLength = Transient._meta.get_field(field).max_length
            if len(value) > maxLength:
                raise CommandError(f"--{field.replace('_', '-')} must be {maxLength} characters or fewer")

        created, updated, skipped = self.import_csv(csvPath, origins, dryRun)

        summary = f"{created} created, {updated} updated, {skipped} skipped — from {csvPath.name}"
        if dryRun:
            self.stdout.write(self.style.WARNING(f"DRY RUN (rolled back): {summary}"))
        else:
            self.stdout.write(self.style.SUCCESS(summary))

    def import_csv(self, csvPath, origins, dryRun):
        """*read the CSV and upsert one transient per row*

        **Key Arguments:**

        - ``csvPath`` -- ``Path`` of the CSV to read
        - ``origins`` -- fallback origin_name/origin_url for rows without their own
        - ``dryRun`` -- roll the transaction back instead of committing

        **Return:**

        - ``created`` -- count of transients added
        - ``updated`` -- count of existing transients refreshed
        - ``skipped`` -- count of unusable rows

        **Usage:**

        ```python
        created, updated, skipped = self.import_csv(csvPath, "lasair", False)
        ```
        """
        created = 0
        updated = 0
        skipped = 0

        with csvPath.open(newline="", encoding="utf-8-sig") as csvFile:
            reader = csv.DictReader(csvFile)
            columns = self.resolve_columns(reader.fieldnames or [])

            # ONE TRANSACTION FOR THE WHOLE FILE: A FAILURE HALFWAY THROUGH
            # LEAVES NOTHING BEHIND, AND --dry-run IS JUST A ROLLBACK.
            with transaction.atomic():
                for lineNumber, row in enumerate(reader, start=2):
                    values = self.clean_row(row, columns, lineNumber, origins)
                    if values is None:
                        skipped += 1
                        continue

                    transient, wasCreated = Transient.objects.update_or_create(
                        name=values["name"],
                        origin_url=values["origin_url"],
                        defaults={
                            "ra": values["ra"],
                            "decl": values["decl"],
                            "url": values["url"],
                            "origin_name": values["origin_name"],
                        },
                    )
                    created += 1 if wasCreated else 0
                    updated += 0 if wasCreated else 1

                if dryRun:
                    transaction.set_rollback(True)

        return created, updated, skipped

    def resolve_columns(self, fieldnames):
        """*match the CSV's headers onto model field names*

        **Key Arguments:**

        - ``fieldnames`` -- the header row as read by ``csv.DictReader``

        **Return:**

        - ``columns`` -- dict of model field name -> CSV header

        **Usage:**

        ```python
        columns = self.resolve_columns(reader.fieldnames)
        ```
        """
        columns = {}
        for field, aliases in COLUMN_ALIASES.items():
            for alias in aliases:
                if alias in fieldnames:
                    columns[field] = alias
                    break

        missing = [field for field in REQUIRED_FIELDS if field not in columns]
        if missing:
            raise CommandError(
                "CSV is missing a column for: "
                + ", ".join(f"{field} (any of {'/'.join(COLUMN_ALIASES[field])})" for field in missing)
                + f". Found: {', '.join(fieldnames)}"
            )
        return columns

    def clean_row(self, row, columns, lineNumber, fallbackOrigins):
        """*parse and validate one CSV row*

        A bad row is reported and skipped rather than aborting the import — a
        single malformed coordinate in a 900-row export should not cost the
        other 899.

        **Key Arguments:**

        - ``row`` -- one row from ``csv.DictReader``
        - ``columns`` -- model field name -> CSV header, from ``resolve_columns``
        - ``lineNumber`` -- the row's line in the file, for the warning message
        - ``fallbackOrigins`` -- origin_name/origin_url for rows whose own cells are blank

        **Return:**

        - ``values`` -- dict of name/ra/decl/url/origin_name/origin_url, or ``None``

        **Usage:**

        ```python
        values = self.clean_row(row, columns, 2, "lasair")
        ```
        """
        name = (row.get(columns["name"]) or "").strip()
        if not name:
            self.stderr.write(self.style.WARNING(f"line {lineNumber}: blank name — skipped"))
            return None

        try:
            ra = float(row[columns["ra"]])
            decl = float(row[columns["decl"]])
        except (TypeError, ValueError):
            self.stderr.write(
                self.style.WARNING(f"line {lineNumber}: {name} has unparsable coordinates — skipped")
            )
            return None

        url = (row.get(columns.get("url", ""), "") or "").strip()
        # A ROW'S OWN VALUE WINS; A BLANK CELL — OR NO COLUMN AT ALL — FALLS BACK
        # TO --origin-name / --origin-url.
        values = {"name": name, "ra": ra, "decl": decl, "url": url}
        for field, fallback in fallbackOrigins.items():
            values[field] = (row.get(columns.get(field, ""), "") or "").strip() or fallback

        # RUN THE MODEL'S OWN VALIDATORS (RA/DEC RANGES, FIELD LENGTHS) — .save()
        # ALONE WOULD NOT. BOTH UNIQUENESS CHECKS ARE OFF: update_or_create OWNS
        # (name, origin_url), AND validate_constraints WOULD OTHERWISE REJECT EVERY
        # ROW OF A RE-IMPORT VIA THE UniqueConstraint.
        candidate = Transient(**values)
        try:
            candidate.full_clean(validate_unique=False, validate_constraints=False)
        except ValidationError as error:
            self.stderr.write(
                self.style.WARNING(f"line {lineNumber}: {name} failed validation ({error.messages[0]}) — skipped")
            )
            return None

        return values
