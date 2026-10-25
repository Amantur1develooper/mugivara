#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Разовое пережатие уже загруженных фото блюд и категорий до 700 px / WebP q78.

Зачем: карточка блюда нигде не шире 320 px, то есть 700 px — это уже двойной
размер для retina. Раньше фото клались как 900 px / q82 — лишние ~40% веса,
которых пользователь не видит, но которые он скачивает.

Скрипт идемпотентный: то, что уже ≤700 px, пропускается. Оригиналы
перезаписываются, поэтому сначала запустите с --dry-run и сделайте бэкап media.

    python recompress_photos.py --dry-run
    python recompress_photos.py --restaurant semeyniy
    python recompress_photos.py                      # все заведения
"""
import argparse
import os
import sys
from io import BytesIO

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from PIL import Image                                   # noqa: E402
from catalog.models import Item, Category               # noqa: E402

Image.MAX_IMAGE_PIXELS = None
MAXSIDE, QUALITY = 700, 78


def shrink(path, dry):
    """Возвращает (было, стало) в байтах; (0, 0) — если трогать не нужно."""
    try:
        before = os.path.getsize(path)
    except OSError:
        return 0, 0
    try:
        img = Image.open(path)
    except Exception:
        return 0, 0
    if img.format == "WEBP" and max(img.size) <= MAXSIDE:
        return 0, 0                                     # уже лёгкое

    has_alpha = img.mode in ("RGBA", "LA") or (
        img.mode == "P" and "transparency" in img.info
    )
    img = img.convert("RGBA" if has_alpha else "RGB")
    img.thumbnail((MAXSIDE, MAXSIDE), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="WEBP", quality=QUALITY, method=6)
    after = buf.tell()
    if after >= before:
        return 0, 0                                     # пережимать нет смысла
    if not dry:
        with open(path, "wb") as fh:
            fh.write(buf.getvalue())
    return before, after


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--restaurant", default="", help="slug заведения; по умолчанию — все")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    qs_items = Item.objects.exclude(photo="").exclude(photo=None)
    qs_cats = Category.objects.exclude(photo="").exclude(photo=None)
    if args.restaurant:
        qs_items = qs_items.filter(restaurant__slug=args.restaurant)
        qs_cats = qs_cats.filter(menu_set__restaurant__slug=args.restaurant)

    total_before = total_after = 0
    touched = skipped = 0
    for qs, label in ((qs_items, "блюда"), (qs_cats, "категории")):
        for obj in qs.iterator(chunk_size=200):
            try:
                path = obj.photo.path
            except Exception:
                continue
            if not os.path.exists(path):
                continue
            b, a = shrink(path, args.dry_run)
            if b:
                total_before += b
                total_after += a
                touched += 1
                if touched % 250 == 0:
                    print("  обработано %d, пока сэкономлено %.0f МБ" % (
                        touched, (total_before - total_after) / 1024 / 1024))
            else:
                skipped += 1

    saved = total_before - total_after
    print()
    print("пережато: %d | пропущено (уже лёгкие): %d" % (touched, skipped))
    if touched:
        print("было %.0f МБ → стало %.0f МБ, экономия %.0f МБ (%.0f%%)" % (
            total_before / 1024 / 1024, total_after / 1024 / 1024,
            saved / 1024 / 1024, 100 * saved / total_before))
    if args.dry_run:
        print("\n--dry-run: файлы не тронуты.")


if __name__ == "__main__":
    main()
