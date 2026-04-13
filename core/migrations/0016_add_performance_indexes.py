from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_restaurant_social_links"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="restaurant",
            index=models.Index(
                fields=["is_active", "-rating"],
                name="restaurant_active_rating_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="restaurant",
            index=models.Index(
                fields=["slug"],
                name="restaurant_slug_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="branch",
            index=models.Index(
                fields=["restaurant", "is_active"],
                name="branch_restaurant_active_idx",
            ),
        ),
    ]
