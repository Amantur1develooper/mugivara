# -*- coding: utf-8 -*-
"""Ценники товаров магазина — PDF на A4, который печатают и режут.

Размер ценника 90×50 мм задан заказчиком: такой влезает в стандартный
держатель на полке. На A4 их ложится 10 штук — два столбца по пять.
Поэтому геометрия считается в миллиметрах и ничего не «подгоняется под
страницу»: напечатанный ценник должен совпасть с держателем, иначе всю
пачку придётся резать заново.
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
TAG_W, TAG_H = 90 * mm, 50 * mm
COLS, ROWS = 2, 5
PAGE_W, PAGE_H = A4
MARGIN_X = (PAGE_W - COLS * TAG_W) / 2
MARGIN_Y = (PAGE_H - ROWS * TAG_H) / 2
PAD = 4 * mm

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


def _draw_tag(c, x, y, name, price_text, unit_text, note):
    """Один ценник. (x, y) — левый нижний угол."""
    c.setStrokeColor(CUT)
    c.setLineWidth(0.4)
    c.rect(x, y, TAG_W, TAG_H)

    inner = TAG_W - 2 * PAD

    # ── цена: занимает нижнюю треть, кегль под ширину ──
    price_size, _ = _fit(price_text, BOLD, inner * 0.78, 1, 46, 16)
    price_baseline = y + PAD + 1.5 * mm
    c.setFillColor(black)
    c.setFont(BOLD, price_size)
    c.drawString(x + PAD, price_baseline, price_text)

    price_w = pdfmetrics.stringWidth(price_text, BOLD, price_size)
    c.setFont(REGULAR, 11)
    c.setFillColor(MUTED)
    c.drawString(x + PAD + price_w + 2 * mm, price_baseline + 1 * mm, "сом")
    if unit_text:
        c.drawRightString(x + TAG_W - PAD, price_baseline + 1 * mm, unit_text)

    # ── название: всё, что осталось сверху ──
    top = y + TAG_H - PAD
    bottom = price_baseline + price_size * 0.85
    avail = top - bottom
    # короткое название набираем крупно: ценник читают с полки, издалека
    name_size, lines = _fit(name, BOLD, inner, 3, 28, 7)
    leading = name_size * 1.12
    while len(lines) * leading > avail and name_size > 7:
        name_size, lines = _fit(name, BOLD, inner, 3, name_size - 0.5, 7)
        leading = name_size * 1.12

    # блок названия центрируем по вертикали: иначе у товара с одним словом
    # между названием и ценой зияет пустая половина ценника
    block = len(lines) * leading
    ty = bottom + (avail - block) / 2 + block - name_size * 0.88
    c.setFillColor(black)
    c.setFont(BOLD, name_size)
    for line in lines:
        c.drawString(x + PAD, ty, line)
        ty -= leading

    if note:
        c.setFont(REGULAR, 7.5)
        c.setFillColor(MUTED)
        c.drawRightString(x + TAG_W - PAD, y + TAG_H - PAD - 1 * mm, note)


def build_pdf(fileobj, rows, title=""):
    """rows — список словарей: name, price, unit, note."""
    _ensure_fonts()
    c = canvas.Canvas(fileobj, pagesize=A4)
    c.setTitle(title or "Ценники")
    per_page = COLS * ROWS

    for i, row in enumerate(rows):
        slot = i % per_page
        if i and slot == 0:
            c.showPage()
        col = slot % COLS
        line = slot // COLS
        x = MARGIN_X + col * TAG_W
        # строки считаем сверху вниз, а координаты в PDF растут снизу вверх
        y = PAGE_H - MARGIN_Y - (line + 1) * TAG_H
        _draw_tag(c, x, y,
                  name=row["name"],
                  price_text=_fmt_price(row.get("price")),
                  unit_text=row.get("unit") or "",
                  note=row.get("note") or "")
    if not rows:
        _ensure_fonts()
        c.setFont(REGULAR, 12)
        c.drawString(MARGIN_X, PAGE_H / 2, "Нет товаров с ценой — ценники печатать не из чего")
    c.showPage()
    c.save()
    return fileobj
