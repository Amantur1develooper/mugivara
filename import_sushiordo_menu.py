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

from core.models import Branch                           # noqa: E402
from catalog.models import (                             # noqa: E402
    MenuSet, Category, Item, ItemCategory,
    BranchMenuSet, BranchCategory, BranchItem, BranchCategoryItem,
)
from sushiordo_menu_data import CATEGORIES               # noqa: E402

# Явная привязка фото пицц к названиям. Ключ — номер снимка в папке
# (файлы сортируются по имени: 1-й, 2-й … 16-й).
# ВНИМАНИЕ: подобрано по виду пиццы на фото. Перед запуском на проде
# сверьтесь со сводкой, которую печатает скрипт.
PIZZA_PHOTO_BY_INDEX = {
    1:  "4 сыра",                  # белая сырная, без томатного соуса
    2:  "Маргарита",               # томатная основа с соусной решёткой
    3:  "Американ хот",            # пепперони + халапеньо
    4:  "4 сезона",                # четыре разные четверти
    5:  "Диабло",                  # пепперони + халапеньо, светлая основа
    6:  "Мясная делюкс",           # ассорти мяса
    7:  "Курочка терияки",         # курица, перец, томаты
    8:  "Пепперони",               # ровная классика
    9:  "Чикен барбекю",           # курица с тёмным соусом барбекю
    10: "Жульен с курочкой",       # грибы и курица в сливочном
    11: "Чизбургер",               # с солёными огурцами
    12: "Курица в сладком чили",   # грибы, лук, светлая
    13: "Банана мама",             # шоколадный топпинг
    14: "Сладкий ордо",            # малина, сахарная пудра
    15: "Половинка",               # половина сыр / половина пепперони
    16: "Ням-Ням",                 # ананас, вишня, кокос
}


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
    # сами Item удаляем только если они больше нигде не используются
    for it in Item.objects.filter(id__in=item_ids):
        if not BranchItem.objects.filter(item=it).exists():
            it.delete()


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
        files = sorted(f for f in os.listdir(args.pizza)
                       if f.lower().endswith((".jpg", ".jpeg", ".png")))
        print("\nпривязка фото пицц (сверьте глазами!):")
        for idx, fname in enumerate(files, start=1):
            name = PIZZA_PHOTO_BY_INDEX.get(idx)
            if not name:
                continue
            pizza_photo[name] = os.path.join(args.pizza, fname)
            print(f"   снимок {idx:2} ({fname[:34]:36}) → {name}")

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
                item = Item.objects.create(
                    restaurant=branch.restaurant,
                    name_ru=data["ru"], name_ky=data["ky"], name_en=data["en"],
                    description_ru=data.get("d_ru", ""),
                    description_ky=data.get("d_ky", ""),
                    description_en=data.get("d_en", ""),
                    base_price=data["price"],
                )
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

                bi = BranchItem.objects.create(
                    branch=branch, item=item, price=data["price"],
                    old_price=data.get("old_price"),
                    is_available=True, delivery_available=True, sort_order=ii)

                BranchCategoryItem.objects.get_or_create(
                    branch_category=bc, branch_item=bi, defaults={"sort_order": ii})

            print(f"  {cat['ru']:26} {len(cat['items']):3} позиций")

    print(f"\nГотово. Категорий: {len(CATEGORIES)}, позиций: {total}, с фото: {with_photo}")
    print(f"Проверьте: /ru/{branch.id}/menu/")


if __name__ == "__main__":
    main()
