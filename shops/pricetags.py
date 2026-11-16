# -*- coding: utf-8 -*-
"""Ценники товаров магазина — PDF на A4, который печатают и режут.

Две раскладки: 65×40 мм по три в ряд (21 на листе) — ходовая, и прежняя
90×50 мм по две (10 на листе) — под держатели, купленные раньше.
Геометрия считается в миллиметрах и ничего не «подгоняется под страницу»:
напечатанный ценник должен совпасть с держателем, иначе всю пачку
придётся резать заново.
"""
from decimal import Decimal
from pathlib import Path

from reportlab.lib.colors import Color, black
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONTS = Path(__file__).resolve().parent / "fonts"
REGULAR, BOLD = "DejaVuCond", "DejaVuCond-Bold"

# ── геометрия, всё в миллиметрах ────────────────────────────────────────────
PAGE_W, PAGE_H = A4


class Layout:
    """Раскладка ценников на листе: размер ценника и сетка под него.

    Размер держат в миллиметрах и не подгоняют под страницу: напечатанный
    ценник должен совпасть с держателем на полке, иначе всю пачку придётся
    резать заново.
    """

    def __init__(self, key, title, tag_w_mm, tag_h_mm, cols, rows, pad_mm, price_hi, name_hi):
        self.key = key
        self.title = title
        self.w = tag_w_mm * mm
        self.h = tag_h_mm * mm
        self.cols = cols
        self.rows = rows
        self.pad = pad_mm * mm
        self.price_hi = price_hi      # самый крупный кегль цены
        self.name_hi = name_hi        # самый крупный кегль названия
        self.margin_x = (PAGE_W - cols * self.w) / 2
        self.margin_y = (PAGE_H - rows * self.h) / 2

    @property
    def per_page(self):
        return self.cols * self.rows


LAYOUTS = {
    # три в ряд — ходовой размер, 21 ценник на лист
    "small": Layout("small", "65×40 мм, 3 в ряд", 65, 40, 3, 7, 3, 34, 20),
    # прежний крупный: под держатели 90×50, 10 на лист
    "big":   Layout("big",   "90×50 мм, 2 в ряд", 90, 50, 2, 5, 4, 46, 28),
}
DEFAULT_LAYOUT = "small"

CUT = Color(0.72, 0.74, 0.77)       # линия реза — серая, чтобы не лезла в глаза
MUTED = Color(0.42, 0.45, 0.5)

_fonts_ready = False


def _ensure_fonts():
    global _fonts_ready
    if _fonts_ready:
        return
    pdfmetrics.registerFont(TTFont(REGULAR, str(FONTS / "DejaVuSansCondensed.ttf")))
    pdfmetrics.registerFont(TTFont(BOLD, str(FONTS / "DejaVuSansCondensed-Bold.ttf")))
    _fonts_ready = True


def _fmt_price(value):
    """1250 → «1 250». Копейки на ценнике не нужны, а неразрывный пробел
    не даёт разряду уехать на другую строку."""
    try:
        n = Decimal(value or 0).quantize(Decimal("1"))
    except Exception:
        return "—"
    return f"{int(n):,}".replace(",", " ")


def _wrap(text, font, size, max_width, max_lines):
    """Разбивает строку по словам под ширину. Возвращает None, если не влезло:
    вызывающий уменьшает кегль и пробует снова."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        probe = f"{cur} {w}".strip()
        if pdfmetrics.stringWidth(probe, font, size) <= max_width:
            cur = probe
            continue
        if cur:
            lines.append(cur)
        # слово само по себе длиннее строки — на этом кегле не разложить
        if pdfmetrics.stringWidth(w, font, size) > max_width:
            return None
        cur = w
        if len(lines) > max_lines:
            return None
    if cur:
        lines.append(cur)
    return lines if 0 < len(lines) <= max_lines else None


def _fit(text, font, max_width, max_lines, hi, lo):
    """Подбирает самый крупный кегль, при котором текст влезает."""
    size = hi
    while size >= lo:
        lines = _wrap(text, font, size, max_width, max_lines)
        if lines:
            return size, lines
        size -= 0.5
    # совсем не поместилось — режем по символам, чтобы ценник не остался пустым
    out, cur = [], ""
    for ch in text:
        if pdfmetrics.stringWidth(cur + ch, font, lo) > max_width:
            out.append(cur)
            cur = ch
            if len(out) == max_lines:
                break
        else:
            cur += ch
    if cur and len(out) < max_lines:
        out.append(cur)
    return lo, out or [text[:12]]


def _draw_tag(c, lay, x, y, name, price_text, unit_text, note):
    """Один ценник. (x, y) — левый нижний угол.

    Всё по центру: ценник читают с полки, под углом и мельком, и
    выключка по центру держит взгляд на одной оси — цена оказывается
    ровно под названием, а не уезжает в угол.
    """
    c.setStrokeColor(CUT)
    c.setLineWidth(0.4)
    c.rect(x, y, lay.w, lay.h)

    inner = lay.w - 2 * lay.pad
    mid = x + lay.w / 2

    # ── единица измерения: самая нижняя строка ──
    unit_h = 0
    if unit_text:
        unit_size = 8.5 if lay.key == "big" else 7.5
        unit_h = unit_size + 0.5
        c.setFont(REGULAR, unit_size)
        c.setFillColor(MUTED)
        c.drawCentredString(mid, y + lay.pad, unit_text)

    # ── цена с «сом»: подбираем кегль так, чтобы вся связка влезла ──
    price_size = lay.price_hi
    while price_size > 14:
        w = (pdfmetrics.stringWidth(price_text, BOLD, price_size)
             + 2 * mm + pdfmetrics.stringWidth("сом", REGULAR, price_size * 0.3))
        if w <= inner:
            break
        price_size -= 0.5

    cur_size = max(8, price_size * 0.3)
    price_w = pdfmetrics.stringWidth(price_text, BOLD, price_size)
    cur_w = pdfmetrics.stringWidth("сом", REGULAR, cur_size)
    group_w = price_w + 2 * mm + cur_w
    price_baseline = y + lay.pad + unit_h + 1.2 * mm
    left = mid - group_w / 2

    c.setFillColor(black)
    c.setFont(BOLD, price_size)
    c.drawString(left, price_baseline, price_text)
    c.setFont(REGULAR, cur_size)
    c.setFillColor(MUTED)
    c.drawString(left + price_w + 2 * mm, price_baseline + 1 * mm, "сом")

    # ── название: занимает всё, что осталось сверху ──
    top = y + lay.h - lay.pad
    bottom = price_baseline + price_size * 0.85
    avail = top - bottom
    # короткое название набираем крупно: ценник читают с полки, издалека
    name_size, lines = _fit(name, BOLD, inner, 3, lay.name_hi, 6)
    leading = name_size * 1.12
    while len(lines) * leading > avail and name_size > 6:
        name_size, lines = _fit(name, BOLD, inner, 3, name_size - 0.5, 6)
        leading = name_size * 1.12

    # блок названия центрируем и по вертикали: у товара из одного слова
    # иначе зияла пустая половина ценника
    block = len(lines) * leading
    ty = bottom + (avail - block) / 2 + block - name_size * 0.88
    c.setFillColor(black)
    c.setFont(BOLD, name_size)
    for line in lines:
        c.drawCentredString(mid, ty, line)
        ty -= leading

    if note:
        c.setFont(REGULAR, 7 if lay.key == "big" else 6)
        c.setFillColor(MUTED)
        c.drawRightString(x + lay.w - lay.pad, y + lay.h - lay.pad - 1 * mm, note)


def build_pdf(fileobj, rows, title="", layout=DEFAULT_LAYOUT):
    """rows — список словарей: name, price, unit, note."""
    _ensure_fonts()
    lay = LAYOUTS.get(layout) or LAYOUTS[DEFAULT_LAYOUT]
    c = canvas.Canvas(fileobj, pagesize=A4)
    c.setTitle(title or "Ценники")

    for i, row in enumerate(rows):
        slot = i % lay.per_page
        if i and slot == 0:
            c.showPage()
        col = slot % lay.cols
        line = slot // lay.cols
        x = lay.margin_x + col * lay.w
        # строки считаем сверху вниз, а координаты в PDF растут снизу вверх
        y = PAGE_H - lay.margin_y - (line + 1) * lay.h
        _draw_tag(c, lay, x, y,
                  name=row["name"],
                  price_text=_fmt_price(row.get("price")),
                  unit_text=row.get("unit") or "",
                  note=row.get("note") or "")
    if not rows:
        c.setFont(REGULAR, 12)
        c.drawString(lay.margin_x, PAGE_H / 2, "Нет товаров с ценой — ценники печатать не из чего")
    c.showPage()
    c.save()
    return fileobj
