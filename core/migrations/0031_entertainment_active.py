"""Activate entertainment PlaceCategory so it appears on the main screen."""
from django.db import migrations


def activate(apps, schema_editor):
    PlaceCategory = apps.get_model("core", "PlaceCategory")
    PlaceCategory.objects.filter(slug="entertainment").update(is_active=True)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0030_simracing_venue"),
    ]

    operations = [
        migrations.RunPython(activate, migrations.RunPython.noop),
    ]
