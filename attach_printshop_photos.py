#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Обновляет услуги полиграф-центра "Ош Принт" (webordo.kg/ru/printshop/Osh_print/):
прикрепляет фото + заполняет name_ky/name_en/description_ru/ky/en.

Источник данных: printshop_data.py (ITEMS: name_ru -> photo/переводы/описания)
+ папка photos_printshop/ (JPEG, по слагу, из свободных источников — Pexels).

НЕ создаёт новые товары/категории — только обновляет уже существующие
PrintProduct по совпадению name_ru (регистронезависимо) в рамках центра.
Если под одним названием несколько товаров (например, категория "Бейджики"
дублирует часть "Продукция для ресторанов") — обновляются все совпадения.

По умолчанию тексты (переводы/описания) заполняются, только если поле
сейчас пустое — существующие непустые name_ky/description_ru и т.п. не
трогаются. Фото — только если его ещё нет. Флаги --overwrite-* включают
принудительную перезапись.

Запуск (из корня проекта, из активного venv):
    python attach_printshop_photos.py --dry-run
    python attach_printshop_photos.py

Параметры:
    --dry-run              показать, что будет сделано, не писать в БД
    --center-slug S        слаг центра (по умолчанию: Osh_print)
    --overwrite-photos     перезаписать фото, даже если уже есть
    --overwrite-text       перезаписать переводы/описания, даже если уже заполнены
"""
import argparse
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(BASE_DIR, "photos_printshop")

sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.dirname(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.core.files.base import ContentFile

from printshop.models import PrintCenter, PrintProduct
from printshop_data import ITEMS


def _norm(s: str) -> str:
    return " ".join(s.strip().split()).casefold()


def run(*, dry_run: bool, center_slug: str, overwrite_photos: bool, overwrite_text: bool):
    center = PrintCenter.objects.filter(slug__iexact=center_slug).first()
    if center is None:
        print(f"❌ Центр со слагом '{center_slug}' не найден.")
        sys.exit(1)
    print(f"Центр: {center} (id={center.pk})")

    all_products = list(PrintProduct.objects.filter(center=center))
    print(f"Товаров/услуг у центра всего: {len(all_products)}")

    products_by_norm: dict[str, list] = {}
    for p in all_products:
        products_by_norm.setdefault(_norm(p.name_ru), []).append(p)

    photo_cache: dict[str, bytes] = {}

    def load_photo(slug: str):
        if slug in photo_cache:
            return photo_cache[slug]
        path = os.path.join(PHOTOS_DIR, f"{slug}.jpg")
        if not os.path.exists(path):
            print(f"    ⚠  Файл фото не найден: {path}")
            return None
        with open(path, "rb") as f:
            data = f.read()
        photo_cache[slug] = data
        return data

    photos_updated = 0
    text_updated = 0
    not_found_in_db = []
    seen_norm_keys = set()

    for name_ru, data in ITEMS.items():
        norm_key = _norm(name_ru)
        if norm_key in seen_norm_keys:
            continue  # тот же товар уже обработан под другим написанием регистра
        seen_norm_keys.add(norm_key)

        products = products_by_norm.get(norm_key, [])
        if not products:
            not_found_in_db.append(name_ru)
            continue

        for p in products:
            changed_fields = []

            if overwrite_text or not p.name_ky:
                p.name_ky = data.get("name_ky", "") or p.name_ky
                changed_fields.append("name_ky")
            if overwrite_text or not p.name_en:
                p.name_en = data.get("name_en", "") or p.name_en
                changed_fields.append("name_en")
            if overwrite_text or not p.description_ru:
                p.description_ru = data.get("desc_ru", "") or p.description_ru
                changed_fields.append("description_ru")
            if overwrite_text or not p.description_ky:
                p.description_ky = data.get("desc_ky", "") or p.description_ky
                changed_fields.append("description_ky")
            if overwrite_text or not p.description_en:
                p.description_en = data.get("desc_en", "") or p.description_en
                changed_fields.append("description_en")

            slug = data.get("photo")
            need_photo = slug and (overwrite_photos or not p.main_photo)

            label = f"{p.name_ru} (id={p.pk})"
            actions = []
            if changed_fields:
                actions.append("тексты")
            if need_photo:
                actions.append(f"фото->{slug}.jpg")
            if actions:
                print(f"  {'[DRY RUN] ' if dry_run else ''}{label}: {', '.join(actions)}")

            if dry_run:
                if changed_fields:
                    text_updated += 1
                if need_photo:
                    photos_updated += 1
                continue

            if changed_fields:
                p.save(update_fields=changed_fields)
                text_updated += 1

            if need_photo:
                raw = load_photo(slug)
                if raw is not None:
                    if p.main_photo:
                        p.main_photo.delete(save=False)
                    p.main_photo.save(f"{slug}.jpg", ContentFile(raw), save=True)
                    photos_updated += 1

    mapped_norm_keys = {_norm(n) for n in ITEMS}
    unmapped_in_db = sorted({
        p.name_ru for p in all_products if _norm(p.name_ru) not in mapped_norm_keys
    })

    verb = "Будет обновлено" if dry_run else "Обновлено"
    print(f"\n✅ {verb} (фото): {photos_updated}")
    print(f"✅ {verb} (тексты RU/KY/EN): {text_updated}")
    if not_found_in_db:
        print(f"\n⚠️  Названия из ITEMS, которых НЕТ в БД у этого центра ({len(not_found_in_db)}):")
        for n in not_found_in_db:
            print(f"     - {n}")
    if unmapped_in_db:
        print(f"\n⚠️  Товары в БД, для которых НЕТ данных в ITEMS ({len(unmapped_in_db)}):")
        for n in unmapped_in_db:
            print(f"     - {n}")


def main():
    ap = argparse.ArgumentParser(description="Обновить фото и переводы услуг Ош Принт")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--center-slug", default="Osh_print")
    ap.add_argument("--overwrite-photos", action="store_true")
    ap.add_argument("--overwrite-text", action="store_true")
    args = ap.parse_args()
    run(dry_run=args.dry_run, center_slug=args.center_slug,
        overwrite_photos=args.overwrite_photos, overwrite_text=args.overwrite_text)


if __name__ == "__main__":
    main()
