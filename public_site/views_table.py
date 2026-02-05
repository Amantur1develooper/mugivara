
# public_site/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages
from django.utils.translation import gettext as _
from decimal import Decimal

from reservations.models import Place
from core.models import Branch
from catalog.models import BranchCategory, BranchCategoryItem, BranchItem
from orders.models import Order, OrderItem
from .cart import get_cart, cart_details, clear_cart
from public_site.cart import get_table_cart, set_table_cart, clear_table_cart, table_cart_totals
from decimal import Decimal
from django.http import JsonResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.db import transaction

from reservations.models import Place
from catalog.models import BranchCategory, BranchItem, ItemCategory  # если у тебя ItemCategory называется иначе — поправь
from orders.models import Order, OrderItem


def _table_cart_key(token: str) -> str:
    return f"table_cart_{token}"


def _get_cart(request, token: str) -> dict:
    return request.session.get(_table_cart_key(token), {})  # {"12": 2, "15": 1}


def _save_cart(request, token: str, cart: dict):
    request.session[_table_cart_key(token)] = cart
    request.session.modified = True


def _cart_calc(branch, cart: dict):
    """
    cart: {"branch_item_id": qty}
    """
    ids = [int(k) for k in cart.keys()] if cart else []
    items = (BranchItem.objects
             .filter(branch=branch, id__in=ids)
             .select_related("item"))

    rows = []
    total_qty = 0
    total_sum = Decimal("0")

    bi_map = {bi.id: bi for bi in items}

    for k, qty in cart.items():
        bi_id = int(k)
        qty = int(qty)
        bi = bi_map.get(bi_id)
        if not bi or qty <= 0:
            continue
        line = (bi.price or 0) * qty
        rows.append({"branch_item": bi, "qty": qty, "line_total": line})
        total_qty += qty
        total_sum += Decimal(str(line))

    return rows, total_qty, total_sum


def _build_branch_menu(branch):
    """
    menu как в твоём шаблоне: [{branch_category, items:[{branch_item}...]}]
    ВАЖНО: для QR-стола НЕ фильтруем delivery_available.
    """
    menu = []
    cats = (BranchCategory.objects
            .filter(branch=branch, is_active=True)
            .select_related("category")
            .order_by("sort_order", "id"))

    for bc in cats:
        item_ids = ItemCategory.objects.filter(category=bc.category).values_list("item_id", flat=True)
        bis = (BranchItem.objects
               .filter(branch=branch, is_available=True, item_id__in=item_ids)
               .select_related("item")
               .order_by("sort_order", "id"))

        menu.append({
            "branch_category": bc,
            "items": [{"branch_item": bi} for bi in bis],
        })
    return menu





@require_POST
def table_add_to_cart(request, token, branch_item_id: int):
    place = get_object_or_404(Place, token=token, is_active=True)
    branch = place.floor.branch

    bi = get_object_or_404(BranchItem, id=branch_item_id, branch=branch, is_available=True)

    qty = int(request.POST.get("qty") or 1)
    if qty < 1:
        qty = 1

    cart = _get_cart(request, token)
    k = str(bi.id)
    cart[k] = int(cart.get(k, 0)) + qty
    _save_cart(request, token, cart)

    _rows, cart_qty, cart_total = _cart_calc(branch, cart)
    return JsonResponse({"ok": True, "qty": cart_qty, "total": float(cart_total)})


def table_cart(request, token):
    place = get_object_or_404(Place, token=token, is_active=True)
    branch = place.floor.branch

    cart = _get_cart(request, token)
    rows, cart_qty, cart_total = _cart_calc(branch, cart)

    return render(request, "public_site/table_cart.html", {
        "token": token,
        "place": place,
        "branch": branch,
        "rows": rows,
        "cart_qty": cart_qty,
        "cart_total": cart_total,
        'table':True
    })


@transaction.atomic
def table_checkout(request, token):
    place = get_object_or_404(Place, token=token, is_active=True)
    branch = place.floor.branch

    cart = _get_cart(request, token)
    rows, cart_qty, cart_total = _cart_calc(branch, cart)
    if cart_qty == 0:
        return redirect("table_menu", token=token)

    if request.method == "POST":
        name = (request.POST.get("customer_name") or "").strip()
        phone = (request.POST.get("customer_phone") or "").strip()
        comment = (request.POST.get("comment") or "").strip()

        order = Order.objects.create(
            type=Order.Type.DINE_IN,              # ✅ В заведении
            branch=branch,
            table_place=place,                    # ✅ привязка к столу
            status=Order.Status.NEW,
            customer_name=name,
            customer_phone=phone,
            comment=comment,
            total_amount=cart_total,
            payment_method=Order.PaymentMethod.CASH,
            payment_status=Order.PaymentStatus.UNPAID,
        )

        for r in rows:
            bi = r["branch_item"]
            qty = r["qty"]
            line_total = r["line_total"]
            OrderItem.objects.create(
                order=order,
                item=bi.item,
                qty=qty,
                price_snapshot=bi.price,
                line_total=line_total,
            )

        # ✅ очищаем корзину
        _save_cart(request, token, {})

        # ⚠️ ВАЖНО: чтобы не было дублей, отправку в телегу делай ТОЛЬКО в одном месте.
        # Лучше оставить через signals.py (on_commit) и тут НЕ вызывать notify_new_order.

        return redirect("table_success", token=token, order_id=order.id)

    return render(request, "public_site/table_checkout.html", {
        "token": token,
        "place": place,
        "branch": branch,
        "rows": rows,
        "cart_qty": cart_qty,
        "cart_total": cart_total,
    })


def table_success(request, token, order_id: int):
    place = get_object_or_404(Place, token=token, is_active=True)
    branch = place.floor.branch
    order = get_object_or_404(Order, id=order_id, branch=branch)

    return render(request, "public_site/table_success.html", {
        "token": token,
        "place": place,
        "branch": branch,
        "order": order,
    })
def table_menu(request, token: str):
    place = get_object_or_404(Place, token=token, is_active=True)
    branch = place.floor.branch

    categories = BranchCategory.objects.filter(branch=branch, is_active=True).order_by("sort_order", "id")

    menu = []
    for bc in categories:
        rows = BranchCategoryItem.objects.select_related("branch_item__item").filter(
            branch_category=bc,
            branch_item__is_available=True,  # ✅ в зале показываем всё доступное
        ).order_by("sort_order", "id")

        menu.append({"branch_category": bc, "items": rows})

    cart = get_table_cart(request, token)
    _, subtotal, qty_total = table_cart_totals(branch, cart)

    return render(request, "public_site/table_menu.html", {
        "branch": branch,
        "place": place,
        "menu": menu,
        "token": token,
        "cart_qty": qty_total,
        "cart_total": subtotal,
        'table':True,
    })