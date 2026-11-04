#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Рисует карточкам товаров плитку-заставку: название, иконка и цвет категории.

Зачем так, а не фото из интернета. Настоящих снимков этих товаров под
свободной лицензией нет, а ставить на 59 позиций «Гигиены» одну и ту же
картинку чужого куска мыла — значит показывать покупателю не тот товар,
который он заказывает. Плитка с названием честнее: она ничего не изображает,
но каталог перестаёт выглядеть пустым, и товар читается прямо с карточки.

Заставки ставятся только тем, у кого фото ещё нет, и помечаются именем файла
tile-<id>.webp — поэтому их легко снять одной командой, когда появятся
настоящие снимки:

    python make_product_tiles.py --store 1 --clear

    python make_product_tiles.py --store 1 --dry-run
    python make_product_tiles.py --store 1
"""
import argparse
import os
import sys
from io import BytesIO

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.core.files.base import ContentFile      # noqa: E402
from PIL import Image, ImageDraw, ImageFont         # noqa: E402

from shops.models import StoreProduct               # noqa: E402

W, H = 800, 600
PREFIX = "tile-"

# цвет и значок на категорию: витрина становится читаемой с одного взгляда
STYLES = {
    "Стирка":          ("#E8F0FE", "#1A56DB", "🧺"),
    "Уборка дома":     ("#E6F6EC", "#0E7C3A", "🧽"),
    "Посуда":          ("#FFF4E5", "#B45309", "🍽"),
    "Волосы":          ("#F3E8FF", "#7E22CE", "💇"),
    "Уход за кожей":   ("#FFE9F0", "#BE185D", "🧴"),
    "Гигиена":         ("#E0F2FE", "#0369A1", "🧼"),
    "Здоровье и БАД":  ("#FEE2E2", "#B91C1C", "💊"),
    "Чай и питание":   ("#FEF3C7", "#92400E", "🍵"),
    "Парфюмерия":      ("#EDE9FE", "#5B21B6", "💐"),
}
DEFAULT_STYLE = ("#F1F3F5", "#495057", "🛍")

FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
EMOJI_PATHS = ["/System/Library/Fonts/Apple Color Emoji.ttc"]


def _font(size):
    for p in FONT_PATHS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    return ImageFont.load_default()


def _emoji_font(size):
    for p in EMOJI_PATHS:
        if os.path.exists(p):
            try:
                # Apple Color Emoji поддерживает только фиксированные кегли
                return ImageFont.truetype(p, 137)
            except OSError:
                pass
    return None


def wrap(draw, text, font, max_w, max_lines=4):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and draw.textlength(lines[-1], font=font) > max_w - 20:
        lines[-1] = lines[-1][:28].rstrip() + "…"
    return lines


def make_tile(name, category):
    """Чисто типографская плитка.

    Эмодзи-иконки пробовал — на Linux-сервере цветного шрифта нет, и вместо
    значка остаётся пустой кружок. Поэтому героем сделано само название:
    оно читается с карточки и одинаково выглядит везде.
    """
    bg, fg, _ = STYLES.get(category, DEFAULT_STYLE)
    img = Image.new("RGB", (W, H), bg)
    dr = ImageDraw.Draw(img)

    # мягкая диагональная штриховка — плитка не выглядит пустым полем
    for x in range(-H, W, 34):
        dr.line([(x, H), (x + H, 0)], fill=_mix(bg, fg, 0.05), width=12)

    # Категорию на плитке не пишем: в карточке она и так стоит чипом,
    # получалось одно и то же слово дважды. Цвет плитки её и так называет.
    dr.rectangle([(0, 0), (W, 10)], fill=_mix(bg, fg, 0.45))

    # название товара по центру, кегль подбираем под длину
    size = 48 if len(name) < 34 else (40 if len(name) < 60 else 34)
    f = _font(size)
    lines = wrap(dr, name, f, W - 130, max_lines=4)
    step = size + 12
    # textbbox учитывает реальную высоту строки — без него блок
    # визуально уезжал вверх
    y = (H - len(lines) * step) / 2 - size * 0.18
    for ln in lines:
        dr.text(((W - dr.textlength(ln, font=f)) / 2, y), ln, font=f, fill=fg)
        y += step

    return img


def _mix(hex_bg, hex_fg, k):
    a = tuple(int(hex_bg[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(hex_fg[i:i + 2], 16) for i in (1, 3, 5))
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def main():
    ap = argparse.ArgumentParser()
    # id магазина или часть названия: номера на сервере и локально разные,
    # и легко отрисовать заставки не тому магазину
    ap.add_argument("--store", required=True, help="id магазина или часть названия")
    ap.add_argument("--clear", action="store_true", help="снять ранее созданные заставки")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from shops.models import Store
    if str(args.store).isdigit():
        store = Store.objects.filter(id=int(args.store)).first()
    else:
        store = Store.objects.filter(name_ru__icontains=args.store).first()
    if not store:
        sys.exit(f"Магазин «{args.store}» не найден. Список: "
                 + ", ".join(f"{s.id}={s.name_ru}" for s in Store.objects.all()))
    print(f"Магазин: #{store.id} {store.name_ru}")
    qs = StoreProduct.objects.filter(store=store).select_related("category")

    if args.clear:
        n = 0
        for p in qs.exclude(photo=""):
            if PREFIX in os.path.basename(p.photo.name):
                if not args.dry_run:
                    p.photo.delete(save=True)
                n += 1
        print(f"{'нашлось' if args.dry_run else 'снято'} заставок: {n}")
        return

    todo = [p for p in qs if not p.photo]
    print(f"Товаров без фото: {len(todo)} из {qs.count()}")
    if args.dry_run:
        from collections import Counter
        for cat, n in Counter(
                (p.category.name_ru if p.category else "—") for p in todo).most_common():
            print(f"   {cat:<18} {n}")
        print("\n--dry-run: ничего не создано.")
        return

    done = 0
    for p in todo:
        cat = p.category.name_ru if p.category else ""
        img = make_tile(p.name_ru, cat)
        buf = BytesIO()
        img.save(buf, "WEBP", quality=80, method=6)
        p.photo.save(f"{PREFIX}{p.id}.webp", ContentFile(buf.getvalue()), save=True)
        done += 1
        if done % 50 == 0:
            print(f"   готово {done}…")
    print(f"\nЗаставок создано: {done}")


if __name__ == "__main__":
    main()
