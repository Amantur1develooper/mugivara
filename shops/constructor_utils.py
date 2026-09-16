"""
Общая логика «Собери сам» — используется и кассой (dashboard_views.shop_pos),
и публичной витриной (views._branch_catalog), чтобы не расходиться в двух местах.
"""
import json as _j
from decimal import Decimal

from .models import StoreConstructor


def fmt(value):
    """Decimal → int если целое, иначе float без лишних нулей."""
    try:
        d = Decimal(str(value))
        return int(d) if d == d.to_integral_value() else float(d.normalize())
    except Exception:
        return value


def constructors_data(store) -> dict:
    """Данные активных конструкторов «Собери сам» магазина: {id: {...}}.
    Помечает is_ready=False, если у обязательной группы (min>0) не хватает
    товаров — такой конструктор нельзя собрать и его не нужно показывать."""
    constructors = (
        StoreConstructor.objects
        .filter(store=store, is_active=True)
        .prefetch_related("groups__ingredients__product")
        .order_by("sort_order", "id")
    )
    data = {}
    for cx in constructors:
        groups = []
        for g in cx.groups.all().order_by("sort_order", "id"):
            ings = []
            for ing in g.ingredients.filter(is_active=True).order_by("sort_order", "id"):
                p = ing.product
                ings.append({
                    "id": ing.id,
                    "name": p.name_ru,
                    "price": fmt(ing.display_price),
                    "photo": p.photo.url if p.photo else "",
                    "product_id": p.id,
                    "write_off_qty": fmt(ing.write_off_qty),
                })
            groups.append({
                "id": g.id, "name": g.name,
                "min": g.min_select, "max": g.max_select,
                "ingredients": ings,
            })
        is_ready = all(g["min"] <= 0 or len(g["ingredients"]) >= g["min"] for g in groups)
        data[cx.id] = {
            "id": cx.id, "name": cx.name,
            "base_price": fmt(cx.base_price),
            "photo": cx.photo.url if cx.photo else "",
            "groups": groups,
            "ready": is_ready,
        }
    return data


def constructors_json(store) -> str:
    return _j.dumps(constructors_data(store), ensure_ascii=False)


def has_ready_constructors(store) -> bool:
    return any(cx["ready"] for cx in constructors_data(store).values())


def validate_cx_selections(cx: dict, selections: dict):
    """Возвращает текст ошибки, если выбор нарушает мин/макс группы, иначе None."""
    for g in cx["groups"]:
        sel_map = selections.get(str(g["id"])) or {}
        total = sum(int(v or 0) for v in sel_map.values())
        if g["min"] > 0 and total < g["min"]:
            return f"Выберите минимум {g['min']} в «{g['name']}»"
        if g["max"] > 0 and total > g["max"]:
            return f"Максимум {g['max']} в «{g['name']}»"
    return None


def resolve_cx_item(data: dict, item: dict):
    """Считает цену/состав/списание для корзинной позиции «Собери сам» на основе
    АКТУАЛЬНЫХ данных конструктора (client присылает только id + выбор, цену не
    доверяем клиенту). item: {"item_id","cx_id","qty","selections"}.
    Возвращает None, если конструктор удалён/выключен/не готов к продаже."""
    cx = data.get(item["cx_id"], data.get(str(item["cx_id"])))
    if not cx or not cx["ready"]:
        return None

    qty = max(1, int(item.get("qty", 1)))
    selections = item.get("selections") or {}

    unit_price = Decimal(str(cx["base_price"]))
    snapshot = []
    summary_parts = []
    wh_deductions: dict = {}  # product_id -> Decimal, за ОДНУ единицу конструктора

    for g in cx["groups"]:
        sel_map = selections.get(str(g["id"])) or {}
        ings_snap = []
        names = []
        for ing in g["ingredients"]:
            try:
                sel_qty = int(sel_map.get(str(ing["id"]), 0) or 0)
            except (TypeError, ValueError):
                sel_qty = 0
            if sel_qty <= 0:
                continue
            price = Decimal(str(ing["price"]))
            unit_price += price * sel_qty
            ings_snap.append({
                "id": ing["id"], "name": ing["name"], "price": ing["price"],
                "qty": sel_qty, "product_id": ing["product_id"],
                "write_off_qty": ing["write_off_qty"],
            })
            names.append(f"{ing['name']} ×{sel_qty}" if sel_qty > 1 else ing["name"])
            wh_deductions[ing["product_id"]] = wh_deductions.get(ing["product_id"], Decimal("0")) \
                + Decimal(str(ing["write_off_qty"])) * sel_qty
        if ings_snap:
            snapshot.append({"gid": g["id"], "gname": g["name"], "ings": ings_snap})
        if names:
            summary_parts.append(", ".join(names))

    return {
        "item_id": item.get("item_id"),
        "cx_id": cx["id"],
        "cx_name": cx["name"],
        "photo": cx.get("photo", ""),
        "qty": qty,
        "unit_price": unit_price,
        "line_total": unit_price * qty,
        "summary": " · ".join(summary_parts),
        "snapshot": snapshot,
        "wh_deductions": wh_deductions,
    }
