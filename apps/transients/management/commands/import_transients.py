"""*import transients from a broker CSV export*

**Usage:**

```bash
python manage.py import_transients                      # the bundled Lasair COSMOS sample
python manage.py import_transients other.csv --origin ztf
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
DEFAULT_CSV = Path(__file__).resolve().parents[2] / "data" / "lasair_cosmos_sample.csv"
DEFAULT_ORIGIN = "lasair"

# MODEL FIELD -> CSV HEADERS THAT MAY SUPPLY IT, IN ORDER OF PREFERENCE. BROKER
# EXPORTS DISAGREE ON dec/decl AND url/uurl, SO BOTH SPELLINGS ARE ACCEPTED.
COLUMN_ALIASES = {
    "name": ("diaObjectId", "objectId", "name"),
    "ra": ("ra", "ramean"),
    "decl": ("decl", "dec", "decmean"),
    "url": ("uurl", "url"),
}
# EVERY FIELD ABOVE EXCEPT url, WHICH IS ALLOWED TO BE BLANK.
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
            "--origin",
            default=DEFAULT_ORIGIN,
            help=f"Value written to every row's origin field. Default: {DEFAULT_ORIGIN}.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate the file, then roll back without writing.",
        )

    def handle(self, *args, **options):
        csvPath = Path(options["csv_path"])
        origin = options["origin"]
        dryRun = options["dry_run"]

        if not csvPath.is_file():
            raise CommandError(f"no such file: {csvPath}")
        if len(origin) > 30:
            raise CommandError("--origin must be 30 characters or fewer")

        created, updated, skipped = self.import_csv(csvPath, origin, dryRun)

        summary = f"{created} created, {updated} updated, {skipped} skipped — from {csvPath.name}"
        if dryRun:
            self.stdout.write(self.style.WARNING(f"DRY RUN (rolled back): {summary}"))
        else:
            self.stdout.write(self.style.SUCCESS(summary))

    def import_csv(self, csvPath, origin, dryRun):
        """*read the CSV and upsert one transient per row*

        **Key Arguments:**

        - ``csvPath`` -- ``Path`` of the CSV to read
        - ``origin`` -- the origin value written to every row
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
                    values = self.clean_row(row, columns, lineNumber)
                    if values is None:
                        skipped += 1
                        continue

                    transient, wasCreated = Transient.objects.update_or_create(
                        name=values["name"],
                        origin=origin,
                        defaults={
                            "ra": values["ra"],
                            "decl": values["decl"],
                            "url": values["url"],
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

    def clean_row(self, row, columns, lineNumber):
        """*parse and validate one CSV row*

        A bad row is reported and skipped rather than aborting the import — a
        single malformed coordinate in a 900-row export should not cost the
        other 899.

        **Key Arguments:**

        - ``row`` -- one row from ``csv.DictReader``
        - ``columns`` -- model field name -> CSV header, from ``resolve_columns``
        - ``lineNumber`` -- the row's line in the file, for the warning message

        **Return:**

        - ``values`` -- dict of name/ra/decl/url, or ``None`` if unusable

        **Usage:**

        ```python
        values = self.clean_row(row, columns, 2)
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

        values = {"name": name, "ra": ra, "decl": decl, "url": url}

        # RUN THE MODEL'S OWN VALIDATORS (RA/DEC RANGES, FIELD LENGTHS) — .save()
        # ALONE WOULD NOT. name/origin UNIQUENESS IS HANDLED BY update_or_create,
        # SO IT IS EXCLUDED FROM THE CHECK.
        candidate = Transient(origin="", **values)
        try:
            candidate.full_clean(exclude=["origin"], validate_unique=False)
        except ValidationError as error:
            self.stderr.write(
                self.style.WARNING(f"line {lineNumber}: {name} failed validation ({error.messages[0]}) — skipped")
            )
            return None

        return values
