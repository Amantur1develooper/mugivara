from decimal import Decimal
from catalog.models import BranchItem

def _cart_key(branch_id: int) -> str:
    return f"sanzhi_cart_{branch_id}"

def get_cart(request, branch_id: int) -> dict:
    return request.session.get(_cart_key(branch_id), {})

def save_cart(request, branch_id: int, cart: dict):
    request.session[_cart_key(branch_id)] = cart
    request.session.modified = True

def add_to_cart(request, branch_id: int, branch_item_id: int, qty: int = 1):
    cart = get_cart(request, branch_id)
    key = str(branch_item_id)
    cart[key] = cart.get(key, 0) + qty
    if cart[key] <= 0:
        cart.pop(key, None)
    save_cart(request, branch_id, cart)

def set_qty(request, branch_id: int, branch_item_id: int, qty: int):
    cart = get_cart(request, branch_id)
    key = str(branch_item_id)
    if qty <= 0:
        cart.pop(key, None)
    else:
        cart[key] = qty
    save_cart(request, branch_id, cart)

def clear_cart(request, branch_id: int):
    request.session.pop(_cart_key(branch_id), None)
    request.session.modified = True

def cart_details(branch, cart: dict):
    """
    Возвращает список позиций, total, qty_total
    """
    ids = [int(k) for k in cart.keys()]
    items = (BranchItem.objects
             .select_related("item")
             .filter(branch=branch, id__in=ids, is_available=True))

    items_map = {bi.id: bi for bi in items}

    rows = []
    total = Decimal("0")
    qty_total = 0

    for k, qty in cart.items():
        bid = int(k)
        bi = items_map.get(bid)
        if not bi:
            continue
        qty = int(qty)
        line = bi.price * qty
        total += line
        qty_total += qty
        rows.append({
            "branch_item": bi,
            "qty": qty,
            "line_total": line,
        })

    rows.sort(key=lambda x: x["branch_item"].sort_order)
    return rows, total, qty_total
