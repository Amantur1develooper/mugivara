#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Заводит ресторан «Исламбек» в Webordo: ресторан, филиал и меню на 3 языках.

Скрипт идемпотентный: повторный запуск обновляет то, что уже есть, и ничего
не удаляет. Чужие заведения не трогает.

Фото берутся из папки islambek_photos (имя файла указано в данных меню).

Запуск:
    python import_islambek.py --dry-run
    python import_islambek.py
    python import_islambek.py --branches "Исламбек — Ош|Исламбек — Бишкек"
"""
import argparse
import os
import sys
from io import BytesIO

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from PIL import Image                                    # noqa: E402
from django.core.files.base import ContentFile           # noqa: E402
from django.db import transaction                        # noqa: E402

from core.models import Restaurant, Branch, PlaceCategory   # noqa: E402
from catalog.models import (                             # noqa: E402
    MenuSet, Category, Item, ItemCategory,
    BranchMenuSet, BranchCategory, BranchItem, BranchCategoryItem,
)
from islambek_menu_data import RESTAURANT, BRANCHES, CATEGORIES   # noqa: E402

PHOTO_DIR = "islambek_photos"


def prepare_photo(path):
    """Готовит фото к загрузке, сохраняя прозрачность, если она есть."""
    img = Image.open(path)
    has_alpha = img.mode in ("RGBA", "LA") or (
        img.mode == "P" and "transparency" in img.info
    )
    img = img.convert("RGBA" if has_alpha else "RGB")
    if max(img.size) > 1100:
        img.thumbnail((1100, 1100), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="WEBP", quality=86, method=6)
    buf.seek(0)
    return ContentFile(buf.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--photos", default=PHOTO_DIR, help="папка с фото блюд")
    ap.add_argument("--branches", default="",
                    help='названия филиалов через «|»')
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(args.photos):
        sys.exit(f"Не нашёл папку с фото: {args.photos}")

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
    with_photo = sum(1 for c in CATEGORIES for i in c["items"] if i["photo"])
    print(f"Исламбек: {len(branches)} филиал(ов), {len(CATEGORIES)} категорий, "
          f"{total} позиций ({with_photo} с фото)")

    missing = [i["photo"] for c in CATEGORIES for i in c["items"]
               if i["photo"] and not os.path.exists(os.path.join(args.photos, i["photo"]))]
    if missing:
        sys.exit(f"Нет файлов фото ({len(missing)}): " + ", ".join(missing[:5]))
    print("все фото на месте\n")

    if args.dry_run:
        for b in branches:
            print(f"  филиал: {b['ru']}")
        for c in CATEGORIES:
            print(f"\n  {c['ru']} / {c['ky']} / {c['en']} — {len(c['items'])} позиций")
            for i in c["items"][:3]:
                print(f"    • {i['ru'][:34]:36} {i['price']:>5}  {i['en']}")
            if len(c["items"]) > 3:
                print(f"    … ещё {len(c['items']) - 3}")
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
        rest.external_url = RESTAURANT.get("external_url", "")
        rest.is_active = True
        if not rest.place_category:
            rest.place_category = PlaceCategory.objects.filter(
                name_ru__icontains="Рестораны").first()
        rest.save()
        print(f"{'создан' if created else 'обновлён'} ресторан #{rest.id} {rest.name_ru}")

        menu_set, _ = MenuSet.objects.get_or_create(
            restaurant=rest, name="Меню", defaults={"is_active": True})
        menu_set.is_active = True
        menu_set.save(update_fields=["is_active"])

        # блюда и категории — один раз на ресторан
        cat_objs = []
        photos_added = 0
        for ci, cat in enumerate(CATEGORIES, start=1):
            category, _ = Category.objects.get_or_create(
                menu_set=menu_set, name_ru=cat["ru"],
                defaults={"name_ky": cat["ky"], "name_en": cat["en"]})
            category.name_ky, category.name_en = cat["ky"], cat["en"]
            category.save(update_fields=["name_ky", "name_en"])

            rows = []
            for ii, data in enumerate(cat["items"], start=1):
                item, _ = Item.objects.get_or_create(restaurant=rest, name_ru=data["ru"])
                item.name_ky = data["ky"]
                item.name_en = data["en"]
                item.description_ru = data.get("d_ru", "")
                item.description_ky = data.get("d_ky", "")
                item.description_en = data.get("d_en", "")
                item.base_price = data["price"]
                item.save()

                # фото ставим только если его ещё нет — иначе повторный запуск
                # плодил бы копии файлов в media
                if data["photo"] and not item.photo:
                    item.photo.save(
                        data["photo"],
                        prepare_photo(os.path.join(args.photos, data["photo"])),
                        save=True,
                    )
                    photos_added += 1

                ItemCategory.objects.get_or_create(
                    item=item, category=category, defaults={"sort_order": ii})
                rows.append((ii, data, item))
            cat_objs.append((ci, cat, category, rows))
            print(f"  {cat['ru']:20} {len(cat['items']):3} позиций")

        print(f"\nзагружено фото: {photos_added}")

        for bdata in branches:
            branch, b_created = Branch.objects.get_or_create(
                restaurant=rest, name_ru=bdata["ru"],
                defaults={"is_active": True, "delivery_enabled": True},
            )
            branch.name_ky = bdata["ky"]
            branch.name_en = bdata["en"]
            branch.address = bdata.get("address", "")
            branch.is_active = True
            branch.save()

            BranchMenuSet.objects.get_or_create(branch=branch, menu_set=menu_set,
                                                defaults={"is_active": True})

            for ci, cat, category, rows in cat_objs:
                bc, _ = BranchCategory.objects.get_or_create(
                    branch=branch, category=category,
                    defaults={"sort_order": ci, "is_active": True})
                bc.sort_order, bc.is_active = ci, True
                bc.save(update_fields=["sort_order", "is_active"])

                for ii, data, item in rows:
                    bitem, _ = BranchItem.objects.get_or_create(
                        branch=branch, item=item, defaults={"price": data["price"]})
                    bitem.price = data["price"]
                    bitem.is_available = True
                    bitem.delivery_available = True
                    bitem.sort_order = ii
                    bitem.save()

                    BranchCategoryItem.objects.get_or_create(
                        branch_category=bc, branch_item=bitem, defaults={"sort_order": ii})

            print(f"{'создан' if b_created else 'обновлён'} филиал #{branch.id} "
                  f"{branch.name_ru} → /ru/{branch.id}/menu/")

    print("\nГотово.")


if __name__ == "__main__":
    main()
