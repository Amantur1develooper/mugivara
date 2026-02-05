from decimal import Decimal
from catalog.models import BranchItem

SESSION_KEY = "cart"  # session["cart"] = { "<branch_id>": { "<branch_item_id>": qty } }

def get_cart(request, branch_id: int) -> dict:
    root = request.session.get(SESSION_KEY, {})
    return root.get(str(branch_id), {})

def _save(request, branch_id: int, branch_cart: dict):
    root = request.session.get(SESSION_KEY, {})
    root[str(branch_id)] = branch_cart
    request.session[SESSION_KEY] = root
    request.session.modified = True

def add_to_cart(request, branch_id: int, branch_item_id: int, qty: int = 1):
    qty = max(1, min(int(qty or 1), 99))
    cart = get_cart(request, branch_id)
    k = str(branch_item_id)
    cart[k] = int(cart.get(k, 0)) + qty
    _save(request, branch_id, cart)
    return cart

def set_qty(request, branch_id: int, branch_item_id: int, qty: int):
    cart = get_cart(request, branch_id)
    k = str(branch_item_id)
    qty = int(qty or 0)
    if qty <= 0:
        cart.pop(k, None)
    else:
        cart[k] = min(qty, 99)
    _save(request, branch_id, cart)
    return cart

def clear_cart(request, branch_id: int):
    root = request.session.get(SESSION_KEY, {})
    root.pop(str(branch_id), None)
    request.session[SESSION_KEY] = root
    request.session.modified = True

def cart_details(branch, cart: dict):
    """
    cart = {"12": 2, "15": 1}
    return rows=[{branch_item, qty, line_total}], subtotal, qty_total
    """
    ids = []
    for k in cart.keys():
        try:
            ids.append(int(k))
        except Exception:
            pass

    qs = BranchItem.objects.select_related("item").filter(branch=branch, id__in=ids)
    mp = {str(x.id): x for x in qs}

    rows = []
    subtotal = Decimal("0")
    qty_total = 0

    for k, qty in cart.items():
        bi = mp.get(str(k))
        if not bi:
            continue
        qty = int(qty or 0)
        if qty <= 0:
            continue
        line_total = bi.price * qty
        subtotal += line_total
        qty_total += qty
        rows.append({"branch_item": bi, "qty": qty, "line_total": line_total})

    rows.sort(key=lambda r: (r["branch_item"].sort_order, r["branch_item"].id))
    return rows, subtotal, qty_total



from decimal import Decimal
from catalog.models import BranchItem

def get_table_cart(request, token: str):
    data = request.session.get("table_cart", {})
    return data.get(token, {})

def set_table_cart(request, token: str, cart: dict):
    data = request.session.get("table_cart", {})
    data[token] = cart
    request.session["table_cart"] = data
    request.session.modified = True

def clear_table_cart(request, token: str):
    data = request.session.get("table_cart", {})
    data.pop(token, None)
    request.session["table_cart"] = data
    request.session.modified = True

def table_cart_totals(branch, cart: dict):
    """
    cart: { "branch_item_id": qty }
    """
    ids = [int(k) for k in cart.keys()]
    items = BranchItem.objects.filter(branch=branch, id__in=ids).select_related("item")
    items_map = {str(x.id): x for x in items}

    rows = []
    subtotal = Decimal("0")
    qty_total = 0

    for bi_id, qty in cart.items():
        bi = items_map.get(str(bi_id))
        if not bi:
            continue
        q = int(qty)
        if q <= 0:
            continue
        line_total = bi.price * q
        subtotal += line_total
        qty_total += q
        rows.append({"branch_item": bi, "qty": q, "line_total": line_total})

    return rows, subtotal, qty_total
