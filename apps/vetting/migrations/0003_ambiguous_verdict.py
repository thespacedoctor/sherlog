# Generated manually: converts sherlock_correct from a boolean to a tri-state
# CharField ("correct" / "incorrect" / "ambiguous", NULL still means unvetted).

from django.db import migrations, models


def bool_to_verdict(apps, schema_editor):
    SherlockVetting = apps.get_model("vetting", "SherlockVetting")
    SherlockVetting.objects.filter(sherlock_correct_bool=True).update(sherlock_correct="correct")
    SherlockVetting.objects.filter(sherlock_correct_bool=False).update(sherlock_correct="incorrect")


def verdict_to_bool(apps, schema_editor):
    SherlockVetting = apps.get_model("vetting", "SherlockVetting")
    SherlockVetting.objects.filter(sherlock_correct="correct").update(sherlock_correct_bool=True)
    SherlockVetting.objects.filter(sherlock_correct="incorrect").update(sherlock_correct_bool=False)
    # "ambiguous" HAS NO BOOLEAN EQUIVALENT, SO IT REVERTS TO NULL ("unvetted").


class Migration(migrations.Migration):

    dependencies = [
        ("vetting", "0002_add_vetting_reason"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="sherlockvetting",
            name="sherlock_ve_sherloc_24008c_idx",
        ),
        migrations.RenameField(
            model_name="sherlockvetting",
            old_name="sherlock_correct",
            new_name="sherlock_correct_bool",
        ),
        migrations.AddField(
            model_name="sherlockvetting",
            name="sherlock_correct",
            field=models.CharField(
                blank=True,
                choices=[
                    ("correct", "Correct"),
                    ("incorrect", "Incorrect"),
                    ("ambiguous", "Ambiguous"),
                ],
                default=None,
                max_length=10,
                null=True,
            ),
        ),
        migrations.RunPython(bool_to_verdict, verdict_to_bool),
        migrations.RemoveField(
            model_name="sherlockvetting",
            name="sherlock_correct_bool",
        ),
        migrations.AddIndex(
            model_name="sherlockvetting",
            index=models.Index(
                fields=["sherlock_version", "sherlock_correct"],
                name="sherlock_ve_sherloc_24008c_idx",
            ),
        ),
    ]
