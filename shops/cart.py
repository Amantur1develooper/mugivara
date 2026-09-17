# shops/cart.py
import uuid
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List

from .models import StoreStock
from .pricing import PromoResolver


def dec(x) -> Decimal:
    try:
        return Decimal(str(x))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _cart_key(branch_id: int) -> str:
    return f"shops_cart_{branch_id}"


def _mode_key(branch_id: int) -> str:
    return f"shops_mode_{branch_id}"


# ---------- MODE: delivery / in_store ----------
def set_mode(request, branch_id: int, mode: str) -> None:
    mode = (mode or "").strip()
    if mode not in ("delivery", "in_store"):
        mode = "delivery"
    request.session[_mode_key(branch_id)] = mode
    request.session.modified = True


def get_mode(request, branch_id: int, default: str = "delivery") -> str:
    mode = request.session.get(_mode_key(branch_id), default)
    if mode not in ("delivery", "in_store"):
        mode = default
    return mode


# ---------- CART (session): {product_id: qty} ----------
def get_cart(request, branch_id: int) -> Dict[str, str]:
    data = request.session.get(_cart_key(branch_id), {})
    if not isinstance(data, dict):
        data = {}
    cleaned: Dict[str, str] = {}
    for k, v in data.items():
        try:
            kk = str(int(k))
            vv = str(int(dec(v)))
            if int(vv) > 0:
                cleaned[kk] = vv
        except Exception:
            continue
    return cleaned


def save_cart(request, branch_id: int, cart: Dict[str, str]) -> None:
    request.session[_cart_key(branch_id)] = cart
    request.session.modified = True


def clear_shop_cart(request, branch) -> None:
    request.session.pop(_cart_key(branch.id), None)
    clear_cx_cart(request, branch.id)
    request.session.modified = True


# ---------- CX CART (session): «Собери сам» в публичной витрине ----------
# Храним только «сырые» данные выбора клиента (id конструктора + что выбрал) —
# цену и состав всегда пересчитываем на сервере из актуальных данных
# конструктора (constructor_utils.resolve_cx_item), клиенту не доверяем.

def _cx_cart_key(branch_id: int) -> str:
    return f"shops_cxcart_{branch_id}"


def get_cx_cart(request, branch_id: int) -> List[Dict[str, Any]]:
    data = request.session.get(_cx_cart_key(branch_id), [])
    if not isinstance(data, list):
        return []
    cleaned: List[Dict[str, Any]] = []
    for it in data:
        if not isinstance(it, dict):
            continue
        try:
            cleaned.append({
                "item_id": str(it.get("item_id") or uuid.uuid4().hex[:10]),
                "cx_id": int(it["cx_id"]),
                "qty": max(1, int(it.get("qty", 1))),
                "selections": it.get("selections") or {},
            })
        except Exception:
            continue
    return cleaned


def save_cx_cart(request, branch_id: int, items: List[Dict[str, Any]]) -> None:
    request.session[_cx_cart_key(branch_id)] = items
    request.session.modified = True


def clear_cx_cart(request, branch_id: int) -> None:
    request.session.pop(_cx_cart_key(branch_id), None)
    request.session.modified = True


def get_shop_cart(request, branch) -> Dict[str, Any]:
    """
    Готовая корзина для checkout/шаблонов:
    rows: [{product_id, product, stock, qty, price, line_total}]
    subtotal, qty_total
    """
    cart = get_cart(request, branch.id)
    if not cart:
        return {"rows": [], "qty_total": 0, "subtotal": Decimal("0")}

    product_ids = [int(pid) for pid in cart.keys()]

    stocks = (
        StoreStock.objects
        .filter(branch=branch, product_id__in=product_ids, product__is_active=True)
        .select_related("product", "product__category")
    )
    stock_map = {s.product_id: s for s in stocks}

    promo = PromoResolver(branch.store)

    rows: List[Dict[str, Any]] = []
    subtotal = Decimal("0")
    qty_total = 0

    for pid_str, qty_str in cart.items():
        pid = int(pid_str)
        stock = stock_map.get(pid)
        if not stock:
            continue

        qty = int(dec(qty_str))
        if qty <= 0:
            continue

        price, discount_percent = promo.price_for(stock.product)
        orig_price = dec(stock.product.price)
        line_total = price * qty

        rows.append({
            "product_id": pid,
            "product": stock.product,
            "stock": stock,
            "qty": qty,
            "price": price,
            "orig_price": orig_price,
            "discount_percent": discount_percent,
            "line_total": line_total,
        })
        subtotal += line_total
        qty_total += qty

    return {"rows": rows, "qty_total": qty_total, "subtotal": subtotal}
