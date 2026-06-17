#!/usr/bin/env python
"""
Импорт меню ресторана Deniz (https://deniz.kg) в WebOrdo.
Парсит встроенный JSON из страницы — получает все 219 позиций с:
  - названиями, описаниями, весом, ценами
  - фотографиями (скачивает и сжимает до 600×600 px, JPEG 80%)
  - категориями и правильным sort_order

Запуск (из корня проекта):
    python import_deniz_menu.py

Параметры:
    --dry-run              показать что будет импортировано, без записи в БД
    --restaurant-id N      использовать существующий ресторан (не создавать)
    --branch-id N          использовать существующий филиал (не создавать)
    --no-photos            не скачивать фотографии
    --overwrite-photos     перезаписать фото даже если уже есть

Требования: pip install pillow  (requests уже есть в проекте)
"""

import argparse
import io
import json
import os
import re
import sys
import html as html_mod
import time
from decimal import Decimal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

import requests
from django.core.files.base import ContentFile
from django.db import transaction

from core.models import Restaurant, Branch
from catalog.models import (
    MenuSet, Category, Item, ItemCategory,
    BranchMenuSet, BranchCategory, BranchItem, BranchCategoryItem,
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

MAX_PHOTO_SIZE = (600, 600)
JPEG_QUALITY = 80


# ── Декодирование Astro-сериализации ─────────────────────────────────────────

def _astro(v):
    """Рекурсивно распаковывает Astro-формат [type_index, value]."""
    if not isinstance(v, list) or len(v) != 2:
        return v
    t, val = v
    if t == 0:
        if isinstance(val, dict):
            return {k: _astro(vv) for k, vv in val.items()}
        if isinstance(val, list):
            return [_astro(i) for i in val]
        return val
    if t == 1:
        return [_astro(i) for i in val]
    return val


# ── Парсинг HTML ──────────────────────────────────────────────────────────────

def scrape(url: str = "https://deniz.kg/") -> tuple[list, list]:
    """
    Возвращает (categories, items) — списки dict'ов.

    Категория: {id, name_ru, sort_order}
    Позиция:   {id, category_id, name_ru, description_ru, price, weight, image_url, sort_order}
    """
    print(f"Загрузка {url} ...")
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"
    html = r.text

    # Найдём <astro-island> содержащий данные меню
    idx = html.find("&quot;menu_items&quot;")
    if idx == -1:
        raise RuntimeError("Данные меню не найдены на странице. Сайт мог измениться.")

    island_start = html.rfind("<astro-island", 0, idx)
    island_end   = html.find("</astro-island>", idx) + len("</astro-island>")
    island       = html[island_start:island_end]

    props_m = re.search(r'\bprops="({.*?})"\s', island, re.DOTALL)
    if not props_m:
        raise RuntimeError("Атрибут props не найден в astro-island.")

    props = json.loads(html_mod.unescape(props_m.group(1)))
    data  = _astro(props["data"])      # внутри ещё [0, {...}]

    raw_cats  = data["categories"]
    raw_items = data["menu_items"]

    categories = [
        {
            "id":        c["id"],
            "name_ru":   c["name"]["ru"],
            "sort_order": c["sort_order"],
        }
        for c in raw_cats
        if c.get("is_active", True)
    ]

    items = [
        {
            "id":             it["id"],
            "category_id":    it["category_id"],
            "name_ru":        it["name"]["ru"],
            "description_ru": (it.get("description") or {}).get("ru", ""),
            "price":          it.get("price") or 0,
            "weight":         it.get("weight"),       # int или None
            "image_url":      it.get("image_url"),    # str или None
            "sort_order":     it.get("sort_order", 0),
        }
        for it in raw_items
        if it.get("is_active", True)
    ]

    return categories, items


# ── Сжатие фото ───────────────────────────────────────────────────────────────

def compress_image(raw_bytes: bytes) -> bytes:
    from PIL import Image
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    img.thumbnail(MAX_PHOTO_SIZE, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()


def fetch_photo(url: str, session: requests.Session) -> bytes | None:
    try:
        r = session.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return compress_image(r.content)
    except Exception as e:
        print(f"    ⚠  Не удалось загрузить фото: {e}")
        return None


# ── Импорт ────────────────────────────────────────────────────────────────────

def import_data(
    categories: list,
    items: list,
    *,
    dry_run: bool = False,
    restaurant_id: int | None = None,
    branch_id: int | None = None,
    no_photos: bool = False,
    overwrite_photos: bool = False,
):
    cat_map = {c["id"]: c for c in categories}    # original_id → category dict
    items_by_cat = {}
    for it in items:
        items_by_cat.setdefault(it["category_id"], []).append(it)

    total_items  = len(items)
    items_w_photo = sum(1 for it in items if it["image_url"])
    items_w_desc  = sum(1 for it in items if it["description_ru"])

    print(f"\nКатегорий: {len(categories)}")
    print(f"Позиций:   {total_items}  (с фото: {items_w_photo},  с описанием: {items_w_desc})")

    if dry_run:
        print("\n[DRY RUN] — в БД ничего не пишется.\n")
        for cat in sorted(categories, key=lambda c: c["sort_order"]):
            print(f"  [{cat['name_ru']}]")
            for it in items_by_cat.get(cat["id"], []):
                photo  = "📷" if it["image_url"] else "  "
                desc   = f"  ({it['description_ru']})" if it["description_ru"] else ""
                weight = f"  {it['weight']}г"          if it["weight"]         else ""
                price  = f"{it['price']} сом"          if it["price"]          else "цена не указана"
                print(f"    {photo} {it['name_ru']}{desc}{weight} — {price}")
        return

    session = requests.Session()

    with transaction.atomic():
        # ── Ресторан ──
        if restaurant_id:
            restaurant = Restaurant.objects.get(pk=restaurant_id)
            print(f"\nРесторан: {restaurant} (id={restaurant.pk})")
        else:
            restaurant, cr = Restaurant.objects.get_or_create(
                slug="deniz",
                defaults={
                    "name_ru": "Deniz",
                    "name_ky": "Deniz",
                    "name_en": "Deniz",
                    "is_active": True,
                },
            )
            print(f"\n{'Создан' if cr else 'Найден'} ресторан: {restaurant} (id={restaurant.pk})")

        # ── Филиал ──
        if branch_id:
            branch = Branch.objects.get(pk=branch_id)
            print(f"Филиал: {branch} (id={branch.pk})")
        else:
            branch, cr = Branch.objects.get_or_create(
                restaurant=restaurant,
                name_ru="Deniz — Ош",
                defaults={
                    "is_active": True,
                    "delivery_enabled": True,
                    "pay_cash_enabled": True,
                    "pay_online_enabled": True,
                    "address": "г. Ош",
                },
            )
            print(f"{'Создан' if cr else 'Найден'} филиал: {branch} (id={branch.pk})")

        # ── MenuSet ──
        menu_set, cr = MenuSet.objects.get_or_create(
            restaurant=restaurant,
            name="Основное меню",
            defaults={"is_active": True},
        )
        print(f"{'Создан' if cr else 'Найден'} MenuSet: {menu_set} (id={menu_set.pk})")
        BranchMenuSet.objects.get_or_create(branch=branch, menu_set=menu_set,
                                            defaults={"is_active": True})

        # ── Категории и позиции ──
        stat = dict(cats_new=0, items_new=0, items_upd=0, photos_new=0)

        # Маппинг original_cat_id → Category (Django)
        django_cats: dict[int, Category] = {}

        for cat in sorted(categories, key=lambda c: c["sort_order"]):
            orig_id = cat["id"]

            category, created = Category.objects.get_or_create(
                menu_set=menu_set,
                name_ru=cat["name_ru"],
                defaults={"name_ky": cat["name_ru"], "name_en": cat["name_ru"]},
            )
            if created:
                stat["cats_new"] += 1
            django_cats[orig_id] = category

            branch_cat, _ = BranchCategory.objects.get_or_create(
                branch=branch,
                category=category,
                defaults={"sort_order": cat["sort_order"], "is_active": True},
            )

            for it in items_by_cat.get(orig_id, []):
                name_ru    = it["name_ru"]
                price      = Decimal(it["price"])
                desc_ru    = it["description_ru"] or ""

                item, item_created = Item.objects.get_or_create(
                    restaurant=restaurant,
                    name_ru=name_ru,
                    defaults={
                        "name_ky":        name_ru,
                        "name_en":        name_ru,
                        "base_price":     price,
                        "description_ru": desc_ru,
                    },
                )

                # Обновляем описание если позиция уже существовала и описание пустое
                if not item_created and desc_ru and not item.description_ru:
                    item.description_ru = desc_ru
                    item.save(update_fields=["description_ru"])
                    stat["items_upd"] += 1

                if item_created:
                    stat["items_new"] += 1

                # Фото
                if not no_photos and it["image_url"]:
                    need_photo = overwrite_photos or not item.photo
                    if need_photo:
                        print(f"  📷 {name_ru} ...", end=" ", flush=True)
                        raw = fetch_photo(it["image_url"], session)
                        if raw:
                            fname = re.sub(r"[^\w]", "_", name_ru)[:50] + ".jpg"
                            if item.photo:
                                item.photo.delete(save=False)
                            item.photo.save(fname, ContentFile(raw), save=True)
                            stat["photos_new"] += 1
                            print(f"✅ ({len(raw)//1024} КБ)")
                        time.sleep(0.05)

                ItemCategory.objects.get_or_create(
                    item=item, category=category,
                    defaults={"sort_order": it["sort_order"]},
                )

                branch_item, _ = BranchItem.objects.get_or_create(
                    branch=branch, item=item,
                    defaults={
                        "price":              price,
                        "is_available":       True,
                        "sort_order":         it["sort_order"],
                        "delivery_available": True,
                    },
                )

                BranchCategoryItem.objects.get_or_create(
                    branch_category=branch_cat, branch_item=branch_item,
                    defaults={"sort_order": it["sort_order"]},
                )

    print(f"\n✅ Готово!")
    print(f"   Категорий создано:         {stat['cats_new']}")
    print(f"   Позиций создано:           {stat['items_new']}")
    print(f"   Позиций обновлено (описание): {stat['items_upd']}")
    print(f"   Фото сохранено:            {stat['photos_new']}")
    print(f"\n   Ресторан ID: {restaurant.pk}")
    print(f"   Филиал ID:   {branch.pk}")
    print(f"   MenuSet ID:  {menu_set.pk}")


# ── Точка входа ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Импорт меню deniz.kg в WebOrdo")
    ap.add_argument("--dry-run",          action="store_true")
    ap.add_argument("--restaurant-id",    type=int, default=None)
    ap.add_argument("--branch-id",        type=int, default=None)
    ap.add_argument("--no-photos",        action="store_true")
    ap.add_argument("--overwrite-photos", action="store_true",
                    help="Перезаписать фото даже если уже загружены")
    args = ap.parse_args()

    try:
        categories, items = scrape()
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        sys.exit(1)

    import_data(
        categories, items,
        dry_run=args.dry_run,
        restaurant_id=args.restaurant_id,
        branch_id=args.branch_id,
        no_photos=args.no_photos,
        overwrite_photos=args.overwrite_photos,
    )


if __name__ == "__main__":
    main()
