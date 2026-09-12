from django.db import migrations


def fill_english(apps, schema_editor):
    EcoProject = apps.get_model("eco", "EcoProject")
    EcoService = apps.get_model("eco", "EcoService")

    project = EcoProject.objects.filter(slug="eko-truby").first()
    if not project:
        return

    if not project.name_en:
        project.name_en = "Eco Pipes"
    if not project.description_en:
        project.description_en = (
            "We collect used plastic bags and turn them into plastic pipes."
        )
    project.save(update_fields=["name_en", "description_en"])

    for service in project.services.all():
        changed = []
        if not service.name_en and service.name == "Сбор полиэтилена":
            service.name_en = "Plastic bag collection"
            changed.append("name_en")
        if not service.description_en and service.description == "Собираем использованные полиэтиленовые пакеты":
            service.description_en = "We collect used plastic bags"
            changed.append("description_en")
        if changed:
            service.save(update_fields=changed)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("eco", "0007_ecoproject_description_en_ecoproject_name_en_and_more"),
    ]

    operations = [
        migrations.RunPython(fill_english, noop),
    ]
