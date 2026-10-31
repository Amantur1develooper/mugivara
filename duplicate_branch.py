#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Создаёт новый филиал ресторана как копию существующего.

Копируется всё, что описывает «как работает точка»:
  • настройки филиала (доставка, часы, Telegram, оформление);
  • привязки наборов меню, категории и их порядок;
  • блюда с ценами, скидками и бейджами, их раскладка по категориям;
  • техкарты с ингредиентами и шагами приготовления;
  • список ингредиентов для склада — с НУЛЕВЫМ остатком.

Не копируется то, что принадлежит старой точке: заказы, брони, столики,
движения склада, промокоды и доступы сотрудников.

Блюда (Item) и ингредиенты (Ingredient) принадлежат ресторану, а не филиалу,
поэтому они переиспользуются — новых дублей в справочниках не появляется.

    python duplicate_branch.py --source 11 --name "Курманжан Датка" \
        --address "Курманжан Датка 99А" --phone "+996557229593" \
        --map "https://2gis.kg/..." --dry-run
"""
import argparse
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import transaction                     # noqa: E402

from core.models import Branch                        # noqa: E402
from catalog.models import (                          # noqa: E402
    BranchCategory, BranchCategoryItem, BranchItem, BranchMenuSet,
)
from techcards.models import (                        # noqa: E402
    IngredientStock, TechCard, TechCardIngredient, TechCardStep,
)

# поля филиала, которые НЕ переносим: они либо уникальны для точки,
# либо задаются аргументами
SKIP_BRANCH_FIELDS = {
    "id", "pk", "created_at", "updated_at",
    "name_ru", "name_ky", "name_en",
    "address", "phone", "whatsapp", "map_url", "lat", "lon",
    "slug", "qr_token",
}


def copy_branch(src, name, address, phone, map_url, dry):
    """Создаёт новый Branch с настройками исходного."""
    clean = _extra(src, SKIP_BRANCH_FIELDS)
    clean["restaurant_id"] = src.restaurant_id
    clean["name_ru"] = clean["name_ky"] = clean["name_en"] = name
    clean["address"] = address
    clean["phone"] = phone
    clean["map_url"] = map_url
    if dry:
        print("  [dry-run] создал бы филиал:", name)
        return None
    new = Branch(**clean)
    new.save()
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=int, required=True, help="id филиала-образца")
    ap.add_argument("--name", required=True)
    ap.add_argument("--address", default="")
    ap.add_argument("--phone", default="")
    ap.add_argument("--map", dest="map_url", default="")
    ap.add_argument("--with-stock", action="store_true",
                    help="перенести и сами остатки (по умолчанию нули)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        src = Branch.objects.get(id=args.source)
    except Branch.DoesNotExist:
        sys.exit(f"Филиал #{args.source} не найден")

    print(f"Образец:  #{src.id} {src.name_ru}  (ресторан: {src.restaurant.name_ru})")
    print(f"Новый:    {args.name}")
    print(f"  адрес:  {args.address or '—'}")
    print(f"  тел.:   {args.phone or '—'}")
    print(f"  карта:  {args.map_url or '—'}")
    print()

    with transaction.atomic():
        new = copy_branch(src, args.name, args.address, args.phone, args.map_url, args.dry_run)

        # ── наборы меню ──
        sets = list(BranchMenuSet.objects.filter(branch=src))
        if not args.dry_run:
            BranchMenuSet.objects.bulk_create([
                BranchMenuSet(branch=new, menu_set_id=s.menu_set_id,
                              **_extra(s, {"branch", "menu_set", "id"}))
                for s in sets
            ])
        print(f"  наборы меню:   {len(sets)}")

        # ── категории ──
        cat_map = {}
        cats = list(BranchCategory.objects.filter(branch=src))
        for c in cats:
            if args.dry_run:
                continue
            nc = BranchCategory(branch=new, category_id=c.category_id,
                                **_extra(c, {"branch", "category", "id"}))
            nc.save()
            cat_map[c.id] = nc
        print(f"  категории:     {len(cats)}")

        # ── блюда ──
        item_map = {}
        items = list(BranchItem.objects.filter(branch=src))
        for bi in items:
            if args.dry_run:
                continue
            nb = BranchItem(branch=new, item_id=bi.item_id,
                            **_extra(bi, {"branch", "item", "id"}))
            nb.save()
            item_map[bi.id] = nb
        print(f"  блюда:         {len(items)}")

        # ── раскладка блюд по категориям ──
        links = list(BranchCategoryItem.objects.filter(branch_category__branch=src))
        if not args.dry_run:
            BranchCategoryItem.objects.bulk_create([
                BranchCategoryItem(
                    branch_category=cat_map[l.branch_category_id],
                    branch_item=item_map[l.branch_item_id],
                    **_extra(l, {"branch_category", "branch_item", "id"}))
                for l in links
                if l.branch_category_id in cat_map and l.branch_item_id in item_map
            ])
        print(f"  связи катег.:  {len(links)}")

        # ── техкарты ──
        cards = list(TechCard.objects.filter(branch=src).prefetch_related("ingredients", "steps"))
        semi_map = {}
        for tc in cards:
            if args.dry_run:
                continue
            ntc = TechCard(branch=new, item_id=tc.item_id,
                           **_extra(tc, {"branch", "item", "id"}))
            ntc.save()
            semi_map[tc.id] = ntc
        n_ing = n_step = 0
        for tc in cards:
            if args.dry_run:
                n_ing += tc.ingredients.count()
                n_step += tc.steps.count()
                continue
            ntc = semi_map[tc.id]
            for line in tc.ingredients.all():
                TechCardIngredient.objects.create(
                    tech_card=ntc,
                    ingredient_id=line.ingredient_id,
                    # полуфабрикат — это другая техкарта, подставляем её копию
                    semi_finished=semi_map.get(line.semi_finished_id),
                    **_extra(line, {"tech_card", "ingredient", "semi_finished", "id"}))
                n_ing += 1
            for st in tc.steps.all():
                TechCardStep.objects.create(tech_card=ntc,
                                            **_extra(st, {"tech_card", "id"}))
                n_step += 1
        print(f"  техкарты:      {len(cards)}  (строк: {n_ing}, шагов: {n_step})")

        # ── ингредиенты склада ──
        stocks = list(IngredientStock.objects.filter(branch=src))
        if not args.dry_run:
            rows = []
            for s in stocks:
                extra = _extra(s, {"branch", "ingredient", "id"})
                if not args.with_stock:
                    # новая точка физически пустая: переносим номенклатуру,
                    # а остатки обнуляем, иначе отчёты покажут несуществующий товар
                    for fld in ("quantity", "qty", "amount"):
                        if fld in extra:
                            extra[fld] = 0
                rows.append(IngredientStock(branch=new, ingredient_id=s.ingredient_id, **extra))
            IngredientStock.objects.bulk_create(rows)
        print(f"  ингредиенты:   {len(stocks)}"
              f"  ({'с остатками' if args.with_stock else 'остатки обнулены'})")

        if args.dry_run:
            print("\n--dry-run: ничего не создано.")
            transaction.set_rollback(True)
            return

    print(f"\nГотово. Новый филиал #{new.id} → /ru/{new.id}/menu/")


def _extra(obj, skip):
    """Все простые поля объекта, кроме перечисленных."""
    out = {}
    for f in obj._meta.concrete_fields:
        if f.primary_key or f.name in skip:
            continue
        out[f.attname if f.is_relation else f.name] = getattr(
            obj, f.attname if f.is_relation else f.name)
    return out


if __name__ == "__main__":
    main()
