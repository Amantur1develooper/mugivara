# -*- coding: utf-8 -*-
"""Разворачивает фотографии товаров магазина на 90°.

Нужна для снимков, загруженных до починки EXIF: тег ориентации при
пересохранении в WebP терялся, и кадры с телефона легли набок. Поворачивать
их по одному через кабинет — долго, если товаров несколько десятков.

    # посмотреть, что будет сделано
    python manage.py rotate_shop_photos --branch 47 --dir right --dry-run

    # повернуть только «лежачие» кадры (ширина больше высоты)
    python manage.py rotate_shop_photos --branch 47 --dir right --only-landscape

Запускать от того же пользователя, под которым работает сайт, иначе файлы
сменят владельца и веб-процесс потеряет право их перезаписывать:

    sudo -u deploy .venv/bin/python manage.py rotate_shop_photos ...
"""
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from PIL import Image, ImageOps

from shops.models import StoreBranch, StoreProduct, StoreStock

TURNS = {
    # по часовой стрелке («вправо») и против («влево»)
    "right": Image.Transpose.ROTATE_270,
    "left":  Image.Transpose.ROTATE_90,
    "180":   Image.Transpose.ROTATE_180,
}


class Command(BaseCommand):
    help = "Поворачивает фотографии товаров магазина на 90°"

    def add_arguments(self, parser):
        who = parser.add_mutually_exclusive_group(required=True)
        who.add_argument("--branch", type=int, help="id филиала — берём товары из его остатков")
        who.add_argument("--store", type=int, help="id магазина — все товары сети")
        parser.add_argument("--dir", choices=sorted(TURNS), default="right",
                            help="right — по часовой (по умолчанию), left — против, 180 — вверх ногами")
        parser.add_argument("--only-landscape", action="store_true",
                            help="трогать только кадры, у которых ширина больше высоты")
        parser.add_argument("--limit", type=int, default=0, help="обработать не больше N фото")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **o):
        if o["branch"]:
            try:
                branch = StoreBranch.objects.select_related("store").get(id=o["branch"])
            except StoreBranch.DoesNotExist:
                raise CommandError(f"Филиал #{o['branch']} не найден")
            ids = StoreStock.objects.filter(branch=branch).values_list("product_id", flat=True)
            products = StoreProduct.objects.filter(id__in=ids)
            where = f"филиал #{branch.id} «{branch.name_ru}» ({branch.store.name_ru})"
        else:
            products = StoreProduct.objects.filter(store_id=o["store"])
            if not products.exists():
                raise CommandError(f"У магазина #{o['store']} нет товаров")
            where = f"магазин #{o['store']}"

        turn = TURNS[o["dir"]]
        self.stdout.write(f"{where}: товаров {products.count()}, поворот «{o['dir']}»")
        if o["only_landscape"]:
            self.stdout.write("Трогаем только кадры шире, чем выше.")
        self.stdout.write("")

        done = skipped_no_photo = skipped_portrait = failed = 0
        for p in products.order_by("id"):
            if not p.photo:
                skipped_no_photo += 1
                continue
            if o["limit"] and done >= o["limit"]:
                break
            try:
                with p.photo.open("rb") as fh:
                    img = Image.open(fh)
                    img = (ImageOps.exif_transpose(img) or img).convert("RGB")
                    w, h = img.size
                    if o["only_landscape"] and w <= h:
                        skipped_portrait += 1
                        continue
                    if o["dry_run"]:
                        done += 1
                        self.stdout.write(f"  [dry-run] {p.name_ru[:46]:<48} {w}×{h}")
                        continue
                    out = img.transpose(turn)
                    buf = BytesIO()
                    out.save(buf, format="WEBP", quality=85, method=6)
                buf.seek(0)
                name = p.photo.name
                storage = p.photo.storage
                if storage.exists(name):
                    storage.delete(name)
                storage.save(name, ContentFile(buf.read()))
                done += 1
                self.stdout.write(f"  ✓ {p.name_ru[:46]:<48} {w}×{h} → {out.size[0]}×{out.size[1]}")
            except Exception as e:
                failed += 1
                self.stderr.write(f"  ✗ {p.name_ru[:46]}: {e}")

        self.stdout.write("")
        self.stdout.write(f"Повёрнуто:        {done}")
        self.stdout.write(f"Без фото:         {skipped_no_photo}")
        if o["only_landscape"]:
            self.stdout.write(f"Уже вертикальных: {skipped_portrait}")
        if failed:
            self.stdout.write(self.style.WARNING(f"Не удалось:       {failed}"))
        if o["dry_run"]:
            self.stdout.write(self.style.WARNING("--dry-run: ничего не сохранено."))
        else:
            self.stdout.write("Браузер может показывать старые картинки из кэша — "
                              "обновите страницу с Ctrl+F5 (на телефоне — ещё раз зайдите).")
