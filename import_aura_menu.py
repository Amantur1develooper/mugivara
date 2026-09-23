#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Создание/обновление ресторана AURA (кафе, Ош) в WebOrdo и импорт полного меню.

Источник данных: aura_menu_data.py (составлено вручную из PDF-меню, RU/KY/EN).
Фото:   папка photos/ рядом со скриптом (JPEG, по одному файлу на слаг).

Это НОВЫЙ ресторан — если он ещё не существует (по слагу), скрипт создаст
Restaurant + один Branch сам, с контактными данными из PDF. Если ресторан
с таким слагом уже есть — просто добавит/обновит меню поверх него.

Запуск (из корня проекта, из активного venv):
    python import_aura_menu.py --dry-run
    python import_aura_menu.py

Параметры:
    --dry-run              показать, что будет импортировано, ничего не писать в БД
    --restaurant-slug S    слаг ресторана (по умолчанию: aura-cafe)
    --restaurant-id N      использовать существующий ресторан по ID вместо создания
    --no-photos            не прикреплять фотографии
    --overwrite-photos     перезаписать фото, даже если уже загружены
    --update-prices        обновить цены у уже существующих позиций

Требования: pip install pillow
"""

import argparse
import os
import sys
from decimal import Decimal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(BASE_DIR, "photos_aura")

sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.dirname(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.core.files.base import ContentFile
from django.db import transaction

from core.models import Restaurant, Branch, PlaceCategory
from catalog.models import (
    MenuSet, Category, Item, ItemCategory,
    BranchMenuSet, BranchCategory, BranchItem, BranchCategoryItem,
)

from aura_menu_data import CATEGORIES

# ── Данные ресторана (из PDF-меню) ──────────────────────────────────────────
RESTAURANT_DEFAULTS = dict(
    name_ru="AURA", name_ky="AURA", name_en="AURA",
    is_active=True,
    about_ru="Кафе быстрого питания AURA в Оше. Пицца, роллы, бургеры, шаурма, "
              "хот-доги, рамёны и многое другое — с доставкой по городу. Халяль.",
    phone="+996880898818",
    whatsapp="+996550889818",
    instagram="https://instagram.com/aura.cafe.osh",
)
BRANCH_DEFAULTS = dict(
    name_ru="AURA — Салиева",
    address="ул. Салиева 10/2, Ош",
    phone="+996550889818",
    is_active=True,
    delivery_enabled=True,
    pay_cash_enabled=True,
    pay_online_enabled=True,
)


def import_data(
    *,
    dry_run: bool = False,
    restaurant_slug: str = "aura-cafe",
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
                print(f"    {photo} {it['name_ru']:<40} {it['price']:>6} сом   "
                      f"(KY: {it['name_ky']} | EN: {it['name_en']})")
        return

    with transaction.atomic():
        # ── Ресторан ──
        if restaurant_id:
            restaurant = Restaurant.objects.get(pk=restaurant_id)
            print(f"\nРесторан: {restaurant} (id={restaurant.pk})")
        else:
            restaurant = Restaurant.objects.filter(slug__iexact=restaurant_slug).first()
            if restaurant is None:
                place_cat = PlaceCategory.objects.filter(name_ru="Рестораны").first()
                restaurant = Restaurant.objects.create(
                    slug=restaurant_slug,
                    place_category=place_cat,
                    **RESTAURANT_DEFAULTS,
                )
                print(f"\n✅ Создан НОВЫЙ ресторан: {restaurant} (id={restaurant.pk})")
            else:
                print(f"\nНайден существующий ресторан: {restaurant} (id={restaurant.pk})")

        # ── Филиал ──
        branches = list(Branch.objects.filter(restaurant=restaurant))
        if not branches:
            branch = Branch.objects.create(restaurant=restaurant, **BRANCH_DEFAULTS)
            branches = [branch]
            print(f"✅ Создан филиал: {branch} (id={branch.pk})")
        else:
            print(f"Филиалов найдено: {len(branches)}")
            for b in branches:
                print(f"   — {b.name_ru} (id={b.pk})")

        # ── MenuSet ──
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

                # Защита от возможных задвоенных Item (см. import_dua_menu.py) —
                # на новом ресторане маловероятно, но не помешает.
                dupes = list(Item.objects.filter(restaurant=restaurant, name_ru=name_ru).order_by("id"))
                if len(dupes) > 1:
                    print(f"    ⚠  Найдено {len(dupes)} задвоенных Item с именем "
                          f"'{name_ru}' — использую id={dupes[0].id}.")
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
    print(f"\n   Ресторан ID: {restaurant.pk}  (slug: {restaurant.slug})")
    print(f"   MenuSet ID:  {menu_set.pk}")
    print(f"   Филиалы:     {', '.join(f'{b.name_ru} (id={b.pk})' for b in branches)}")


def main():
    ap = argparse.ArgumentParser(description="Импорт меню AURA cafe в WebOrdo")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--restaurant-slug", default="aura-cafe")
    ap.add_argument("--restaurant-id", type=int, default=None)
    ap.add_argument("--no-photos", action="store_true")
    ap.add_argument("--overwrite-photos", action="store_true")
    ap.add_argument("--update-prices", action="store_true")
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
