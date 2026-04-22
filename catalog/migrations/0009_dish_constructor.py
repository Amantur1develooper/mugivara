from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0008_add_stock_to_branch_item"),
        ("core", "0021_branch_pay_methods"),
    ]

    operations = [
        migrations.CreateModel(
            name="DishConstructor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200, verbose_name="Название")),
                ("description", models.TextField(blank=True, default="", verbose_name="Описание")),
                ("photo", models.ImageField(blank=True, null=True, upload_to="constructors/", verbose_name="Фото")),
                ("base_price", models.DecimalField(decimal_places=0, default=0, help_text="Цена без учёта доп. ингредиентов", max_digits=10, verbose_name="Базовая цена (сом)")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dish_constructors", to="core.branch", verbose_name="Филиал")),
            ],
            options={"verbose_name": "Конструктор блюда", "verbose_name_plural": "Конструкторы блюд", "ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="ConstructorGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200, verbose_name="Название шага")),
                ("min_select", models.PositiveSmallIntegerField(default=1, verbose_name="Минимум выбора")),
                ("max_select", models.PositiveSmallIntegerField(default=1, help_text="0 = без лимита", verbose_name="Максимум выбора")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")),
                ("constructor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="groups", to="catalog.dishconstructor")),
            ],
            options={"verbose_name": "Группа конструктора", "verbose_name_plural": "Группы конструктора", "ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="ConstructorIngredient",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200, verbose_name="Название")),
                ("extra_price", models.DecimalField(decimal_places=0, default=0, max_digits=10, verbose_name="Доп. цена (сом)")),
                ("photo", models.ImageField(blank=True, null=True, upload_to="constructors/ingredients/", verbose_name="Фото")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ingredients", to="catalog.constructorgroup")),
            ],
            options={"verbose_name": "Ингредиент", "verbose_name_plural": "Ингредиенты", "ordering": ["sort_order", "id"]},
        ),
    ]
