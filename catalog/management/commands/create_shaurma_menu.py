"""
Создаёт ресторан «Центр Шаурма» + филиал + полное меню (RU/KY/EN), собранное с фото
двух досок меню (шаурма/комбо/бокс/хот-дог/рамен + донер/чизстейки/бургеры/снеки/напитки).

Фото блюд: рисунки на реальных досках меню — шаблонные (не фото этих конкретных блюд),
поэтому вместо них подставлены свободные фото по категориям (Unsplash License —
можно использовать бесплатно, коммерчески, без указания автора). Они лежат рядом
с этой командой в папке _shaurma_menu_photos/ — интернет при запуске не нужен.
Позже подменишь на свои настоящие фото через админку/панель управления.

Позиция без цены на фото («Шаурма Мидос» — стикер с ценой пустой) пропущена —
добавь вручную через админку, когда узнаешь цену.

Использование:
    python manage.py create_shaurma_menu
    python manage.py create_shaurma_menu --slug "centr-shaurma-osh" --address "г. Ош, ..." --phone "+996700000000"
    python manage.py create_shaurma_menu --dry-run
"""

import os

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

PHOTOS_DIR = os.path.join(os.path.dirname(__file__), "_shaurma_menu_photos")

_RU_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify_ru(text: str) -> str:
    """slugify() кириллицу просто выбрасывает и даёт пустую строку — транслитерируем сами."""
    lowered = text.lower()
    transliterated = "".join(_RU_TO_LAT.get(ch, ch) for ch in lowered)
    return slugify(transliterated)

# ── Меню: (категория_ru, категория_ky, категория_en, photo_key, [items]) ───
# item = (name_ru, name_ky, name_en, price, desc_ru, desc_ky, desc_en)
MENU_DATA = [
    ("Шаурма", "Шаурма", "Shawarma", "shaurma.jpg", [
        ("Сырная шаурма", "Сырдуу шаурма", "Cheese Shawarma", 260, "", "", ""),
        ("Классическая шаурма", "Классикалык шаурма", "Classic Shawarma", 250, "", "", ""),
        ("Мини-классическая шаурма", "Мини-классикалык шаурма", "Mini Classic Shawarma", 180, "", "", ""),
        ("Шаурма «Гурман»", "«Гурман» шаурмасы", "Gourmet Shawarma", 300, "", "", ""),
        ("Мини-запечённая шаурма", "Мини-бышырылган шаурма", "Mini Baked Shawarma", 195, "", "", ""),
        ("Куриная шаурма", "Тооктон жасалган шаурма", "Chicken Shawarma", 250, "", "", ""),
        ("Мини-куриная шаурма", "Мини тоок шаурмасы", "Mini Chicken Shawarma", 180, "", "", ""),
        ("Арабская шаурма", "Араб шаурмасы", "Arabic Shawarma", 300, "", "", ""),
        ("Шаурма «Ассорти»", "«Ассорти» шаурмасы", "Assorted Shawarma", 275, "", "", ""),
        ("Запечённая шаурма", "Бышырылган шаурма", "Baked Shawarma", 265, "", "", ""),
        # "Шаурма Мидос" — цена на стикере пустая, пропущено. Добавь вручную, когда узнаешь цену.
    ]),
    ("Комбо", "Комбо", "Combo", "shaurma.jpg", [
        ("Комбо №1", "Комбо №1", "Combo #1", 350,
         "1 шаурма, картофель фри, 1 л компота",
         "1 шаурма, картошка фри, 1 л компот",
         "1 shawarma, French fries, 1L compote"),
        ("Комбо №2", "Комбо №2", "Combo #2", 599,
         "2 шаурмы, 2 порции картофеля фри, 1 л компота",
         "2 шаурма, 2 порция картошка фри, 1 л компот",
         "2 shawarmas, 2 servings of French fries, 1L compote"),
        ("Комбо №3", "Комбо №3", "Combo #3", 999,
         "4 шаурмы «Классические», 2 порции картофеля фри, 2 л компота",
         "4 «Классикалык» шаурма, 2 порция картошка фри, 2 л компот",
         "4 Classic shawarmas, 2 servings of French fries, 2L compote"),
    ]),
    ("Бокс", "Бокс", "Box", "shaurma.jpg", [
        ("Бокс большой", "Чоң бокс", "Large Box", 275, "", "", ""),
        ("Бокс средний", "Орто бокс", "Medium Box", 255, "", "", ""),
    ]),
    ("Хот-дог", "Хот-дог", "Hot Dog", "hotdog.jpg", [
        ("Хот-дог", "Хот-дог", "Hot Dog", 130, "", "", ""),
    ]),
    ("Рамен", "Рамен", "Ramen", "ramen.jpg", [
        ("Рамен", "Рамен", "Ramen", 250, "", "", ""),
    ]),
    ("Донер", "Донер", "Doner", "shaurma.jpg", [
        ("Донер классика", "Донер классика", "Doner Classic", 250, "", "", ""),
        ("Донер сырный", "Донер сырдуу", "Doner Cheese", 255, "", "", ""),
        ("Донер большой", "Донер чоң", "Doner Large", 275, "", "", ""),
        ("Донер только мясо", "Донер тек эле эт", "Doner Meat Only", 300, "", "", ""),
    ]),
    ("Чизстейки", "Чизстейктер", "Cheesesteaks", "cheesesteak.jpg", [
        ("Чизстейк", "Чизстейк", "Cheesesteak", 220, "", "", ""),
        ("Чиз-Виз", "Чиз-Виз", "Cheese Whiz", 240, "", "", ""),
        ("Чиз-Хотти", "Чиз-Хотти", "Cheese Hottie", 240, "", "", ""),
    ]),
    ("Бургеры", "Бургерлер", "Burgers", "burger.jpg", [
        ("Гамбургер", "Гамбургер", "Hamburger", 270, "", "", ""),
        ("Смэш бургер", "Смэш бургер", "Smash Burger", 260, "", "", ""),
        ("Чикен бургер", "Тоок бургер", "Chicken Burger", 250, "", "", ""),
    ]),
    ("Снеки", "Снектер", "Snacks", "fries.jpg", [
        ("Картофель фри", "Картошка фри", "French Fries", 150, "", "", ""),
        ("Луковые кольца", "Пияз шакектери", "Onion Rings", 160, "", "", ""),
        ("Наггетсы", "Наггетстер", "Nuggets", 160, "", "", ""),
        ("Сырные палочки", "Сыр таякчалары", "Cheese Sticks", 180, "", "", ""),
    ]),
    ("Напитки", "Ичимдиктер", "Drinks", "drinks.jpg", [
        ("Кола 1 литр", "Кола 1 литр", "Cola 1L", 120, "", "", ""),
        ("Фанта 1 литр", "Фанта 1 литр", "Fanta 1L", 120, "", "", ""),
        ("Спрайт 1 литр", "Спрайт 1 литр", "Sprite 1L", 120, "", "", ""),
        ("Фюсти 1 литр", "Фюсти 1 литр", "Fusty 1L", 100, "", "", ""),
        ("Чалап 1 литр", "Чалап 1 литр", "Chalap 1L", 80, "", "", ""),
        ("Салам кола 1 литр", "Салам кола 1 литр", "Salam Cola 1L", 120, "", "", ""),
        ("Ава 1 литр", "Ава 1 литр", "Ava 1L", 110, "", "", ""),
        ("Да-да сок 1 литр", "Да-да ширеси 1 литр", "DaDa Juice 1L", 140, "", "", ""),
        ("Фанта 0.5 л", "Фанта 0.5 л", "Fanta 0.5L", 80, "", "", ""),
        ("Кола 0.5 л", "Кола 0.5 л", "Cola 0.5L", 75, "", "", ""),
    ]),
]


class Command(BaseCommand):
    help = "Создаёт ресторан «Центр Шаурма» + филиал + полное меню (RU/KY/EN) с фото"

    def add_arguments(self, parser):
        parser.add_argument("--name", default="Центр Шаурма", help="Название заведения (RU)")
        parser.add_argument("--slug", default="", help="Slug ресторана, по умолчанию сгенерируется из названия")
        parser.add_argument("--name-ky", default="", help="Название (KY), по умолчанию = RU")
        parser.add_argument("--name-en", default="Shaurma Center", help="Название (EN)")
        parser.add_argument("--address", default="", help="Адрес филиала")
        parser.add_argument("--phone", default="", help="Телефон филиала")
        parser.add_argument("--no-photos", action="store_true", help="Не подставлять фото-заглушки")
        parser.add_argument("--dry-run", action="store_true", help="Только показать, что будет создано, без записи в БД")

    def log(self, msg):
        self.stdout.write(msg)

    def ok(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))

    def err(self, msg):
        self.stdout.write(self.style.ERROR(msg))

    def handle(self, *args, **options):
        name_ru = options["name"].strip()
        slug = slugify_ru(options["slug"].strip()) or slugify_ru(name_ru)
        if not slug:
            raise CommandError("Не удалось сгенерировать slug — укажи его явно через --slug")
        name_ky = options["name_ky"].strip() or name_ru
        name_en = options["name_en"].strip() or name_ru
        address = options["address"].strip()
        phone = options["phone"].strip()
        no_photos = options["no_photos"]
        dry = options["dry_run"]

        total_items = sum(len(items) for *_, items in MENU_DATA)
        self.log(f"📋 Заведение : {name_ru} (slug={slug})")
        self.log(f"   Категорий : {len(MENU_DATA)}")
        self.log(f"   Позиций   : {total_items}")
        self.log(f"   Фото      : {'выключены (--no-photos)' if no_photos else PHOTOS_DIR}")

        if dry:
            for cat_ru, cat_ky, cat_en, photo_key, items in MENU_DATA:
                self.log(f"\n📂 {cat_ru} / {cat_ky} / {cat_en} ({len(items)}) — фото: {photo_key}")
                for name_r, name_k, name_e, price, *_ in items:
                    self.log(f"   • {name_r} — {price} сом  ({name_e} / {name_k})")
            self.ok("\n✅ DRY RUN — в базу ничего не записано.")
            return

        from catalog.models import (
            BranchCategory, BranchCategoryItem, BranchItem,
            BranchMenuSet, Category, Item, ItemCategory, MenuSet,
        )
        from core.models import Branch, Restaurant

        if Restaurant.objects.filter(slug=slug).exists():
            raise CommandError(
                f"Ресторан со slug='{slug}' уже существует. "
                f"Выбери другой --slug или удали существующий вручную."
            )

        # Кэш байтов фото по имени файла, чтобы не читать с диска на каждую позицию
        photo_cache = {}

        def get_photo_content(photo_key):
            if no_photos or not photo_key:
                return None
            if photo_key not in photo_cache:
                path = os.path.join(PHOTOS_DIR, photo_key)
                if not os.path.exists(path):
                    self.err(f"   ⚠️ фото не найдено: {path}")
                    photo_cache[photo_key] = None
                else:
                    with open(path, "rb") as f:
                        photo_cache[photo_key] = f.read()
            return photo_cache[photo_key]

        restaurant = Restaurant.objects.create(
            slug=slug, name_ru=name_ru, name_ky=name_ky, name_en=name_en,
            is_active=True,
        )
        self.ok(f"✨ Создан ресторан id={restaurant.id} ({name_ru})")

        branch = Branch.objects.create(
            restaurant=restaurant,
            name_ru=name_ru, name_ky=name_ky, name_en=name_en,
            address=address, phone=phone,
            is_active=True,
        )
        self.ok(f"✨ Создан филиал id={branch.id}")

        menu_set = MenuSet.objects.create(
            restaurant=restaurant, name="Основное меню", is_active=True,
        )
        BranchMenuSet.objects.create(branch=branch, menu_set=menu_set)
        self.log(f"   MenuSet id={menu_set.id}")

        items_created = 0
        photos_set = 0
        for cat_idx, (cat_ru, cat_ky, cat_en, photo_key, items) in enumerate(MENU_DATA):
            category = Category.objects.create(
                menu_set=menu_set, name_ru=cat_ru, name_ky=cat_ky, name_en=cat_en,
            )
            branch_category = BranchCategory.objects.create(
                branch=branch, category=category,
                sort_order=cat_idx, is_active=True,
            )
            self.log(f"\n📂 [{cat_idx + 1}/{len(MENU_DATA)}] {cat_ru} — {len(items)} поз.")

            for item_idx, (name_r, name_k, name_e, price, desc_r, desc_k, desc_e) in enumerate(items):
                item = Item(
                    restaurant=restaurant,
                    name_ru=name_r, name_ky=name_k, name_en=name_e,
                    description_ru=desc_r, description_ky=desc_k, description_en=desc_e,
                    base_price=price,
                )
                content = get_photo_content(photo_key)
                photo_status = ""
                if content:
                    # прямое присваивание, а не .save(): иначе upload_to подставится
                    # дважды при повторном сохранении внутри Item.save()->_compress_photo()
                    item.photo = ContentFile(content, name=photo_key)
                    photos_set += 1
                    photo_status = " 📷"
                item.save()

                branch_item = BranchItem.objects.create(
                    branch=branch, item=item,
                    price=price, sort_order=item_idx, is_available=True,
                )
                ItemCategory.objects.create(item=item, category=category, sort_order=item_idx)
                BranchCategoryItem.objects.create(
                    branch_category=branch_category, branch_item=branch_item,
                    sort_order=item_idx,
                )
                items_created += 1
                self.log(f"   • {name_r} — {price} сом{photo_status}")

        self.stdout.write("")
        self.ok("=" * 55)
        self.ok("✅ Готово!")
        self.log(f"   Ресторан   : {name_ru} (id={restaurant.id}, slug={slug})")
        self.log(f"   Филиал     : id={branch.id}")
        self.log(f"   Категорий  : {len(MENU_DATA)}")
        self.log(f"   Позиций    : {items_created}")
        self.log(f"   С фото     : {photos_set}/{items_created}")
        self.log(f"   Меню       : http://<host>/ru/{branch.id}/menu/")
        self.ok("=" * 55)
        self.log("")
        self.log("⚠️  Фото — свободные стоковые (Unsplash), подобраны по категориям,")
        self.log("   не фото именно этих блюд. Замени на свои настоящие через админку,")
        self.log("   когда будут — там же и логотип/обложку заведения добавь.")
        self.log("")
        self.log("⚠️  Пропущено: «Шаурма Мидос» — цена на стикере не была указана.")
        self.log("   Добавь вручную через админку, когда узнаешь цену.")
        self.log("")
        self.log("📌 Если нужно привязать аккаунт владельца к ресторану:")
        self.log("   python manage.py shell")
        self.log("   from core.models import Restaurant, Membership")
        self.log("   from django.contrib.auth.models import User")
        self.log("   u = User.objects.get(username='ЛОГИН_ВЛАДЕЛЬЦА')")
        self.log(f"   r = Restaurant.objects.get(slug='{slug}')")
        self.log("   Membership.objects.get_or_create(user=u, restaurant=r)")
