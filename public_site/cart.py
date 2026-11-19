from decimal import Decimal

from catalog.models import BranchItem, BranchItemSize

# session["cart"] = { "<branch_id>": { "<ключ>": qty } }
# Ключ — либо id блюда филиала, либо «id:размер», когда у блюда есть размеры:
# 30 см и 40 см пиццы лежат в корзине отдельными строками со своими ценами.
SESSION_KEY = "cart"


def make_key(branch_item_id, size_id=None):
    return f"{branch_item_id}:{size_id}" if size_id else str(branch_item_id)


def split_key(key):
    """«12:5» → (12, 5); «12» → (12, None)."""
    raw = str(key)
    if ":" in raw:
        left, right = raw.split(":", 1)
        try:
            return int(left), int(right)
        except ValueError:
            return None, None
    try:
        return int(raw), None
    except ValueError:
        return None, None

def get_cart(request, branch_id: int) -> dict:
    root = request.session.get(SESSION_KEY, {})
    return root.get(str(branch_id), {})

def _save(request, branch_id: int, branch_cart: dict):
    root = request.session.get(SESSION_KEY, {})
    root[str(branch_id)] = branch_cart
    request.session[SESSION_KEY] = root
    request.session.modified = True

def add_to_cart(request, branch_id: int, branch_item_id: int, qty: int = 1,
                size_id=None):
    qty = max(1, min(int(qty or 1), 99))
    cart = get_cart(request, branch_id)
    k = make_key(branch_item_id, size_id)
    cart[k] = int(cart.get(k, 0)) + qty
    _save(request, branch_id, cart)
    return cart

def set_qty(request, branch_id: int, branch_item_id: int, qty: int, size_id=None):
    cart = get_cart(request, branch_id)
    k = make_key(branch_item_id, size_id)
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

def _resolve(branch, cart, delivery_only):
    """Разбирает ключи корзины в строки с ценой за выбранный размер."""
    ids, size_ids = set(), set()
    for k in cart.keys():
        bi_id, size_id = split_key(k)
        if bi_id:
            ids.add(bi_id)
        if size_id:
            size_ids.add(size_id)

    qs = (BranchItem.objects.select_related("item")
          .prefetch_related("sizes").filter(branch=branch, id__in=ids))
    if delivery_only:
        # Онлайн-корзина: блюда «только в зале» сюда не попадают
        qs = qs.filter(delivery_available=True)
    items = {x.id: x for x in qs}
    sizes = {z.id: z for z in BranchItemSize.objects.filter(
        id__in=size_ids, branch_item__branch=branch)}

    rows = []
    subtotal = Decimal("0")
    qty_total = 0
    for k, qty in cart.items():
        bi_id, size_id = split_key(k)
        bi = items.get(bi_id)
        if not bi:
            continue
        qty = int(qty or 0)
        if qty <= 0:
            continue
        size = sizes.get(size_id) if size_id else None
        # Размер могли удалить, пока корзина лежала в сессии — берём размер
        # по умолчанию, чтобы заказ не потерялся из-за правки меню.
        if size_id and (not size or size.branch_item_id != bi.id):
            size = bi.default_size()
        if not size and bi.has_sizes:
            size = bi.default_size()
        price = size.price if size else bi.price
        line_total = price * qty
        subtotal += line_total
        qty_total += qty
        rows.append({"branch_item": bi, "qty": qty, "line_total": line_total,
                     "size": size, "unit_price": price, "key": k})

    rows.sort(key=lambda r: (r["branch_item"].sort_order, r["branch_item"].id,
                             r["size"].sort_order if r["size"] else 0))
    return rows, subtotal, qty_total


def cart_details(branch, cart: dict):
    """
    cart = {"12": 2, "15:3": 1}
    return rows=[{branch_item, qty, line_total, size, unit_price, key}],
           subtotal, qty_total
    """
    return _resolve(branch, cart, delivery_only=True)



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
    """То же, что cart_details, но для столика: блюда «только в зале» нужны."""
    return _resolve(branch, cart, delivery_only=False)
