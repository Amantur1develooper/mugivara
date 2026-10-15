#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Замена меню «СУШИ ОРДО» на новое из PDF.

ВНИМАНИЕ: скрипт УДАЛЯЕТ всё текущее меню указанного филиала
(категории, блюда, фото) и создаёт новое на трёх языках.

Запуск:
    python import_sushiordo_menu.py --branch 10 --photos /path/to/photos --dry-run
    python import_sushiordo_menu.py --branch 10 --photos /path/to/photos --yes

Ключи:
    --branch N    ID филиала (на проде у «Суши Ордо» это 10)
    --photos DIR  папка с фото блюд (имена вида «категория__название.jpg»)
    --pizza DIR   папка с фото пицц (pizza_01.jpg … по порядку меню)
    --dry-run     только показать, что будет сделано, ничего не менять
    --yes         подтвердить удаление старого меню
"""
import argparse
import os
import re
import sys
import unicodedata

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.core.files import File                      # noqa: E402
from django.db import transaction                        # noqa: E402
from django.db.models.deletion import ProtectedError     # noqa: E402

from core.models import Branch                           # noqa: E402
from catalog.models import (                             # noqa: E402
    MenuSet, Category, Item, ItemCategory,
    BranchMenuSet, BranchCategory, BranchItem, BranchCategoryItem,
)
from sushiordo_menu_data import CATEGORIES               # noqa: E402

# Надпись на бейдже у позиций со скидкой (пусто → подставится «Акция»)
PROMO_LABEL = "Выгода"

# Привязка фото пицц к названиям по ИМЕНИ ФАЙЛА — сверено поштучно с
# фотографиями пицц из PDF (стр. 4): каждое фото из папки сличалось с
# эталоном в меню. Ключ — имя файла (без учёта регистра).
PIZZA_PHOTO_BY_FILE = {
    "whatsapp image 2026-10-14 at 21.02.49 (1).jpeg": "4 сыра",                # белая сырная
    "whatsapp image 2026-10-14 at 21.02.49 (2).jpeg": "Курочка терияки",       # решётка соуса
    "whatsapp image 2026-10-14 at 21.02.49 (3).jpeg": "Американ хот",          # пепперони + халапеньо
    "whatsapp image 2026-10-14 at 21.02.49.jpeg":     "4 сезона",              # четыре четверти
    "whatsapp image 2026-10-14 at 21.02.50 (1).jpeg": "Диабло",                # густо пепперони + халапеньо
    "whatsapp image 2026-10-14 at 21.02.50 (2).jpeg": "Мясная делюкс",         # мясное ассорти
    "whatsapp image 2026-10-14 at 21.02.50.jpeg":     "Маргарита",             # томаты, зелень
    "whatsapp image 2026-10-14 at 21.02.51 (1).jpeg": "Пепперони",             # ровная классика
    "whatsapp image 2026-10-14 at 21.02.51 (2).jpeg": "Чикен барбекю",         # тёмный соус барбекю
    "whatsapp image 2026-10-14 at 21.02.51 (3).jpeg": "Курица в сладком чили", # курица, крошка
    "whatsapp image 2026-10-14 at 21.02.51 (4).jpeg": "Чизбургер",             # солёные огурцы
    "whatsapp image 2026-10-14 at 21.02.51 (5).jpeg": "Жульен с курочкой",     # грибы и курица
    "whatsapp image 2026-10-14 at 21.02.51 (6).jpeg": "Банана мама",           # шоколадная решётка
    "whatsapp image 2026-10-14 at 21.02.51 (7).jpeg": "Сладкий ордо",          # малина, сливочный соус
    "whatsapp image 2026-10-14 at 21.02.51.jpeg":     "Половинка",             # половина сыр / пепперони
    "whatsapp image 2026-10-14 at 21.02.52.jpeg":     "Ням-Ням",               # ананас, вишня, кокос
}

# Запасной вариант, если файлы переименуют: порядок сортировки по имени.
PIZZA_PHOTO_BY_INDEX = {
    i: name for i, name in enumerate(PIZZA_PHOTO_BY_FILE.values(), start=1)
}


def resolve_pizza_photos(folder):
    """Возвращает {название пиццы: путь к файлу}.

    Порядок попыток для каждого файла:
      1) имя файла — транслит названия пиццы (папка sushiordo_pizza_named);
         тогда порядок и переименования файлов ни на что не влияют;
      2) исходное имя из WhatsApp;
      3) в последнюю очередь — порядковый номер в сортировке по имени.
    """
    files = sorted(f for f in os.listdir(folder)
                   if f.lower().endswith((".jpg", ".jpeg", ".png")))
    by_slug = {slugify_ru(n): n for n in PIZZA_PHOTO_BY_FILE.values()}
    out = {}
    for idx, fname in enumerate(files, start=1):
        stem = os.path.splitext(fname)[0].lower()
        name = (by_slug.get(stem)
                or PIZZA_PHOTO_BY_FILE.get(fname.lower())
                or PIZZA_PHOTO_BY_INDEX.get(idx))
        if not name:
            print(f"   снимок {idx:2} ({fname[:40]}) → не опознан, пропуск")
            continue
        out[name] = os.path.join(folder, fname)
        print(f"   {name:24} ← {fname[:44]}")
    missing = [n for n in PIZZA_PHOTO_BY_FILE.values() if n not in out]
    if missing:
        print(f"   ! без фото останутся: {', '.join(missing)}")
    return out


def slugify_ru(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).lower().replace("ё", "е")
    tr = str.maketrans("абвгдежзийклмнопрстуфхцчшщъыьэюя",
                       "abvgdejziyklmnoprstufhccss'y'eua")
    s = s.translate(tr)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60]


def wipe_menu(branch, dry=False):
    """Удаляет текущее меню филиала."""
    bcs = BranchCategory.objects.filter(branch=branch)
    bis = BranchItem.objects.filter(branch=branch)
    links = BranchCategoryItem.objects.filter(branch_category__branch=branch)
    # ВАЖНО: список id фиксируем ДО удаления связей, иначе после удаления
    # BranchItem ленивый queryset вернёт пусто и старые блюда останутся
    item_ids = list(Item.objects.filter(branch_items__branch=branch)
                    .distinct().values_list("id", flat=True))

    print(f"  категорий:     {bcs.count()}")
    print(f"  позиций:       {bis.count()}")
    print(f"  связей:        {links.count()}")
    print(f"  блюд (Item):   {len(item_ids)}")
    if dry:
        return

    links.delete()
    bis.delete()
    bcs.delete()
    # Сами блюда удаляем, только если они больше нигде не используются.
    # Блюда, попавшие в историю заказов, Django защищает (OrderItem.item = PROTECT) —
    # такие оставляем: из меню они уже убраны, а старые чеки останутся целыми.
    kept = 0
    for it in Item.objects.filter(id__in=item_ids):
        if BranchItem.objects.filter(item=it).exists():
            continue
        try:
            it.delete()
        except ProtectedError:
            kept += 1
    if kept:
        print(f"  оставлено блюд из истории заказов: {kept}")


def attach_photo(item, path):
    if not path or not os.path.exists(path):
        return False
    with open(path, "rb") as fh:
        item.photo.save(os.path.basename(path), File(fh), save=True)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", type=int, required=True)
    ap.add_argument("--photos", default="")
    ap.add_argument("--pizza", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    try:
        branch = Branch.objects.select_related("restaurant").get(id=args.branch)
    except Branch.DoesNotExist:
        sys.exit(f"Филиал id={args.branch} не найден")

    total = sum(len(c["items"]) for c in CATEGORIES)
    print(f"Филиал: {branch.id} — {branch.name_ru} ({branch.restaurant.name_ru})")
    print(f"Новое меню: {len(CATEGORIES)} категорий, {total} позиций\n")
    print("Будет удалено текущее меню:")
    wipe_menu(branch, dry=True)

    if args.dry_run:
        print("\n--dry-run: ничего не изменено.")
        return
    if not args.yes:
        sys.exit("\nДобавьте --yes, чтобы подтвердить удаление старого меню.")

    pizza_photo = {}
    if args.pizza and os.path.isdir(args.pizza):
        print("\nпривязка фото пицц:")
        pizza_photo = resolve_pizza_photos(args.pizza)

    with transaction.atomic():
        print("\nудаляю старое меню…")
        wipe_menu(branch)

        menu_set, _ = MenuSet.objects.get_or_create(
            restaurant=branch.restaurant, name="Меню", defaults={"is_active": True})
        menu_set.is_active = True
        menu_set.save(update_fields=["is_active"])
        BranchMenuSet.objects.get_or_create(branch=branch, menu_set=menu_set,
                                            defaults={"is_active": True})

        with_photo = 0
        for ci, cat in enumerate(CATEGORIES, start=1):
            category, _ = Category.objects.get_or_create(
                menu_set=menu_set, name_ru=cat["ru"],
                defaults={"name_ky": cat["ky"], "name_en": cat["en"]})
            category.name_ky, category.name_en = cat["ky"], cat["en"]
            category.save(update_fields=["name_ky", "name_en"])

            bc, _ = BranchCategory.objects.get_or_create(
                branch=branch, category=category,
                defaults={"sort_order": ci, "is_active": True})
            bc.sort_order, bc.is_active = ci, True
            bc.save(update_fields=["sort_order", "is_active"])

            for ii, data in enumerate(cat["items"], start=1):
                # Блюдо с таким названием может остаться от старого меню
                # (если оно есть в истории заказов и его нельзя было удалить) —
                # тогда переиспользуем его и обновляем поля, а не плодим дубликат:
                # у Item уникальна пара (ресторан, название).
                item, _created = Item.objects.get_or_create(
                    restaurant=branch.restaurant, name_ru=data["ru"],
                )
                item.name_ky = data["ky"]
                item.name_en = data["en"]
                item.description_ru = data.get("d_ru", "")
                item.description_ky = data.get("d_ky", "")
                item.description_en = data.get("d_en", "")
                item.base_price = data["price"]
                item.save()
                # фото
                path = None
                if cat["slug"] == "pizza":
                    base = data["ru"].replace(" 30 см", "").replace(" 35 см", "")
                    path = pizza_photo.get(base)
                elif args.photos:
                    fname = f'{cat["slug"]}__{slugify_ru(data["ru"])}.jpg'
                    cand = os.path.join(args.photos, fname)
                    path = cand if os.path.exists(cand) else None
                if attach_photo(item, path):
                    with_photo += 1

                ItemCategory.objects.get_or_create(
                    item=item, category=category, defaults={"sort_order": ii})

                # На позициях со старой ценой бейдж подписываем «Выгода»
                # (если текст не задать, подставляется «Акция»).
                bi = BranchItem.objects.create(
                    branch=branch, item=item, price=data["price"],
                    old_price=data.get("old_price"),
                    promo_label=PROMO_LABEL if data.get("old_price") else "",
                    is_available=True, delivery_available=True, sort_order=ii)

                BranchCategoryItem.objects.get_or_create(
                    branch_category=bc, branch_item=bi, defaults={"sort_order": ii})

            print(f"  {cat['ru']:26} {len(cat['items']):3} позиций")

    print(f"\nГотово. Категорий: {len(CATEGORIES)}, позиций: {total}, с фото: {with_photo}")
    print(f"Проверьте: /ru/{branch.id}/menu/")


if __name__ == "__main__":
    main()
