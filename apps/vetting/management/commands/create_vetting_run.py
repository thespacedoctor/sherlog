"""*open a vetting run for a Sherlock version*

**Usage:**

```bash
python manage.py create_vetting_run v0.0.0
```
"""

from django.core.management.base import BaseCommand, CommandError

from apps.transients.models import Transient
from apps.vetting.models import SherlockVetting


class Command(BaseCommand):
    help = "Create the unvetted rows for a Sherlock version, one per transient."

    def add_arguments(self, parser):
        # POSITIONAL, NOT --version: THAT FLAG IS TAKEN BY DJANGO ITSELF, WHICH
        # USES IT TO PRINT THE DJANGO VERSION.
        parser.add_argument(
            "sherlock_version",
            help="The Sherlock version being vetted, e.g. v0.0.0.",
        )

    def handle(self, *args, **options):
        version = options["sherlock_version"].strip()

        maxLength = SherlockVetting._meta.get_field("sherlock_version").max_length
        if not version:
            raise CommandError("the Sherlock version cannot be blank")
        if len(version) > maxLength:
            raise CommandError(f"the Sherlock version must be {maxLength} characters or fewer")

        transients = Transient.objects.all()
        if not transients.exists():
            raise CommandError("there are no transients to vet — import some first")

        before = SherlockVetting.objects.filter(sherlock_version=version).count()

        # ignore_conflicts LEANS ON THE (transient, sherlock_version) UNIQUE
        # CONSTRAINT, SO RE-RUNNING ONLY FILLS IN TRANSIENTS ADDED SINCE AND
        # NEVER DISTURBS A VERDICT ALREADY RECORDED.
        SherlockVetting.objects.bulk_create(
            [
                SherlockVetting(transient=transient, sherlock_version=version)
                for transient in transients
            ],
            ignore_conflicts=True,
        )

        after = SherlockVetting.objects.filter(sherlock_version=version).count()
        created = after - before

        self.stdout.write(
            self.style.SUCCESS(
                f"{created} created, {before} already present — {after} transients to vet for {version}"
            )
        )
