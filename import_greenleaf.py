#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Импорт товаров «Грин лиф» из выгрузки кассы (CSV).

Выгрузка сделана не для витрины: колонка ProductGroup содержит не категорию,
а состояние товара — «В работе» или «удаленные». Поэтому категории собираем
сами по названию, а снятые с продажи не переносим.

    python import_greenleaf.py --csv "products грин лиф.csv" --dry-run
    python import_greenleaf.py --csv "products грин лиф.csv"
"""
import argparse
import csv
import io
import os
import re
import sys
from decimal import Decimal, InvalidOperation

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import transaction                          # noqa: E402
from shops.models import (                                 # noqa: E402
    Store, StoreBranch, StoreCategory, StoreProduct, StoreStock,
)

STORE_SLUG_NAME = "Грин лиф"

# Категория определяется по словам в названии. Порядок важен: первое
# совпадение выигрывает, поэтому более узкие правила стоят выше.
RULES = [
    # Порядок важен: первое совпадение выигрывает, узкие правила стоят выше.
    # В выгрузке много опечаток продавца — «мила» вместо мыла, «поршок»
    # вместо порошка, — поэтому ищем и по ним тоже.
    ("Парфюмерия",        ["духи", "парфюм", "одеколон", "аромат лаванд",
                            "мужской аромат", "женский аромат"]),
    ("Стирка",            ["стирк", "стиральн", "порошок", "поршок", "кондиционер для бель",
                            "отбелив", "пятновыводит", "пятен", "бель", "одежд"]),
    ("Уборка дома",       ["очистител", "чистк", "чиски", "чистящ", "унитаз", "плит",
                            "жир", "накип", "стекл", "мытья пола", "для пола", "труб",
                            "ванн", "крышк", "сетка", "шарик", "освежител", "дезодоратор",
                            "запах", "спрей от", "комар"]),
    ("Посуда",            ["посуд", "губк", "мочалк", "салфетк", "сальфетк", "тряпк",
                            "платочк", "бумага", "бумажн"]),
    ("Волосы",            ["шампун", "волос", "перхот", "краск", "бальзам",
                            "ополаскиват", "три мастера"]),
    ("Уход за кожей",     ["крем", "маск", "лиц", "макияж", "пенк", "тональ", "сыворотк",
                            "скраб", "лосьон", "тоник", "умыв", "мусс", "пудр", "подводк",
                            "тушь", "ресниц", "спф", "солнцезащ", "сонце", "коллаген",
                            "калоген", "ниацинамид", "гиалурон", "эссенц", "бб ", "вв крем",
                            "алоэ", "алое", "прыщ", "акне"]),
    ("Гигиена",           ["мыло", "мила", "гель для душа", "гель душ", "душа",
                            "зубн", "зуб щетк", "щетк", "зубочистк", "паста", "прокладк",
                            "ватн", "полости рта", "ополоскователь", "дезодорант",
                            "влажные салфетк", "интим", "женск", "нитью", "уход"]),
    ("Здоровье и БАД",    ["капсул", "пластыр", "витамин", "гриб", "простотит",
                            "сердечно", "лечебн", "таблетк", "сахаром", "кальци"]),
    ("Чай и питание",     ["чай", "кофе", "мёд", "напиток", "конфет", "имбирь",
                            "фасол", "молоко", "сахар"]),
]
DEFAULT_CATEGORY = "Разное"


def guess_category(name):
    low = " " + name.lower().strip() + " "
    for cat, words in RULES:
        for w in words:
            if w in low:
                return cat
    return DEFAULT_CATEGORY


def dec(v, default="0"):
    try:
        return Decimal(str(v).replace(",", ".") or default)
    except (InvalidOperation, ValueError):
        return Decimal(default)


def clean_name(raw):
    """Чистит названия из кассы: лишние пробелы и прилипший штрихкод."""
    name = re.sub(r"\s+", " ", (raw or "").strip())
    # «очиститель плиты6955470950734» — штрихкод приклеен к названию
    name = re.sub(r"(?<=\D)\d{12,14}$", "", name).strip()
    if name.isupper() and len(name) > 12:
        name = name.capitalize()
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--branch", type=int, default=0, help="id филиала для остатков")
    ap.add_argument("--with-deleted", action="store_true",
                    help="переносить и группу «удаленные» (по умолчанию пропускаются)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    store = Store.objects.filter(name_ru__icontains=STORE_SLUG_NAME).first()
    if not store:
        sys.exit(f"Магазин «{STORE_SLUG_NAME}» не найден")
    branch = (StoreBranch.objects.filter(id=args.branch).first() if args.branch
              else StoreBranch.objects.filter(store=store).order_by("id").first())
    if not branch:
        sys.exit("У магазина нет филиалов")

    rows = list(csv.DictReader(io.open(args.csv, encoding="utf-8-sig")))
    keep, skipped = [], 0
    seen_names = set()
    for r in rows:
        group = (r.get("ProductGroup") or "").strip()
        if group == "удаленные" and not args.with_deleted:
            skipped += 1
            continue
        name = clean_name(r.get("Name"))
        if not name:
            skipped += 1
            continue
        key = name.lower()
        if key in seen_names:      # в выгрузке встречаются повторы
            skipped += 1
            continue
        seen_names.add(key)
        keep.append((name, r))

    print(f"Магазин:  {store.name_ru}")
    print(f"Филиал:   #{branch.id} {branch.name_ru}")
    print(f"В файле:  {len(rows)} | переносим: {len(keep)} | пропущено: {skipped}")

    by_cat = {}
    for name, r in keep:
        by_cat.setdefault(guess_category(name), []).append((name, r))
    print("\nКатегории:")
    for cat in sorted(by_cat, key=lambda c: -len(by_cat[c])):
        print(f"   {cat:<18} {len(by_cat[cat])}")

    if args.dry_run:
        print("\n--dry-run: ничего не создано.")
        return

    created = updated = 0
    with transaction.atomic():
        cat_objs = {}
        for i, cat in enumerate(sorted(by_cat)):
            obj, _ = StoreCategory.objects.get_or_create(
                store=store, name_ru=cat,
                defaults={"sort_order": i * 10, "is_active": True})
            cat_objs[cat] = obj

        for cat, items in by_cat.items():
            for name, r in items:
                barcode = (r.get("Barcode") or "").strip()
                price = dec(r.get("Price"))
                cost = dec(r.get("Cost"))
                prod = StoreProduct.objects.filter(store=store, name_ru=name).first()
                if prod is None:
                    prod = StoreProduct(store=store, name_ru=name)
                    created += 1
                else:
                    updated += 1
                prod.category = cat_objs[cat]
                prod.price = price
                prod.cost_price = cost
                prod.barcode = barcode
                prod.is_active = True
                prod.save()

                qty = dec(r.get("Quantity"))
                stock, _ = StoreStock.objects.get_or_create(
                    branch=branch, product=prod, defaults={"qty": Decimal("0")})
                # остаток берём из кассы как есть; отрицательные обнуляем
                stock.qty = qty if qty > 0 else Decimal("0")
                stock.save(update_fields=["qty"])

    print(f"\nСоздано: {created} | обновлено: {updated}")
    print(f"Готово → /ru/shops/b/{branch.id}/")


if __name__ == "__main__":
    main()
