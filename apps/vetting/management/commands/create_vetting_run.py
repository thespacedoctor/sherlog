"""*open a vetting run for a Sherlock version*

**Usage:**

```bash
python manage.py create_vetting_run           # one run per version Sherlock has classified
python manage.py create_vetting_run v3.1.0    # just that one
```
"""

from django.core.management.base import BaseCommand, CommandError

from apps.sherlock.models import SherlockClassification
from apps.vetting.models import SherlockVetting


class Command(BaseCommand):
    help = "Create the unvetted rows for a Sherlock version, one per transient it classified."

    def add_arguments(self, parser):
        # POSITIONAL, NOT --version: THAT FLAG IS TAKEN BY DJANGO ITSELF, WHICH
        # USES IT TO PRINT THE DJANGO VERSION. OPTIONAL, BECAUSE SHERLOCK NOW
        # STAMPS THE VERSION ON ITS OWN OUTPUT AND TYPING ONE IN IS HOW RUNS
        # ENDED UP NAMED AFTER VERSIONS THAT NEVER EXISTED.
        parser.add_argument(
            "sherlock_version",
            nargs="?",
            help="The Sherlock version to open a run for. Omit to open one per version found.",
        )

    def handle(self, *args, **options):
        maxLength = SherlockVetting._meta.get_field("sherlock_version").max_length
        version = (options["sherlock_version"] or "").strip()

        if version and len(version) > maxLength:
            raise CommandError(f"the Sherlock version must be {maxLength} characters or fewer")

        versions = [version] if version else self.classified_versions()
        if not versions:
            raise CommandError(
                "Sherlock has not classified anything — run it first, or name a version explicitly"
            )

        for version in versions:
            self.open_run(version, maxLength)

    def classified_versions(self):
        """*every Sherlock version present in the classifications table*

        **Return:**

        - ``versions`` -- sorted list of version strings

        **Usage:**

        ```python
        versions = Command().classified_versions()
        ```
        """
        return sorted(
            version
            for version in SherlockClassification.objects.values_list(
                "sherlock_version", flat=True
            ).distinct()
            if version
        )

    def open_run(self, version, maxLength):
        """*create the unvetted rows for one version*

        **Key Arguments:**

        - ``version`` -- the Sherlock version being vetted
        - ``maxLength`` -- how long the version column allows a version to be
        """
        if len(version) > maxLength:
            raise CommandError(
                f"Sherlock reports version {version!r}, which is longer than the "
                f"{maxLength} characters the vetting table allows"
            )

        # ONLY THE TRANSIENTS THIS VERSION ACTUALLY CLASSIFIED. A RUN IS A
        # JUDGEMENT ON ONE VERSION'S WORK, SO IT COVERS THAT VERSION'S WORK.
        transientIds = SherlockClassification.objects.filter(sherlock_version=version).values_list(
            "transient_id", flat=True
        )
        if not transientIds:
            raise CommandError(f"Sherlock {version} has not classified anything")

        before = SherlockVetting.objects.filter(sherlock_version=version).count()

        # ignore_conflicts LEANS ON THE (transient, sherlock_version) UNIQUE
        # CONSTRAINT, SO RE-RUNNING ONLY FILLS IN TRANSIENTS ADDED SINCE AND
        # NEVER DISTURBS A VERDICT ALREADY RECORDED.
        SherlockVetting.objects.bulk_create(
            [
                SherlockVetting(transient_id=transientId, sherlock_version=version)
                for transientId in transientIds
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
