#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Универсальный импорт заведения в Webordo из файла меню.

Файл меню — модуль с RESTAURANT, BRANCHES и CATEGORIES
(см. pizzburg_menu_data.py или islambek_menu_data.py).

Скрипт идемпотентный: повторный запуск обновляет то, что уже есть, и ничего
не удаляет. Чужие заведения не трогает.

Запуск:
    python import_restaurant.py --data pizzburg_menu_data --photos pizzburg_photos --dry-run
    python import_restaurant.py --data pizzburg_menu_data --photos pizzburg_photos
    python import_restaurant.py --data islambek_menu_data --photos islambek_photos
    ... --branches "Пиццбург — Центр|Пиццбург — Юг"
    ... --theme ny-burgers          # включить индивидуальный дизайн
"""
import argparse
import importlib
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

Image.MAX_IMAGE_PIXELS = None


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
    ap.add_argument("--data", required=True, help="модуль с меню, напр. pizzburg_menu_data")
    ap.add_argument("--photos", required=True, help="папка с фото блюд")
    ap.add_argument("--cat-photos", default="", dest="cat_photos",
                    help="папка с обложками категорий (по умолчанию — та же, что у блюд)")
    ap.add_argument("--branches", default="", help='названия филиалов через «|»')
    ap.add_argument("--theme", default="", help="код индивидуального дизайна (template_slug)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        data = importlib.import_module(args.data)
    except ImportError as e:
        sys.exit(f"Не нашёл модуль меню «{args.data}»: {e}")
    RESTAURANT, BRANCHES, CATEGORIES = data.RESTAURANT, data.BRANCHES, data.CATEGORIES

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
    have_photo = sum(1 for c in CATEGORIES for i in c["items"] if i["photo"])
    print(f'{RESTAURANT["ru"]}: {len(branches)} филиал(ов), {len(CATEGORIES)} категорий, '
          f'{total} позиций ({have_photo} с фото)')

    missing = [i["photo"] for c in CATEGORIES for i in c["items"]
               if i["photo"] and not os.path.exists(os.path.join(args.photos, i["photo"]))]
    if missing:
        sys.exit(f"Нет файлов фото ({len(missing)}): " + ", ".join(missing[:5]))
    print("все фото на месте\n")

    if args.dry_run:
        for b in branches:
            print(f'  филиал: {b["ru"]}')
        for c in CATEGORIES:
            print(f'\n  {c["ru"]} / {c["ky"]} / {c["en"]} — {len(c["items"])}')
            for i in c["items"][:3]:
                print(f'    • {i["ru"][:32]:34} {i["price"]:>5}  {i["en"]}')
            if len(c["items"]) > 3:
                print(f'    … ещё {len(c["items"]) - 3}')
        print("\n--dry-run: ничего не изменено.")
        return

    with transaction.atomic():
        rest, created = Restaurant.objects.get_or_create(
            slug=RESTAURANT["slug"],
            defaults={"name_ru": RESTAURANT["ru"], "is_active": True},
        )
        rest.name_ru = RESTAURANT["ru"]
        rest.name_ky = RESTAURANT.get("ky", "")
        rest.name_en = RESTAURANT.get("en", "")
        rest.about_ru = RESTAURANT.get("about_ru", "")
        rest.external_url = RESTAURANT.get("external_url", "")
        rest.is_active = True
        if not rest.place_category:
            rest.place_category = PlaceCategory.objects.filter(
                name_ru__icontains="Рестораны").first()
        rest.save()
        print(f'{"создан" if created else "обновлён"} ресторан #{rest.id} {rest.name_ru}')

        menu_set, _ = MenuSet.objects.get_or_create(
            restaurant=rest, name="Меню", defaults={"is_active": True})
        menu_set.is_active = True
        menu_set.save(update_fields=["is_active"])

        cat_objs, photos_added = [], 0
        for ci, cat in enumerate(CATEGORIES, start=1):
            category, _ = Category.objects.get_or_create(
                menu_set=menu_set, name_ru=cat["ru"],
                defaults={"name_ky": cat["ky"], "name_en": cat["en"]})
            category.name_ky, category.name_en = cat["ky"], cat["en"]
            category.save(update_fields=["name_ky", "name_en"])

            # обложка раздела: ставим, только если её ещё нет
            cover = cat.get("photo")
            if cover and not category.photo:
                cover_path = os.path.join(args.cat_photos or args.photos, cover)
                if os.path.exists(cover_path):
                    with open(cover_path, "rb") as fh:
                        category.photo.save(cover, ContentFile(fh.read()), save=True)

            rows = []
            for ii, d in enumerate(cat["items"], start=1):
                item, _ = Item.objects.get_or_create(restaurant=rest, name_ru=d["ru"])
                item.name_ky = d["ky"]
                item.name_en = d["en"]
                item.description_ru = d.get("d_ru", "")
                item.description_ky = d.get("d_ky", "")
                item.description_en = d.get("d_en", "")
                item.base_price = d["price"]
                item.save()

                # фото ставим только если его ещё нет — иначе повторный запуск
                # плодил бы копии файлов в media
                if d["photo"] and not item.photo:
                    item.photo.save(
                        d["photo"],
                        prepare_photo(os.path.join(args.photos, d["photo"])),
                        save=True,
                    )
                    photos_added += 1

                ItemCategory.objects.get_or_create(
                    item=item, category=category, defaults={"sort_order": ii})
                rows.append((ii, d, item))
            cat_objs.append((ci, category, rows))
            print(f'  {cat["ru"]:24} {len(cat["items"]):3}')

        print(f"\nзагружено фото: {photos_added}")

        for b in branches:
            branch, b_created = Branch.objects.get_or_create(
                restaurant=rest, name_ru=b["ru"],
                defaults={"is_active": True, "delivery_enabled": True},
            )
            branch.name_ky = b.get("ky", "")
            branch.name_en = b.get("en", "")
            branch.address = b.get("address", "")
            branch.is_active = True
            # контакты и часы работы, если указаны в данных меню
            if b.get("phone"):
                branch.phone = b["phone"]
            if b.get("map_url"):
                branch.map_url = b["map_url"]
            if b.get("open_time") and b.get("close_time"):
                from django.utils.dateparse import parse_time
                ot, ct = parse_time(b["open_time"]), parse_time(b["close_time"])
                if ot and ct:
                    branch.open_time, branch.close_time = ot, ct
                    branch.is_open_24h = False
            if b.get("work_days"):
                branch.work_days = b["work_days"]
            if args.theme:
                branch.template_slug = args.theme
            branch.save()

            BranchMenuSet.objects.get_or_create(branch=branch, menu_set=menu_set,
                                                defaults={"is_active": True})

            for ci, category, rows in cat_objs:
                bc, _ = BranchCategory.objects.get_or_create(
                    branch=branch, category=category,
                    defaults={"sort_order": ci, "is_active": True})
                bc.sort_order, bc.is_active = ci, True
                bc.save(update_fields=["sort_order", "is_active"])

                for ii, d, item in rows:
                    bi, _ = BranchItem.objects.get_or_create(
                        branch=branch, item=item, defaults={"price": d["price"]})
                    bi.price = d["price"]
                    bi.is_available = True
                    bi.delivery_available = True
                    bi.sort_order = ii
                    bi.save()

                    BranchCategoryItem.objects.get_or_create(
                        branch_category=bc, branch_item=bi, defaults={"sort_order": ii})

            print(f'{"создан" if b_created else "обновлён"} филиал #{branch.id} '
                  f'{branch.name_ru} → /ru/{branch.id}/menu/')

    print("\nГотово.")


if __name__ == "__main__":
    main()
