from urllib.parse import quote

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import cart as cart_api
from .models import (
    PrintBranch, PrintCategory, PrintCenter, PrintOptionValue, PrintOrder,
    PrintOrderItem, PrintProduct, PrintProductVariant, PrintPromoCode,
)


# ── helpers ────────────────────────────────────────────────────────────────

def _digits(phone):
    return "".join(ch for ch in (phone or "") if ch.isdigit() or ch == "+").lstrip("+")


def _tg_token():
    return (getattr(settings, "TG_BOT_TOKEN", "") or getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()


def _calc_promo(promo, subtotal):
    """Returns (discount_amount, free_delivery: bool)."""
    if promo.discount_type == PrintPromoCode.DiscountType.FREE_DELIVERY:
        return 0, True
    if promo.discount_type == PrintPromoCode.DiscountType.PERCENT:
        return round(subtotal * promo.discount_value / 100), False
    if promo.discount_type == PrintPromoCode.DiscountType.FIXED:
        return min(promo.discount_value, subtotal), False
    return 0, False


def _build_order_text(order):
    lines = [f"🖨️ Новый заказ №{order.id}"]
    if order.name:
        lines += ["", "Имя:", order.name]
    lines += ["", "Телефон:", order.phone]
    if order.address:
        lines += ["", "Адрес:", order.address]

    lines += ["", "Товары:"]
    for item in order.items.all():
        lines.append(item.product_name_snapshot)
        sel = item.selection_snapshot or {}
        variant = sel.get("variant")
        if variant:
            lines.append(f"Вариант: {variant.get('label')}")
        for opt in sel.get("options", []):
            delta = opt.get("price_delta")
            extra = f" (+{delta} сом)" if delta and str(delta) not in ("0", "0.00") else ""
            lines.append(f"{opt['group_name']}: {opt['value_label']}{extra}")
        lines.append(f"Количество: {item.qty}")
        lines.append(f"Цена: {item.unit_price:.0f} сом")
        if item.comment:
            lines.append(f"Комментарий: {item.comment}")
        lines.append("")

    if order.comment:
        lines += ["Комментарий к заказу:", order.comment, ""]

    lines.append(f"Подытог: {order.subtotal:.0f} сом")
    if order.delivery_fee:
        lines.append(f"Доставка: {order.delivery_fee:.0f} сом")
    if order.promo_code:
        lines.append(f"Промокод: {order.promo_code.code}")
        lines.append(f"Скидка: {order.discount_amount:.0f} сом")
    lines.append(f"Итого к оплате: {order.total:.0f} сом")
    return "\n".join(lines)


def _send_telegram(branch, text):
    if not branch.tg_chat_id:
        return
    token = _tg_token()
    if not token:
        return
    try:
        from integrations.telegram import send_message
        send_message(token, branch.tg_chat_id, text, message_thread_id=branch.tg_thread_id)
    except Exception:
        pass


# ── PUBLIC PAGES ─────────────────────────────────────────────────────────

def center_list(request):
    q = (request.GET.get("q") or "").strip()
    centers = (
        PrintCenter.objects.filter(is_active=True, branches__is_active=True)
        .distinct()
        .prefetch_related("branches")
        .order_by("name_ru")
    )
    if q:
        centers = centers.filter(name_ru__icontains=q)
    return render(request, "printshop/center_list.html", {"centers": centers, "q": q})


def center_detail(request, slug):
    center = get_object_or_404(PrintCenter, slug=slug, is_active=True)
    branches = center.branches.filter(is_active=True).order_by("name_ru")
    if branches.count() == 1:
        return redirect("printshop:branch_catalog", slug=center.slug, branch_id=branches.first().id)
    return render(request, "printshop/center_detail.html", {"center": center, "branches": branches})


def branch_catalog(request, slug, branch_id):
    center = get_object_or_404(PrintCenter, slug=slug, is_active=True)
    branch = get_object_or_404(PrintBranch, id=branch_id, center=center, is_active=True)

    categories = (
        PrintCategory.objects.filter(center=center, is_active=True)
        .order_by("sort_order", "id")
        .prefetch_related("products")
    )
    products = list(
        PrintProduct.objects.filter(center=center, is_available=True)
        .prefetch_related("photos", "variants", "option_groups__values")
        .order_by("sort_order", "id")
    )
    by_cat = {}
    for p in products:
        by_cat.setdefault(p.category_id, []).append(p)

    cat_sections = [
        {"cat": cat, "products": by_cat.get(cat.id, [])}
        for cat in categories if by_cat.get(cat.id)
    ]
    uncat_products = by_cat.get(None, [])

    cart = cart_api.get_cart(request, branch.id)
    rows, subtotal, qty_total = cart_api.cart_summary(branch, cart)

    products_json = {
        p.id: {
            "id": p.id,
            "name": p.name_ru,
            "description": p.description_ru,
            "base_price": str(p.base_price),
            "main_photo": p.main_photo.url if p.main_photo else "",
            "photos": [ph.photo.url for ph in p.photos.all()],
            "variants": [
                {"id": v.id, "label": v.label, "price": str(v.price), "is_default": v.is_default}
                for v in p.variants.all() if v.is_active
            ],
            "option_groups": [
                {
                    "id": g.id, "name": g.name, "is_required": g.is_required, "allow_multiple": g.allow_multiple,
                    "values": [
                        {"id": v.id, "label": v.label, "price_delta": str(v.price_delta), "is_default": v.is_default}
                        for v in g.values.all()
                    ],
                }
                for g in p.option_groups.all()
            ],
        }
        for p in products
    }

    return render(request, "printshop/branch_catalog.html", {
        "center": center, "branch": branch,
        "cat_sections": cat_sections, "uncat_products": uncat_products,
        "cart_qty": qty_total, "cart_total": subtotal,
        "products_json": products_json,
    })


# ── CART (AJAX) ──────────────────────────────────────────────────────────

def _cart_payload(branch, cart, promo_code=""):
    rows, subtotal, qty_total = cart_api.cart_summary(branch, cart)

    delivery_fee = branch.delivery_fee if branch.delivery_enabled else 0
    free_delivery_reached = False
    if branch.delivery_enabled and branch.free_delivery_from:
        if subtotal >= branch.free_delivery_from:
            delivery_fee = 0
            free_delivery_reached = True

    discount = 0
    promo_msg = ""
    promo_obj = None
    if promo_code:
        promo_obj = PrintPromoCode.objects.filter(branch=branch, code__iexact=promo_code).first()
        if promo_obj:
            ok, msg = promo_obj.is_valid()
            if ok:
                discount, free_delivery = _calc_promo(promo_obj, subtotal)
                if free_delivery:
                    delivery_fee = 0
                    free_delivery_reached = True
                promo_msg = "Промокод применён"
            else:
                promo_msg = msg
        else:
            promo_msg = "Промокод не найден"

    total = max(0, subtotal - discount + delivery_fee)

    return {
        "ok": True,
        "items": [
            {
                "line_id": r["line_id"],
                "name": r["product"].name_ru,
                "variant": r["variant"].label if r["variant"] else "",
                "options": [f"{o.group.name}: {o.label}" for o in r["options"]],
                "comment": r["comment"],
                "qty": r["qty"],
                "unit_price": str(r["unit_price"]),
                "line_total": str(r["line_total"]),
                "photo_url": r["product"].main_photo.url if r["product"].main_photo else "",
            }
            for r in rows
        ],
        "qty_total": qty_total,
        "subtotal": str(subtotal),
        "delivery_fee": str(delivery_fee),
        "free_delivery_reached": free_delivery_reached,
        "free_delivery_from": str(branch.free_delivery_from) if branch.free_delivery_from else "",
        "min_order_amount": str(branch.min_order_amount),
        "delivery_enabled": branch.delivery_enabled,
        "discount": str(discount),
        "promo_valid": bool(discount) or (promo_obj and promo_obj.discount_type == PrintPromoCode.DiscountType.FREE_DELIVERY and free_delivery_reached),
        "promo_msg": promo_msg,
        "total": str(total),
    }


def cart_json(request, branch_id):
    branch = get_object_or_404(PrintBranch, id=branch_id, is_active=True)
    cart = cart_api.get_cart(request, branch.id)
    promo_code = request.GET.get("promo", "")
    return JsonResponse(_cart_payload(branch, cart, promo_code))


@require_POST
def cart_add(request, branch_id):
    branch = get_object_or_404(PrintBranch, id=branch_id, is_active=True)
    product = get_object_or_404(PrintProduct, id=request.POST.get("product_id"), center=branch.center, is_available=True)

    variant_id = request.POST.get("variant_id") or None
    if variant_id:
        get_object_or_404(PrintProductVariant, id=variant_id, product=product, is_active=True)

    option_value_ids = [v for v in request.POST.getlist("option_value_id") if v]
    if option_value_ids:
        valid_ids = set(
            PrintOptionValue.objects.filter(id__in=option_value_ids, group__product=product)
            .values_list("id", flat=True)
        )
        option_value_ids = [int(v) for v in option_value_ids if int(v) in valid_ids]

    qty = request.POST.get("qty", "1")
    comment = request.POST.get("comment", "")

    cart_api.add_line(request, branch.id, product.id, variant_id, option_value_ids, qty, comment)
    cart = cart_api.get_cart(request, branch.id)
    return JsonResponse(_cart_payload(branch, cart))


@require_POST
def cart_update(request, branch_id, line_id):
    branch = get_object_or_404(PrintBranch, id=branch_id, is_active=True)
    cart_api.update_qty(request, branch.id, line_id, request.POST.get("qty"))
    cart = cart_api.get_cart(request, branch.id)
    return JsonResponse(_cart_payload(branch, cart))


@require_POST
def cart_remove(request, branch_id, line_id):
    branch = get_object_or_404(PrintBranch, id=branch_id, is_active=True)
    cart_api.remove_line(request, branch.id, line_id)
    cart = cart_api.get_cart(request, branch.id)
    return JsonResponse(_cart_payload(branch, cart))


def validate_promo(request, branch_id):
    branch = get_object_or_404(PrintBranch, id=branch_id, is_active=True)
    cart = cart_api.get_cart(request, branch.id)
    code = request.GET.get("code", "")
    return JsonResponse(_cart_payload(branch, cart, code))


# ── CHECKOUT ─────────────────────────────────────────────────────────────

@require_POST
def checkout(request, branch_id):
    branch = get_object_or_404(PrintBranch, id=branch_id, center__is_active=True, is_active=True)
    cart = cart_api.get_cart(request, branch.id)
    rows, subtotal, qty_total = cart_api.cart_summary(branch, cart)

    if not rows:
        return redirect("printshop:branch_catalog", slug=branch.center.slug, branch_id=branch.id)

    name = request.POST.get("name", "").strip()
    phone = request.POST.get("phone", "").strip()
    address = request.POST.get("address", "").strip()
    comment = request.POST.get("comment", "").strip()
    order_mode = request.POST.get("mode", "delivery" if branch.delivery_enabled else "pickup")
    is_delivery = order_mode == "delivery" and branch.delivery_enabled

    if not phone:
        return redirect("printshop:branch_catalog", slug=branch.center.slug, branch_id=branch.id)
    if is_delivery and branch.min_order_amount and subtotal < branch.min_order_amount:
        return redirect("printshop:branch_catalog", slug=branch.center.slug, branch_id=branch.id)

    delivery_fee = branch.delivery_fee if is_delivery else 0
    if is_delivery and branch.free_delivery_from and subtotal >= branch.free_delivery_from:
        delivery_fee = 0

    promo_code_str = request.POST.get("promo_code", "").strip()
    discount = 0
    promo_obj = None
    if promo_code_str:
        promo_obj = PrintPromoCode.objects.filter(branch=branch, code__iexact=promo_code_str).first()
        if promo_obj:
            ok, _msg = promo_obj.is_valid()
            if ok:
                discount, free_delivery = _calc_promo(promo_obj, subtotal)
                if free_delivery:
                    delivery_fee = 0
            else:
                promo_obj = None

    total = max(0, subtotal - discount + delivery_fee)

    with transaction.atomic():
        order = PrintOrder.objects.create(
            branch=branch, name=name, phone=phone, address=address, comment=comment,
            promo_code=promo_obj, subtotal=subtotal, discount_amount=discount,
            delivery_fee=delivery_fee, total=total,
        )
        PrintOrderItem.objects.bulk_create([
            PrintOrderItem(
                order=order,
                product=r["product"],
                product_name_snapshot=r["product"].name_ru,
                qty=r["qty"],
                unit_price=r["unit_price"],
                line_total=r["line_total"],
                comment=r["comment"],
                selection_snapshot={
                    "variant": {"label": r["variant"].label, "price": str(r["variant"].price)} if r["variant"] else None,
                    "options": [
                        {"group_name": o.group.name, "value_label": o.label, "price_delta": str(o.price_delta)}
                        for o in r["options"]
                    ],
                },
            )
            for r in rows
        ])
        if promo_obj:
            PrintPromoCode.objects.filter(id=promo_obj.id).update(used_count=F("used_count") + 1)

    cart_api.clear_cart(request, branch.id)

    order_text = _build_order_text(order)
    _send_telegram(branch, order_text)

    wa_phone = _digits(branch.whatsapp or branch.phone)
    if wa_phone:
        return redirect(f"https://wa.me/{wa_phone}?text={quote(order_text)}")

    return redirect("printshop:checkout_success", slug=branch.center.slug, branch_id=branch.id, order_id=order.id)


def checkout_success(request, slug, branch_id, order_id):
    branch = get_object_or_404(PrintBranch, id=branch_id)
    order = get_object_or_404(PrintOrder.objects.prefetch_related("items"), id=order_id, branch=branch)

    order_text = _build_order_text(order)
    wa_phone = _digits(branch.whatsapp or branch.phone)
    whatsapp_url = f"https://wa.me/{wa_phone}?text={quote(order_text)}" if wa_phone else ""
    whatsapp_deeplink = f"whatsapp://send?phone={wa_phone}&text={quote(order_text)}" if wa_phone else ""

    return render(request, "printshop/checkout_success.html", {
        "center": branch.center, "branch": branch, "order": order,
        "whatsapp_url": whatsapp_url, "whatsapp_deeplink": whatsapp_deeplink,
        "call_url": f"tel:{branch.phone}" if branch.phone else "",
        "msg_text": order_text,
    })
