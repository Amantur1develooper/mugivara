
# public_site/views_table.py
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages
from django.utils.translation import gettext as _
from decimal import Decimal
from django.db import transaction
from django.db.models import F

from reservations.models import Place
from core.models import Branch, Restaurant
from catalog.models import BranchCategory, BranchCategoryItem, BranchItem, ItemCategory, DishConstructor
from orders.models import Order, OrderItem, ConstructorOrderItem
from .cart import get_cart, cart_details, clear_cart
from public_site.cart import get_table_cart, set_table_cart, clear_table_cart, table_cart_totals


def _table_cart_key(token: str) -> str:
    return f"table_cart_{token}"


def _get_cart(request, token: str) -> dict:
    return request.session.get(_table_cart_key(token), {})  # {"12": 2, "15": 1}


def _save_cart(request, token: str, cart: dict):
    request.session[_table_cart_key(token)] = cart
    request.session.modified = True


def _cart_calc(branch, cart: dict):
    """cart: {"branch_item_id": qty}"""
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


# ── КОНСТРУКТОР КОРЗИНА (table QR flow) ──────────────────────────────────────

def _table_cx_key(token: str) -> str:
    return f"table_cx_{token}"


def _get_cx_cart(request, token: str) -> list:
    return request.session.get(_table_cx_key(token), [])


def _save_cx_cart(request, token: str, cart: list):
    request.session[_table_cx_key(token)] = cart
    request.session.modified = True


def _cx_cart_totals(cx_cart: list):
    """Returns (total_qty, total_sum) for constructor cart."""
    total_qty = 0
    total_sum = Decimal("0")
    for item in cx_cart:
        q = int(item.get("qty", 0))
        if q <= 0:
            continue
        total_qty += q
        total_sum += Decimal(str(item["unit_price"])) * q
    return total_qty, total_sum


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

    _, reg_qty, reg_total = _cart_calc(branch, cart)
    cx_qty, cx_total = _cx_cart_totals(_get_cx_cart(request, token))
    return JsonResponse({"ok": True, "qty": reg_qty + cx_qty, "total": float(reg_total + cx_total)})


@require_POST
def table_add_constructor(request, token: str, cx_id: int):
    """Add a constructor dish to the table cart."""
    place = get_object_or_404(Place, token=token, is_active=True)
    branch = place.floor.branch
    cx = get_object_or_404(DishConstructor, id=cx_id, branch=branch, is_active=True)

    try:
        selections_raw = json.loads(request.POST.get("selections", "{}"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Неверные данные"}, status=400)

    groups = cx.groups.prefetch_related("ingredients").order_by("sort_order", "id")
    selections = []
    total_price = Decimal("0")

    for g in groups:
        chosen_ids = selections_raw.get(str(g.id), [])
        if not isinstance(chosen_ids, list):
            chosen_ids = [chosen_ids]
        chosen_ids = [int(i) for i in chosen_ids if i]

        if g.min_select and len(chosen_ids) < g.min_select:
            return JsonResponse({"ok": False, "error": f"Выберите минимум {g.min_select} в «{g.name}»"}, status=400)
        if g.max_select > 0 and len(chosen_ids) > g.max_select:
            return JsonResponse({"ok": False, "error": f"Максимум {g.max_select} в «{g.name}»"}, status=400)

        ings_data = []
        for ing in g.ingredients.select_related("branch_item__item").filter(is_active=True, id__in=chosen_ids):
            ings_data.append({"id": ing.id, "name": ing.display_name, "price": str(ing.display_price)})
            total_price += ing.display_price

        if ings_data:
            selections.append({"gid": g.id, "gname": g.name, "ings": ings_data})

    unit_price = total_price

    cx_cart = _get_cx_cart(request, token)
    idx = max((item["idx"] for item in cx_cart), default=-1) + 1
    cx_cart.append({
        "idx": idx,
        "cx_id": cx.id,
        "cx_name": cx.name,
        "base_price": str(cx.base_price),
        "selections": selections,
        "unit_price": str(unit_price),
        "qty": 1,
        "line_total": str(unit_price),
    })
    _save_cx_cart(request, token, cx_cart)

    cart = _get_cart(request, token)
    _, reg_qty, reg_total = _cart_calc(branch, cart)
    cx_qty, cx_total = _cx_cart_totals(cx_cart)
    return JsonResponse({"ok": True, "qty": reg_qty + cx_qty, "total": float(reg_total + cx_total)})


@require_POST
def table_cx_update(request, token: str):
    """Update qty or remove a constructor cart item."""
    place = get_object_or_404(Place, token=token, is_active=True)
    branch = place.floor.branch

    idx = int(request.POST.get("idx") or -1)
    action = (request.POST.get("action") or "").strip()

    cx_cart = _get_cx_cart(request, token)
    item = next((x for x in cx_cart if x["idx"] == idx), None)
    if not item:
        return JsonResponse({"ok": False}, status=404)

    unit_price = Decimal(str(item["unit_price"]))

    if action == "inc":
        item["qty"] = int(item["qty"]) + 1
    elif action == "dec":
        item["qty"] = int(item["qty"]) - 1
    elif action == "remove":
        item["qty"] = 0

    new_qty = int(item["qty"])
    if new_qty <= 0:
        cx_cart = [x for x in cx_cart if x["idx"] != idx]
        new_line = Decimal("0")
        new_qty = 0
    else:
        new_line = unit_price * new_qty
        item["line_total"] = str(new_line)

    _save_cx_cart(request, token, cx_cart)

    cart = _get_cart(request, token)
    _, reg_qty, reg_total = _cart_calc(branch, cart)
    cx_qty, cx_total = _cx_cart_totals(cx_cart)

    return JsonResponse({
        "ok": True,
        "item_qty": new_qty,
        "line_total": str(new_line),
        "qty": reg_qty + cx_qty,
        "total": str(reg_total + cx_total),
    })


def table_cart(request, token):
    place = get_object_or_404(Place, token=token, is_active=True)
    branch = place.floor.branch

    cart = _get_cart(request, token)
    rows, reg_qty, reg_total = _cart_calc(branch, cart)

    cx_cart = _get_cx_cart(request, token)
    cx_qty, cx_total = _cx_cart_totals(cx_cart)

    return render(request, "public_site/table_cart.html", {
        "token": token,
        "place": place,
        "branch": branch,
        "rows": rows,
        "cx_rows": cx_cart,
        "cart_qty": reg_qty + cx_qty,
        "cart_total": reg_total + cx_total,
        "table": True,
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

        # увеличиваем рейтинг ресторана
        Restaurant.objects.filter(pk=branch.restaurant_id).update(rating=F("rating") + Decimal("0.1"))

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
            branch_item__is_available=True,
        ).order_by("sort_order", "id")

        menu.append({"branch_category": bc, "items": rows})

    # Конструкторы — показываем только если есть хотя бы один активный
    constructors_qs = (
        DishConstructor.objects
        .filter(branch=branch, is_active=True)
        .prefetch_related("groups__ingredients")
        .order_by("sort_order", "id")
    )
    constructors = [
        cx for cx in constructors_qs
        if any(g.ingredients.filter(is_active=True).exists() for g in cx.groups.all())
    ]

    cart = _get_cart(request, token)
    _, reg_qty, reg_total = _cart_calc(branch, cart)
    cx_cart = _get_cx_cart(request, token)
    cx_qty, cx_total = _cx_cart_totals(cx_cart)

    return render(request, "public_site/table_menu.html", {
        "branch": branch,
        "place": place,
        "menu": menu,
        "constructors": constructors,
        "token": token,
        "cart_qty": reg_qty + cx_qty,
        "cart_total": reg_total + cx_total,
        "table": True,
    })
    
    
from django.views.decorators.http import require_POST

@require_POST
def table_cart_update(request, token):
    place = get_object_or_404(Place, token=token, is_active=True)
    branch = place.floor.branch

    action = (request.POST.get("action") or "").strip()
    bi_id = int(request.POST.get("branch_item_id") or 0)

    bi = get_object_or_404(BranchItem, id=bi_id, branch=branch)

    cart = _get_cart(request, token)  # твоя функция/сессионная корзина
    k = str(bi_id)
    cur = int(cart.get(k, 0))

    if action == "inc":
        new_qty = cur + 1
    elif action == "dec":
        new_qty = cur - 1
    elif action == "remove":
        new_qty = 0
    else:
        return JsonResponse({"ok": False}, status=400)

    if new_qty <= 0:
        cart.pop(k, None)
        new_qty = 0
    else:
        cart[k] = new_qty

    _save_cart(request, token, cart)
    rows, reg_qty, reg_total = _cart_calc(branch, cart)
    cx_qty, cx_total = _cx_cart_totals(_get_cx_cart(request, token))

    line_total = "0"
    for r in rows:
        if r["branch_item"].id == bi_id:
            line_total = str(r["line_total"])
            break

    return JsonResponse({
        "ok": True,
        "item_qty": new_qty,
        "line_total": line_total,
        "qty": reg_qty + cx_qty,
        "total": str(reg_total + cx_total),
    })


from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from reservations.models import Place
from integrations.tasks import notify_call_waiter  # сделаем ниже
from django.http import HttpResponse

@require_POST
def table_call_waiter(request, token):
    place = get_object_or_404(Place, token=token, is_active=True)
    branch = place.floor.branch

    # можно добавить короткий текст
    note = (request.POST.get("note") or "").strip()[:200]

    notify_call_waiter.delay(place.id, note)
    return JsonResponse({"ok": True})
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from reservations.models import Place
from orders.models import Order, OrderItem
from catalog.models import BranchItem

@require_POST
def table_create_order(request, token):
    place = get_object_or_404(Place, token=token, is_active=True)
    branch = place.floor.branch

    customer_name = (request.POST.get("customer_name") or "").strip()[:120]
    comment = (request.POST.get("comment") or "").strip()

    cart = _get_cart(request, token)
    cx_cart = _get_cx_cart(request, token)

    if not cart and not cx_cart:
        return redirect("table_cart", token=token)

    order = Order.objects.create(
        branch=branch,
        type=Order.Type.DINE_IN,
        table_place=place,
        status=Order.Status.NEW,
        customer_name=customer_name,
        comment=comment,
        payment_method=Order.PaymentMethod.CASH,
        payment_status=Order.PaymentStatus.UNPAID,
    )

    total = Decimal("0")

    for bi_id, qty in cart.items():
        bi = get_object_or_404(BranchItem, id=int(bi_id), branch=branch)
        qty = int(qty)
        line_total = bi.price * qty
        OrderItem.objects.create(
            order=order,
            item=bi.item,
            qty=qty,
            price_snapshot=bi.price,
            line_total=line_total,
        )
        total += line_total

    for cx_item in cx_cart:
        qty = int(cx_item.get("qty", 1))
        unit_price = Decimal(str(cx_item["unit_price"]))
        line_total = unit_price * qty
        cx = get_object_or_404(DishConstructor, id=cx_item["cx_id"])
        ConstructorOrderItem.objects.create(
            order=order,
            constructor=cx,
            constructor_name_snapshot=cx_item["cx_name"],
            qty=qty,
            unit_price=unit_price,
            line_total=line_total,
            ingredients_snapshot=cx_item.get("selections", []),
        )
        total += line_total

    order.total_amount = total
    order.save(update_fields=["total_amount"])

    _save_cart(request, token, {})
    _save_cx_cart(request, token, [])

    Restaurant.objects.filter(pk=branch.restaurant_id).update(rating=F("rating") + Decimal("0.1"))

    return redirect("table_success", token=token, order_id=order.id)


# ── Branch tables public page ─────────────────────────────────────────────────

def branch_tables_page(request, branch_id):
    from core.models import Branch
    from reservations.models import Floor
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    floors = (Floor.objects
              .filter(branch=branch, is_active=True)
              .prefetch_related("places")
              .order_by("sort_order", "id"))
    floors_with_tables = [
        {"floor": f, "places": [p for p in f.places.all() if p.is_active]}
        for f in floors
        if any(p.is_active for p in f.places.all())
    ]
    return render(request, "public_site/branch_tables.html", {
        "branch": branch,
        "floors": floors_with_tables,
    })
