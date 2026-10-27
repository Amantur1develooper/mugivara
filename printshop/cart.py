import uuid
from decimal import Decimal

from .models import PrintOptionValue, PrintProduct, PrintProductVariant

SESSION_KEY = "printshop_cart"


def _cart_key(branch_id):
    return str(branch_id)


def get_cart(request, branch_id):
    root = request.session.get(SESSION_KEY, {})
    return dict(root.get(_cart_key(branch_id), {}))


def save_cart(request, branch_id, cart):
    root = request.session.get(SESSION_KEY, {})
    root[_cart_key(branch_id)] = cart
    request.session[SESSION_KEY] = root
    request.session.modified = True


def clear_cart(request, branch_id):
    root = request.session.get(SESSION_KEY, {})
    root.pop(_cart_key(branch_id), None)
    request.session[SESSION_KEY] = root
    request.session.modified = True


HARD_MAX = 100000   # потолок на случай опечатки в форме; тиражи бывают большими


def _product_rule(product_id):
    """Правило тиража товара. None — если товар не найден."""
    return PrintProduct.objects.filter(id=product_id).only(
        "id", "min_qty", "qty_step", "max_qty").first()


def _clamp(product, qty):
    qty = min(HARD_MAX, max(0, int(qty or 0)))
    return product.clamp_qty(qty) if product else max(1, qty)


def add_line(request, branch_id, product_id, variant_id=None, option_value_ids=None, qty=1, comment=""):
    option_value_ids = sorted(int(x) for x in (option_value_ids or []))
    product = _product_rule(product_id)
    qty = _clamp(product, qty)
    comment = (comment or "").strip()[:300]

    cart = get_cart(request, branch_id)

    # merge into an identical existing line (same product/variant/options/comment)
    for line in cart.values():
        if (
            line["product_id"] == product_id
            and line.get("variant_id") == variant_id
            and sorted(line.get("option_value_ids", [])) == option_value_ids
            and line.get("comment", "") == comment
        ):
            # складываем тиражи: 100 + 100 = 200, кратность при этом сохраняется
            line["qty"] = _clamp(product, line["qty"] + qty)
            save_cart(request, branch_id, cart)
            return

    line_id = uuid.uuid4().hex[:12]
    cart[line_id] = {
        "product_id": int(product_id),
        "variant_id": int(variant_id) if variant_id else None,
        "option_value_ids": option_value_ids,
        "qty": qty,
        "comment": comment,
    }
    save_cart(request, branch_id, cart)


def update_qty(request, branch_id, line_id, qty):
    cart = get_cart(request, branch_id)
    if line_id not in cart:
        return
    qty = int(qty or 0)
    product = _product_rule(cart[line_id]["product_id"])
    # «минус» на минимальном тираже убирает позицию целиком — иначе кнопка
    # выглядела бы сломанной: нажимаешь, а число не меняется
    if product and qty < product.order_min:
        cart.pop(line_id, None)
    elif qty <= 0:
        cart.pop(line_id, None)
    else:
        cart[line_id]["qty"] = _clamp(product, qty)
    save_cart(request, branch_id, cart)


def remove_line(request, branch_id, line_id):
    cart = get_cart(request, branch_id)
    cart.pop(line_id, None)
    save_cart(request, branch_id, cart)


def resolve_lines(branch, cart):
    """Resolve raw session cart dict into enriched rows for display/checkout."""
    product_ids = {l["product_id"] for l in cart.values()}
    variant_ids = {l["variant_id"] for l in cart.values() if l.get("variant_id")}
    option_ids = {oid for l in cart.values() for oid in l.get("option_value_ids", [])}

    products = {
        p.id: p for p in PrintProduct.objects.filter(
            id__in=product_ids, center=branch.center, is_available=True
        )
    }
    variants = {
        v.id: v for v in PrintProductVariant.objects.filter(id__in=variant_ids, is_active=True)
    }
    options = {
        o.id: o for o in PrintOptionValue.objects.select_related("group").filter(id__in=option_ids)
    }

    rows = []
    for line_id, line in cart.items():
        product = products.get(line["product_id"])
        if not product:
            continue
        variant = variants.get(line["variant_id"]) if line.get("variant_id") else None
        unit_price = variant.price if variant else product.base_price
        opt_rows = []
        for oid in line.get("option_value_ids", []):
            ov = options.get(oid)
            if ov and ov.group.product_id == product.id:
                opt_rows.append(ov)
                unit_price += ov.price_delta

        qty = line["qty"]
        rows.append({
            "line_id": line_id,
            "product": product,
            "variant": variant,
            "options": opt_rows,
            "qty": qty,
            "comment": line.get("comment", ""),
            "unit_price": unit_price,
            "line_total": unit_price * qty,
        })
    return rows


def cart_summary(branch, cart):
    rows = resolve_lines(branch, cart)
    subtotal = sum((r["line_total"] for r in rows), Decimal("0"))
    qty_total = sum(r["qty"] for r in rows)
    return rows, subtotal, qty_total
