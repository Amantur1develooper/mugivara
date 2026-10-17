#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Заводит заведение «NY Burgers» в Webordo: ресторан, филиалы и меню.

Скрипт идемпотентный: повторный запуск обновляет то, что уже есть, и ничего
не удаляет. Чужие заведения не трогает.

По умолчанию создаёт два филиала с общим меню и включает им индивидуальный
дизайн (тему `ny-burgers`).

Фото блюд берутся из статики темы — static/custom/ny-burgers/img, поэтому
отдельно заливать исходный сайт на сервер не нужно.

Запуск:
    python import_ny_burgers.py --dry-run
    python import_ny_burgers.py
    python import_ny_burgers.py --branches "Ош — Центр|Ош — Кулатова"
    python import_ny_burgers.py --photos /путь/к/ny-burgers-site/img
    python import_ny_burgers.py --no-theme      # без индивидуального дизайна
"""
import argparse
import os
import sys
from io import BytesIO

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from PIL import Image                                    # noqa: E402
from django.conf import settings                         # noqa: E402
from django.core.files.base import ContentFile           # noqa: E402
from django.db import transaction                        # noqa: E402

from core.models import Restaurant, Branch, PlaceCategory   # noqa: E402
from catalog.models import (                             # noqa: E402
    MenuSet, Category, Item, ItemCategory,
    BranchMenuSet, BranchCategory, BranchItem, BranchCategoryItem,
)
from ny_burgers_menu_data import RESTAURANT, BRANCHES, CATEGORIES   # noqa: E402

THEME = "ny-burgers"

# метки на карточках (бейдж без скидки)
LABELS = {"Double Cheese": "Хит", "Chicken BBQ": "Новинка"}


def default_photo_dir():
    """Фото лежат в статике темы — там же, где их берёт сама страница."""
    for base in list(getattr(settings, "STATICFILES_DIRS", [])) + [settings.BASE_DIR]:
        cand = os.path.join(str(base), "custom", THEME, "img")
        if os.path.isdir(cand):
            return cand
    return os.path.join(str(settings.BASE_DIR), "static", "custom", THEME, "img")


def prepare_photo(path):
    """Готовит фото к загрузке, СОХРАНЯЯ прозрачность.

    У исходников фон удалён — блюдо лежит на прозрачном. Именно это даёт
    аккуратный вид и на тёмной карточке темы, и на светлой стандартной
    витрине. Заливать белым нельзя: на тёмной карточке получится белый
    прямоугольник.
    """
    img = Image.open(path)
    has_alpha = img.mode in ("RGBA", "LA") or (
        img.mode == "P" and "transparency" in img.info
    )
    img = img.convert("RGBA" if has_alpha else "RGB")
    buf = BytesIO()
    img.save(buf, format="WEBP", quality=90, method=6)
    buf.seek(0)
    return ContentFile(buf.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--photos", default="", help="папка с фото блюд (по умолчанию — статика темы)")
    ap.add_argument("--branches", default="",
                    help='названия филиалов через «|», например "Ош — Центр|Ош — Юг"')
    ap.add_argument("--no-theme", action="store_true", help="не включать индивидуальный дизайн")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    img_dir = args.photos or default_photo_dir()
    if not os.path.isdir(img_dir):
        sys.exit(f"Не нашёл папку с фото: {img_dir}")

    # филиалы: из аргумента или из данных
    if args.branches:
        names = [n.strip() for n in args.branches.split("|") if n.strip()]
        branches = []
        for i, n in enumerate(names):
            base = dict(BRANCHES[i]) if i < len(BRANCHES) else dict(BRANCHES[0])
            base["ru"] = base["ky"] = base["en"] = n
            branches.append(base)
    else:
        branches = BRANCHES

    total = sum(len(c["items"]) for c in CATEGORIES)
    print(f"NY Burgers: {len(branches)} филиала(ов), {len(CATEGORIES)} категории, {total} позиций")
    print(f"фото из: {img_dir}")

    missing = [i["photo"] for c in CATEGORIES for i in c["items"]
               if not os.path.exists(os.path.join(img_dir, i["photo"]))]
    if missing:
        sys.exit("Нет файлов фото: " + ", ".join(missing))
    print(f"фото на месте: {total}/{total}\n")

    if args.dry_run:
        for b in branches:
            print(f"  филиал: {b['ru']}")
        for c in CATEGORIES:
            print(f"\n  {c['ru']} / {c['ky']} / {c['en']}")
            for i in c["items"]:
                price = str(i["price"])
                if i.get("old_price"):
                    price = f"{i['price']} (было {i['old_price']})"
                label = LABELS.get(i["ru"], "")
                print(f"    • {i['ru']:26} {price:18} {label}")
        print("\n--dry-run: ничего не изменено.")
        return

    with transaction.atomic():
        rest, created = Restaurant.objects.get_or_create(
            slug=RESTAURANT["slug"],
            defaults={"name_ru": RESTAURANT["ru"], "is_active": True},
        )
        rest.name_ru = RESTAURANT["ru"]
        rest.name_ky = RESTAURANT["ky"]
        rest.name_en = RESTAURANT["en"]
        rest.about_ru = RESTAURANT.get("about_ru", "")
        rest.instagram = RESTAURANT.get("instagram", "")
        rest.is_active = True
        # без категории платформы заведение не попадёт в каталог /restaurants/
        if not rest.place_category:
            rest.place_category = PlaceCategory.objects.filter(
                name_ru__icontains="Рестораны").first()
        rest.save()
        print(f"{'создан' if created else 'обновлён'} ресторан #{rest.id} {rest.name_ru}")

        # одно меню на сеть: блюда общие, цены задаются по филиалам
        menu_set, _ = MenuSet.objects.get_or_create(
            restaurant=rest, name="Меню", defaults={"is_active": True})
        menu_set.is_active = True
        menu_set.save(update_fields=["is_active"])

        # блюда и категории — один раз на ресторан
        cat_objs = []
        for ci, cat in enumerate(CATEGORIES, start=1):
            category, _ = Category.objects.get_or_create(
                menu_set=menu_set, name_ru=cat["ru"],
                defaults={"name_ky": cat["ky"], "name_en": cat["en"]})
            category.name_ky, category.name_en = cat["ky"], cat["en"]
            category.save(update_fields=["name_ky", "name_en"])

            items = []
            for ii, data in enumerate(cat["items"], start=1):
                item, _ = Item.objects.get_or_create(restaurant=rest, name_ru=data["ru"])
                item.name_ky = data["ky"]
                item.name_en = data["en"]
                item.description_ru = data.get("d_ru", "")
                item.description_ky = data.get("d_ky", "")
                item.description_en = data.get("d_en", "")
                item.base_price = data["price"]
                item.save()

                # фото обновляем только если его ещё нет: иначе каждый повторный
                # запуск плодил бы копии файла в media
                if not item.photo:
                    item.photo.save(
                        data["photo"],
                        prepare_photo(os.path.join(img_dir, data["photo"])),
                        save=True,
                    )

                ItemCategory.objects.get_or_create(
                    item=item, category=category, defaults={"sort_order": ii})
                items.append((ii, data, item))
            cat_objs.append((ci, cat, category, items))
        print(f"блюд в меню: {total}")

        # филиалы
        for bi_num, bdata in enumerate(branches, start=1):
            branch, b_created = Branch.objects.get_or_create(
                restaurant=rest, name_ru=bdata["ru"],
                defaults={"is_active": True, "delivery_enabled": True},
            )
            branch.name_ky = bdata["ky"]
            branch.name_en = bdata["en"]
            branch.address = bdata.get("address", "")
            branch.is_active = True
            if not args.no_theme:
                branch.template_slug = THEME
            branch.save()

            BranchMenuSet.objects.get_or_create(branch=branch, menu_set=menu_set,
                                                defaults={"is_active": True})

            for ci, cat, category, items in cat_objs:
                bc, _ = BranchCategory.objects.get_or_create(
                    branch=branch, category=category,
                    defaults={"sort_order": ci, "is_active": True})
                bc.sort_order, bc.is_active = ci, True
                bc.save(update_fields=["sort_order", "is_active"])

                for ii, data, item in items:
                    bitem, _ = BranchItem.objects.get_or_create(
                        branch=branch, item=item, defaults={"price": data["price"]})
                    bitem.price = data["price"]
                    bitem.old_price = data.get("old_price")
                    bitem.promo_label = data.get("promo_label", "") if data.get("old_price") else ""
                    bitem.label = LABELS.get(data["ru"], "")
                    bitem.is_available = True
                    bitem.delivery_available = True
                    bitem.sort_order = ii
                    bitem.save()

                    BranchCategoryItem.objects.get_or_create(
                        branch_category=bc, branch_item=bitem, defaults={"sort_order": ii})

            theme = branch.template_slug or "стандартный"
            print(f"  {'создан' if b_created else 'обновлён'} филиал #{branch.id} "
                  f"{branch.name_ru} — дизайн: {theme}")
            print(f"      меню: /ru/{branch.id}/menu/")

    print("\nГотово.")


if __name__ == "__main__":
    main()
