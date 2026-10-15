#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Точечная правка меню «СУШИ ОРДО» без переимпорта.

Делает две вещи:
  1) заново ставит фото всем 16 пиццам по сверенной привязке
     (на сайте были перепутаны «Жульен с курочкой» ↔ «Курица в сладком чили»
      и «Маргарита» ↔ «Курочка терияки»);
  2) переименовывает «Комбо «Делюкс Микс» большой» → «Комбо «Пати»»
     (название изменилось в новом PDF).

Меню НЕ удаляется, цены и позиции не трогаются.

Запуск:
    python fix_sushiordo_pizza_photos.py --branch 10 --pizza sushiordo_photos_pizza --dry-run
    python fix_sushiordo_pizza_photos.py --branch 10 --pizza sushiordo_photos_pizza
"""
import argparse
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.core.files import File       # noqa: E402
from django.db import transaction        # noqa: E402

from core.models import Branch           # noqa: E402
from catalog.models import Item, BranchItem   # noqa: E402

from import_sushiordo_menu import (       # noqa: E402
    PIZZA_PHOTO_BY_FILE, PROMO_LABEL, resolve_pizza_photos, slugify_ru,
)

# Переименования из нового PDF: старое название → новые на трёх языках
RENAMES = {
    "Комбо «Делюкс Микс» большой": {
        "name_ru": "Комбо «Пати»",
        "name_ky": "«Пати» комбосу",
        "name_en": "Combo Party",
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", type=int, required=True)
    ap.add_argument("--pizza", required=True, help="папка с фото пицц")
    ap.add_argument("--combo", default="",
                    help="папка с фото комбо-пицц (sushiordo_combo_named)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        branch = Branch.objects.select_related("restaurant").get(id=args.branch)
    except Branch.DoesNotExist:
        sys.exit(f"Филиал id={args.branch} не найден")
    rest = branch.restaurant
    print(f"Филиал {branch.id} — {branch.name_ru} ({rest.name_ru})\n")

    if not os.path.isdir(args.pizza):
        sys.exit(f"Папка не найдена: {args.pizza}")

    print("привязка файлов:")
    photo_for = resolve_pizza_photos(args.pizza)

    missing = [n for n in PIZZA_PHOTO_BY_FILE.values() if n not in photo_for]
    if missing:
        sys.exit("Нет файлов для: " + ", ".join(missing))

    with transaction.atomic():
        print("фото пицц:")
        done = skipped = 0
        for base, path in photo_for.items():
            # фото хранится у Item, а пицца заведена двумя позициями: 30 см и 35 см
            items = list(Item.objects.filter(restaurant=rest, name_ru__startswith=base + " "))
            if not items:
                print(f"  ! не найдено в меню: {base}")
                skipped += 1
                continue
            for it in items:
                print(f"  {it.name_ru:26} ← {os.path.basename(path)[:44]}")
                if args.dry_run:
                    continue
                with open(path, "rb") as fh:
                    it.photo.save(os.path.basename(path), File(fh), save=True)
                done += 1

        # Комбо-пиццы: в PDF у них свои фото — композиции из нескольких пицц,
        # а не снимок одной. Имя файла — транслит названия позиции.
        if args.combo:
            if not os.path.isdir(args.combo):
                sys.exit(f"Папка не найдена: {args.combo}")
            print("\nфото комбо-пицц:")
            for fname in sorted(os.listdir(args.combo)):
                if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                stem = os.path.splitext(fname)[0]
                it = next((i for i in Item.objects.filter(restaurant=rest)
                           if slugify_ru(i.name_ru) == stem), None)
                if not it:
                    print(f"  ! не нашёл позицию для {fname}")
                    skipped += 1
                    continue
                print(f"  {it.name_ru:26} ← {fname[:44]}")
                if args.dry_run:
                    continue
                path = os.path.join(args.combo, fname)
                with open(path, "rb") as fh:
                    it.photo.save(fname, File(fh), save=True)
                done += 1

        print("\nпереименования:")
        for old, new in RENAMES.items():
            it = Item.objects.filter(restaurant=rest, name_ru=old).first()
            if not it:
                print(f"  — «{old}» не найдено (возможно, уже переименовано)")
                continue
            print(f"  «{old}» → «{new['name_ru']}»")
            if args.dry_run:
                continue
            for field, value in new.items():
                setattr(it, field, value)
            it.save(update_fields=list(new))

        # Бейдж на позициях со скидкой: «Выгода» вместо «Акция».
        # Пустой promo_label подставляет «Акция», поэтому проставляем явно.
        badge = BranchItem.objects.filter(branch=branch, old_price__isnull=False)
        wrong = badge.exclude(promo_label=PROMO_LABEL)
        print(f"\nбейдж «{PROMO_LABEL}»: позиций со скидкой {badge.count()}, "
              f"поправить {wrong.count()}")
        if not args.dry_run:
            wrong.update(promo_label=PROMO_LABEL)

        if args.dry_run:
            transaction.set_rollback(True)
            print("\n--dry-run: ничего не изменено.")
            return

    print(f"\nГотово. Обновлено фото: {done}, пропущено пицц: {skipped}")
    print(f"Проверьте: /ru/{branch.id}/menu/")


if __name__ == "__main__":
    main()
