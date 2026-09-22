#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Импорт/обновление меню ресторана DUA (https://webordo.kg/ru/r/DUA/) в WebOrdo.

Источник данных: dua_menu_data.py (составлено вручную из PDF-меню, RU/KY/EN).
Фото:   папка photos/ рядом со скриптом (JPEG, по одному файлу на слаг).

Применяет ОДНО И ТО ЖЕ меню ко ВСЕМ филиалам ресторана DUA (филиалы находятся
автоматически — Restaurant.branches.all()). Категории/позиции создаются или
обновляются по имени (name_ru) — безопасно запускать повторно.

Запуск (из корня проекта, из активного venv):
    python import_dua_menu.py --dry-run
    python import_dua_menu.py

Параметры:
    --dry-run              показать, что будет импортировано, ничего не писать в БД
    --restaurant-slug S    слаг ресторана (по умолчанию: dua, регистр не важен)
    --restaurant-id N      использовать ресторан по ID вместо поиска по слагу
    --no-photos            не прикреплять фотографии
    --overwrite-photos     перезаписать фото, даже если уже загружены
    --update-prices        обновить base_price/BranchItem.price для уже существующих позиций
                            (по умолчанию цены существующих позиций не трогаются)

Требования: pip install pillow  (requests НЕ нужен — фото берутся локально)
"""

import argparse
import os
import sys
from decimal import Decimal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(BASE_DIR, "photos")

sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.dirname(BASE_DIR))  # на случай запуска не из корня проекта
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.core.files.base import ContentFile
from django.db import transaction

from core.models import Restaurant, Branch
from catalog.models import (
    MenuSet, Category, Item, ItemCategory,
    BranchMenuSet, BranchCategory, BranchItem, BranchCategoryItem,
)

from dua_menu_data import CATEGORIES


def import_data(
    *,
    dry_run: bool = False,
    restaurant_slug: str = "dua",
    restaurant_id: int | None = None,
    no_photos: bool = False,
    overwrite_photos: bool = False,
    update_prices: bool = False,
):
    total_items = sum(len(c["items"]) for c in CATEGORIES)
    items_w_photo = sum(1 for c in CATEGORIES for it in c["items"] if it.get("photo"))
    print(f"Категорий: {len(CATEGORIES)}")
    print(f"Позиций:   {total_items}  (с фото: {items_w_photo})")

    if dry_run:
        print("\n[DRY RUN] — в БД ничего не пишется.\n")
        for cat in CATEGORIES:
            print(f"  [{cat['name_ru']} / {cat['name_ky']} / {cat['name_en']}]")
            for it in cat["items"]:
                photo = "📷" if it.get("photo") else "  "
                print(f"    {photo} {it['name_ru']:<45} {it['price']:>6} сом   "
                      f"(KY: {it['name_ky']} | EN: {it['name_en']})")
        return

    with transaction.atomic():
        # ── Ресторан ──
        if restaurant_id:
            restaurant = Restaurant.objects.get(pk=restaurant_id)
        else:
            restaurant = Restaurant.objects.filter(slug__iexact=restaurant_slug).first()
            if restaurant is None:
                print(f"❌ Ресторан со слагом '{restaurant_slug}' не найден. "
                      f"Передайте --restaurant-id или --restaurant-slug.")
                sys.exit(1)
        print(f"\nРесторан: {restaurant} (id={restaurant.pk})")

        branches = list(Branch.objects.filter(restaurant=restaurant))
        if not branches:
            print("❌ У ресторана нет ни одного филиала (Branch). Нечего обновлять.")
            sys.exit(1)
        print(f"Филиалов найдено: {len(branches)}")
        for b in branches:
            print(f"   — {b.name_ru} (id={b.pk})")

        # ── MenuSet (один на ресторан, общий для всех филиалов) ──
        menu_set, cr = MenuSet.objects.get_or_create(
            restaurant=restaurant,
            name="Основное меню",
            defaults={"is_active": True},
        )
        print(f"{'Создан' if cr else 'Найден'} MenuSet: {menu_set} (id={menu_set.pk})")
        for b in branches:
            BranchMenuSet.objects.get_or_create(branch=b, menu_set=menu_set,
                                                 defaults={"is_active": True})

        stat = dict(cats_new=0, items_new=0, items_upd=0, photos_new=0, branch_items_new=0)
        photo_cache: dict[str, bytes] = {}

        def load_photo(slug: str) -> bytes | None:
            if slug in photo_cache:
                return photo_cache[slug]
            path = os.path.join(PHOTOS_DIR, f"{slug}.jpg")
            if not os.path.exists(path):
                print(f"    ⚠  Фото не найдено: {path}")
                return None
            with open(path, "rb") as f:
                data = f.read()
            photo_cache[slug] = data
            return data

        sort_order = 0
        for cat in CATEGORIES:
            sort_order += 1
            category, created = Category.objects.get_or_create(
                menu_set=menu_set,
                name_ru=cat["name_ru"],
                defaults={"name_ky": cat["name_ky"], "name_en": cat["name_en"]},
            )
            if created:
                stat["cats_new"] += 1
            elif not category.name_ky or not category.name_en:
                category.name_ky = category.name_ky or cat["name_ky"]
                category.name_en = category.name_en or cat["name_en"]
                category.save(update_fields=["name_ky", "name_en"])

            branch_cats = {}
            for b in branches:
                bc, _ = BranchCategory.objects.get_or_create(
                    branch=b, category=category,
                    defaults={"sort_order": sort_order, "is_active": True},
                )
                branch_cats[b.pk] = bc

            item_sort = 0
            for it in cat["items"]:
                item_sort += 1
                name_ru = it["name_ru"]
                price = Decimal(str(it["price"]))

                # NOTE: используем filter().first() вместо get_or_create() —
                # в существующем ресторане могут уже быть задвоенные Item с
                # одинаковым name_ru (расхождение до этого импорта), и
                # get_or_create() падает на них с MultipleObjectsReturned.
                # first() детерминированно берёт самый старый (по id) и не трогает
                # остальные дубли — их можно почистить позже отдельно.
                dupes = list(Item.objects.filter(restaurant=restaurant, name_ru=name_ru).order_by("id"))
                if len(dupes) > 1:
                    print(f"    ⚠  Найдено {len(dupes)} задвоенных Item с именем "
                          f"'{name_ru}' (id={[d.id for d in dupes]}) — использую id={dupes[0].id}, "
                          f"остальные не трогаю.")
                item = dupes[0] if dupes else None
                item_created = False
                if item is None:
                    item = Item.objects.create(
                        restaurant=restaurant,
                        name_ru=name_ru,
                        name_ky=it.get("name_ky", ""),
                        name_en=it.get("name_en", ""),
                        base_price=price,
                        description_ru=it.get("desc_ru", ""),
                        description_ky=it.get("desc_ky", ""),
                        description_en=it.get("desc_en", ""),
                    )
                    item_created = True
                if item_created:
                    stat["items_new"] += 1
                else:
                    changed = []
                    if not item.name_ky and it.get("name_ky"):
                        item.name_ky = it["name_ky"]; changed.append("name_ky")
                    if not item.name_en and it.get("name_en"):
                        item.name_en = it["name_en"]; changed.append("name_en")
                    if not item.description_ru and it.get("desc_ru"):
                        item.description_ru = it["desc_ru"]; changed.append("description_ru")
                    if not item.description_ky and it.get("desc_ky"):
                        item.description_ky = it["desc_ky"]; changed.append("description_ky")
                    if not item.description_en and it.get("desc_en"):
                        item.description_en = it["desc_en"]; changed.append("description_en")
                    if update_prices and item.base_price != price:
                        item.base_price = price; changed.append("base_price")
                    if changed:
                        item.save(update_fields=changed)
                        stat["items_upd"] += 1

                # ── Фото ──
                slug = it.get("photo")
                if not no_photos and slug:
                    need_photo = overwrite_photos or not item.photo
                    if need_photo:
                        raw = load_photo(slug)
                        if raw:
                            fname = f"{slug}.jpg"
                            if item.photo:
                                item.photo.delete(save=False)
                            item.photo.save(fname, ContentFile(raw), save=True)
                            stat["photos_new"] += 1

                ItemCategory.objects.get_or_create(
                    item=item, category=category,
                    defaults={"sort_order": item_sort},
                )

                for b in branches:
                    # Тот же защитный паттерн — BranchItem не имеет unique_together
                    # на (branch, item), так что теоретически тоже могут быть дубли.
                    bi_dupes = list(BranchItem.objects.filter(branch=b, item=item).order_by("id"))
                    branch_item = bi_dupes[0] if bi_dupes else None
                    bi_created = False
                    if branch_item is None:
                        branch_item = BranchItem.objects.create(
                            branch=b, item=item, price=price, is_available=True,
                            sort_order=item_sort, delivery_available=True,
                        )
                        bi_created = True
                    if bi_created:
                        stat["branch_items_new"] += 1
                    elif update_prices and branch_item.price != price:
                        branch_item.price = price
                        branch_item.save(update_fields=["price"])

                    BranchCategoryItem.objects.get_or_create(
                        branch_category=branch_cats[b.pk], branch_item=branch_item,
                        defaults={"sort_order": item_sort},
                    )

    print(f"\n✅ Готово!")
    print(f"   Категорий создано:            {stat['cats_new']}")
    print(f"   Позиций создано:              {stat['items_new']}")
    print(f"   Позиций обновлено (тексты):   {stat['items_upd']}")
    print(f"   Фото сохранено:               {stat['photos_new']}")
    print(f"   BranchItem создано:           {stat['branch_items_new']}")
    print(f"\n   Ресторан ID: {restaurant.pk}")
    print(f"   MenuSet ID:  {menu_set.pk}")
    print(f"   Филиалы:     {', '.join(f'{b.name_ru} (id={b.pk})' for b in branches)}")


def main():
    ap = argparse.ArgumentParser(description="Импорт меню DUA в WebOrdo (все филиалы)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--restaurant-slug", default="dua")
    ap.add_argument("--restaurant-id", type=int, default=None)
    ap.add_argument("--no-photos", action="store_true")
    ap.add_argument("--overwrite-photos", action="store_true")
    ap.add_argument("--update-prices", action="store_true",
                     help="Обновить цены у уже существующих позиций/BranchItem")
    args = ap.parse_args()

    import_data(
        dry_run=args.dry_run,
        restaurant_slug=args.restaurant_slug,
        restaurant_id=args.restaurant_id,
        no_photos=args.no_photos,
        overwrite_photos=args.overwrite_photos,
        update_prices=args.update_prices,
    )


if __name__ == "__main__":
    main()
