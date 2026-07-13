"""
Data migration: add 'entertainment' PlaceCategory and create a full
sim-racing / karting venue (Restaurant, Branch, catalog, booking places).

⚠️  After migrating, fill in real data through Django admin:
    - Restaurant  → phone, whatsapp, map_url, logo
    - Branch      → address, phone, map_url, open_time / close_time
    - TelegramRecipient → chat_id (your Telegram group id)
"""
from decimal import Decimal
from django.db import migrations


# ── catalogue data ─────────────────────────────────────────────────────────────

CATEGORIES_DATA = [
    {
        "name": "Стандартный картинг",
        "name_ky": "Стандарттык картинг",
        "name_en": "Standard Karting",
        "sort_order": 1,
        "items": [
            {"name_ru": "5 минут",  "name_en": "5 min",  "price": Decimal("390")},
            {"name_ru": "8 минут",  "name_en": "8 min",  "price": Decimal("490")},
            {"name_ru": "11 минут", "name_en": "11 min", "price": Decimal("690")},
        ],
    },
    {
        "name": "Автосимулятор",
        "name_ky": "Авто симулятор",
        "name_en": "Auto Simulator",
        "sort_order": 2,
        "items": [
            {"name_ru": "20 минут", "name_en": "20 min", "price": Decimal("190")},
            {"name_ru": "30 минут", "name_en": "30 min", "price": Decimal("290")},
            {"name_ru": "40 минут", "name_en": "40 min", "price": Decimal("390")},
            {"name_ru": "60 минут", "name_en": "60 min", "price": Decimal("490")},
        ],
    },
    {
        "name": "Спортивный Евроспор картинг",
        "name_ky": "Спорттук Евроспор картинг",
        "name_en": "Sport Eurocup Karting",
        "sort_order": 3,
        "items": [
            {"name_ru": "5 минут",  "name_en": "5 min",  "price": Decimal("690")},
            {"name_ru": "8 минут",  "name_en": "8 min",  "price": Decimal("890")},
            {"name_ru": "11 минут", "name_en": "11 min", "price": Decimal("1190")},
        ],
    },
]

# Booking places (floors → simulators/karts).
# Adjust titles and counts after migration via admin.
FLOORS_DATA = [
    {
        "name_ru": "Картинговая трасса",
        "name_en": "Karting Track",
        "sort_order": 1,
        "places": [
            {"title": "Карт №1", "token": "simr_kart_01_tok32xpad_____"},
            {"title": "Карт №2", "token": "simr_kart_02_tok32xpad_____"},
            {"title": "Карт №3", "token": "simr_kart_03_tok32xpad_____"},
            {"title": "Карт №4", "token": "simr_kart_04_tok32xpad_____"},
        ],
    },
    {
        "name_ru": "Зона симуляторов",
        "name_en": "Simulator Zone",
        "sort_order": 2,
        "places": [
            {"title": "Симулятор №1", "token": "simr_sim_01_tok32xpaddd___"},
            {"title": "Симулятор №2", "token": "simr_sim_02_tok32xpaddd___"},
            {"title": "Симулятор №3", "token": "simr_sim_03_tok32xpaddd___"},
        ],
    },
]


def create_simracing(apps, schema_editor):
    PlaceCategory = apps.get_model("core",    "PlaceCategory")
    Restaurant    = apps.get_model("core",    "Restaurant")
    Branch        = apps.get_model("core",    "Branch")
    MenuSet       = apps.get_model("catalog", "MenuSet")
    Category      = apps.get_model("catalog", "Category")
    Item          = apps.get_model("catalog", "Item")
    ItemCategory  = apps.get_model("catalog", "ItemCategory")
    BranchMenuSet       = apps.get_model("catalog", "BranchMenuSet")
    BranchItem          = apps.get_model("catalog", "BranchItem")
    BranchCategory      = apps.get_model("catalog", "BranchCategory")
    BranchCategoryItem  = apps.get_model("catalog", "BranchCategoryItem")
    Floor         = apps.get_model("reservations", "Floor")
    Place         = apps.get_model("reservations", "Place")

    # ── 1. Entertainment PlaceCategory ────────────────────────────────────────
    ent_cat, _ = PlaceCategory.objects.get_or_create(
        slug="entertainment",
        defaults=dict(
            sort_order=10,
            name_ru="Развлечения",
            name_ky="Көңүл ачуу",
            name_en="Entertainment",
            subtitle_ru="Симрейсинг, картинг, игры",
            subtitle_ky="Симрейсинг, картинг, оюндар",
            subtitle_en="Sim racing, karting, games",
            icon="🎮",
            supports_catalog=True,
            supports_ordering=True,
            supports_booking=True,
            item_noun_ru="Сессии",
            item_noun_ky="Сессиялар",
            item_noun_en="Sessions",
            is_active=True,
        ),
    )

    # ── 2. Restaurant ─────────────────────────────────────────────────────────
    restaurant, _ = Restaurant.objects.get_or_create(
        slug="simracing",
        defaults=dict(
            place_category=ent_cat,
            name_ru="Симрейсинг",
            name_ky="Симрейсинг",
            name_en="Sim Racing",
            about_ru=(
                "Картинг и авто-симуляторы. "
                "Три вида трасс — стандартный картинг, Евроспор и авто-симулятор. "
                "Выбери продолжительность сессии и количество кругов!"
            ),
            phone="",      # ← заполни в admin
            whatsapp="",   # ← заполни в admin (напр. +996700XXXXXX)
            map_url="",    # ← заполни в admin (2ГИС / Google Maps)
            is_active=True,
            rating=Decimal("0.0"),
        ),
    )

    # ── 3. Branch ─────────────────────────────────────────────────────────────
    branch, _ = Branch.objects.get_or_create(
        restaurant=restaurant,
        name_ru="Симрейсинг",
        defaults=dict(
            name_ky="Симрейсинг",
            name_en="Sim Racing",
            address="",    # ← заполни в admin
            phone="",      # ← заполни в admin
            map_url="",    # ← заполни в admin
            is_active=True,
            delivery_enabled=False,
            pay_cash_enabled=True,
            pay_online_enabled=True,
            work_days="0,1,2,3,4,5,6",
        ),
    )

    # ── 4. MenuSet ────────────────────────────────────────────────────────────
    menu_set, _ = MenuSet.objects.get_or_create(
        restaurant=restaurant,
        name="Услуги",
        defaults=dict(is_active=True),
    )

    # ── 5. BranchMenuSet ──────────────────────────────────────────────────────
    BranchMenuSet.objects.get_or_create(
        branch=branch,
        menu_set=menu_set,
        defaults=dict(is_active=True),
    )

    # ── 6. Categories + Items ─────────────────────────────────────────────────
    for cat_order, cat_data in enumerate(CATEGORIES_DATA):
        category, _ = Category.objects.get_or_create(
            menu_set=menu_set,
            name_ru=cat_data["name"],
            defaults=dict(
                name_ky=cat_data.get("name_ky", ""),
                name_en=cat_data.get("name_en", ""),
            ),
        )

        branch_cat, _ = BranchCategory.objects.get_or_create(
            branch=branch,
            category=category,
            defaults=dict(sort_order=cat_data["sort_order"], is_active=True),
        )

        for item_order, item_data in enumerate(cat_data["items"]):
            full_name = f"{cat_data['name']} — {item_data['name_ru']}"
            item, _ = Item.objects.get_or_create(
                restaurant=restaurant,
                name_ru=full_name,
                defaults=dict(
                    name_en=f"{cat_data.get('name_en', cat_data['name'])} — {item_data.get('name_en', item_data['name_ru'])}",
                    base_price=item_data["price"],
                    description_ru=(
                        f"{item_data['name_ru']} · {cat_data['name']}. "
                        "Укажи количество — можно купить несколько сессий за раз."
                    ),
                ),
            )

            ItemCategory.objects.get_or_create(
                item=item, category=category,
                defaults=dict(sort_order=item_order),
            )

            branch_item, _ = BranchItem.objects.get_or_create(
                branch=branch,
                item=item,
                defaults=dict(
                    price=item_data["price"],
                    is_available=True,
                    sort_order=item_order,
                    delivery_available=False,
                ),
            )

            BranchCategoryItem.objects.get_or_create(
                branch_category=branch_cat,
                branch_item=branch_item,
                defaults=dict(sort_order=item_order),
            )

    # ── 7. Floors + Places (booking) ──────────────────────────────────────────
    for floor_data in FLOORS_DATA:
        floor, _ = Floor.objects.get_or_create(
            branch=branch,
            name_ru=floor_data["name_ru"],
            defaults=dict(
                name_en=floor_data.get("name_en", ""),
                sort_order=floor_data["sort_order"],
                is_active=True,
            ),
        )
        for place_data in floor_data["places"]:
            Place.objects.get_or_create(
                floor=floor,
                title=place_data["title"],
                defaults=dict(
                    type="table",
                    seats=1,
                    token=place_data["token"],
                    is_active=True,
                ),
            )


def reverse_simracing(apps, schema_editor):
    Restaurant = apps.get_model("core", "Restaurant")
    PlaceCategory = apps.get_model("core", "PlaceCategory")
    Restaurant.objects.filter(slug="simracing").delete()
    PlaceCategory.objects.filter(slug="entertainment").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core",         "0029_branch_print_on_accept"),
        ("catalog",      "0015_constructor_ingredient_warehouse_link"),
        ("reservations", "0009_alter_booking_options_alter_floor_options_and_more"),
    ]

    operations = [
        migrations.RunPython(create_simracing, reverse_simracing),
    ]
