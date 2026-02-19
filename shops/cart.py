# shops/cart.py
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List

from .models import StoreStock


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

        price = dec(stock.product.price)
        line_total = price * qty

        rows.append({
            "product_id": pid,
            "product": stock.product,
            "stock": stock,
            "qty": qty,
            "price": price,
            "line_total": line_total,
        })
        subtotal += line_total
        qty_total += qty

    return {"rows": rows, "qty_total": qty_total, "subtotal": subtotal}
