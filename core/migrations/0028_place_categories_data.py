"""
Data migration: create all platform PlaceCategory records and
auto-assign existing restaurants (place_category=None) to 'restaurants'.
"""
from django.db import migrations

CATEGORIES = [
    {
        "slug": "restaurants",
        "sort_order": 1,
        "name_ru": "Рестораны",
        "name_ky": "Тамак-аш",
        "name_en": "Restaurants",
        "subtitle_ru": "Меню, доставка, QR",
        "subtitle_ky": "Меню, жеткирүү, QR",
        "subtitle_en": "Menu, delivery, QR",
        "icon": "🍽️",
        "supports_catalog": True,
        "supports_ordering": True,
        "supports_booking": True,
        "item_noun_ru": "Блюда",
        "item_noun_ky": "Тамактар",
        "item_noun_en": "Dishes",
    },
    {
        "slug": "shops",
        "sort_order": 2,
        "name_ru": "Магазины",
        "name_ky": "Дүкөндөр",
        "name_en": "Shops",
        "subtitle_ru": "Товары, доставка",
        "subtitle_ky": "Товарлар, жеткирүү",
        "subtitle_en": "Products, delivery",
        "icon": "🛍️",
        "supports_catalog": True,
        "supports_ordering": True,
        "supports_booking": False,
        "item_noun_ru": "Товары",
        "item_noun_ky": "Товарлар",
        "item_noun_en": "Products",
    },
    {
        "slug": "markets",
        "sort_order": 3,
        "name_ru": "Рынки",
        "name_ky": "Базарлар",
        "name_en": "Markets",
        "subtitle_ru": "Свежие продукты",
        "subtitle_ky": "Свежие продукты",
        "subtitle_en": "Fresh products",
        "icon": "🥬",
        "supports_catalog": True,
        "supports_ordering": True,
        "supports_booking": False,
        "item_noun_ru": "Товары",
        "item_noun_ky": "Товарлар",
        "item_noun_en": "Products",
    },
    {
        "slug": "hotels",
        "sort_order": 4,
        "name_ru": "Отели",
        "name_ky": "Мейманканалар",
        "name_en": "Hotels",
        "subtitle_ru": "Бронирование номеров",
        "subtitle_ky": "Номер брондоо",
        "subtitle_en": "Room booking",
        "icon": "🏨",
        "supports_catalog": True,
        "supports_ordering": False,
        "supports_booking": True,
        "item_noun_ru": "Номера",
        "item_noun_ky": "Бөлмөлөр",
        "item_noun_en": "Rooms",
    },
    {
        "slug": "pharmacy",
        "sort_order": 5,
        "name_ru": "Аптеки",
        "name_ky": "Аптекалар",
        "name_en": "Pharmacies",
        "subtitle_ru": "Лекарства и товары",
        "subtitle_ky": "Дарылар жана товарлар",
        "subtitle_en": "Medicine & products",
        "icon": "💊",
        "supports_catalog": True,
        "supports_ordering": True,
        "supports_booking": False,
        "item_noun_ru": "Препараты",
        "item_noun_ky": "Дарылар",
        "item_noun_en": "Medicines",
    },
    {
        "slug": "legal",
        "sort_order": 6,
        "name_ru": "Юридические",
        "name_ky": "Юридикалык",
        "name_en": "Legal",
        "subtitle_ru": "Юридические услуги",
        "subtitle_ky": "Юридикалык кызматтар",
        "subtitle_en": "Legal services",
        "icon": "⚖️",
        "supports_catalog": True,
        "supports_ordering": False,
        "supports_booking": True,
        "item_noun_ru": "Услуги",
        "item_noun_ky": "Кызматтар",
        "item_noun_en": "Services",
    },
    {
        "slug": "eco",
        "sort_order": 7,
        "name_ru": "Эко",
        "name_ky": "Эко",
        "name_en": "Eco",
        "subtitle_ru": "Органические товары",
        "subtitle_ky": "Органикалык товарлар",
        "subtitle_en": "Organic products",
        "icon": "🌿",
        "supports_catalog": True,
        "supports_ordering": True,
        "supports_booking": False,
        "item_noun_ru": "Товары",
        "item_noun_ky": "Товарлар",
        "item_noun_en": "Products",
    },
    {
        "slug": "agency",
        "sort_order": 8,
        "name_ru": "Агентства",
        "name_ky": "Агенттиктер",
        "name_en": "Agencies",
        "subtitle_ru": "Услуги и консультации",
        "subtitle_ky": "Кызматтар жана кеңешмелер",
        "subtitle_en": "Services & consulting",
        "icon": "🏢",
        "supports_catalog": True,
        "supports_ordering": False,
        "supports_booking": True,
        "item_noun_ru": "Услуги",
        "item_noun_ky": "Кызматтар",
        "item_noun_en": "Services",
    },
    {
        "slug": "karaoke",
        "sort_order": 9,
        "name_ru": "Karaoke",
        "name_ky": "Karaoke",
        "name_en": "Karaoke",
        "subtitle_ru": "Залы и бронирование",
        "subtitle_ky": "Залдар жана брондоо",
        "subtitle_en": "Halls & booking",
        "icon": "🎤",
        "supports_catalog": True,
        "supports_ordering": False,
        "supports_booking": True,
        "item_noun_ru": "Залы",
        "item_noun_ky": "Залдар",
        "item_noun_en": "Halls",
    },
]


def create_categories(apps, schema_editor):
    PlaceCategory = apps.get_model("core", "PlaceCategory")
    Restaurant = apps.get_model("core", "Restaurant")

    restaurants_cat = None
    for data in CATEGORIES:
        slug = data["slug"]
        cat, created = PlaceCategory.objects.get_or_create(
            slug=slug,
            defaults=data,
        )
        if not created:
            # Update fields on existing record (e.g. admin already created "restaurants")
            for field, value in data.items():
                setattr(cat, field, value)
            cat.save()
        if slug == "restaurants":
            restaurants_cat = cat

    # Assign all currently-uncategorised restaurants to "restaurants" category
    if restaurants_cat is not None:
        Restaurant.objects.filter(place_category=None).update(
            place_category=restaurants_cat
        )


def reverse_categories(apps, schema_editor):
    PlaceCategory = apps.get_model("core", "PlaceCategory")
    slugs = [c["slug"] for c in CATEGORIES]
    PlaceCategory.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0027_place_category_and_restaurant_cover"),
    ]

    operations = [
        migrations.RunPython(create_categories, reverse_categories),
    ]
