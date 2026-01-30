from django.db.models import Q
from core.models import Restaurant, Branch
from catalog.models import BranchCategory, BranchCategoryItem, BranchItem
from django.utils.translation import get_language
from integrations.tasks import notify_new_order
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils.translation import get_language
from core.models import Branch
from catalog.models import BranchCategory, BranchCategoryItem, BranchItem
from orders.models import Order, OrderItem
from .cart import add_to_cart, set_qty, clear_cart, get_cart, cart_details
from django.utils.translation import gettext as _
def tr(obj, base: str, lang: str):
    """Если есть name_ru/name_ky/name_en — отдаём по языку, иначе base."""
    field = f"{base}_{lang}"
    if hasattr(obj, field):
        val = getattr(obj, field) or ""
        if val:
            return val
        # fallback на RU
        return getattr(obj, f"{base}_ru", "") or ""
    return getattr(obj, base, "")

def home(request):
    q = (request.GET.get("q") or "").strip()
    open_now = request.GET.get("open_now") == "1"

    restaurants = Restaurant.objects.filter(is_active=True).prefetch_related("branches").order_by("name_ru")

    if q:
        # если у Restaurant позже появятся name_ru/name_ky/name_en — расширишь тут
        restaurants = restaurants.filter(Q(name_ru__icontains=q))

    cards = []
    for r in restaurants:
        branches = [b for b in r.branches.all() if b.is_active]

        is_open = any(b.is_open_now() for b in branches)
        if open_now and not is_open:
            continue

        delivery_branches = [b for b in branches if b.delivery_enabled]
        has_delivery = bool(delivery_branches)

        min_order = min((b.min_order_amount for b in delivery_branches), default=None)
        min_fee = min((b.delivery_fee for b in delivery_branches), default=None)

        # “время работы” для карточки ресторана — показываем если у всех филиалов одинаково,
        # иначе не рискуем врать
        hours_text = None
        hours_set = set()
        for b in branches:
            if b.is_open_24h:
                hours_set.add("24/7")
            elif b.open_time and b.close_time:
                hours_set.add(f"{b.open_time.strftime('%H:%M')}–{b.close_time.strftime('%H:%M')}")
        if len(hours_set) == 1:
            hours_text = list(hours_set)[0]

        cards.append({
            "obj": r,
            "is_open": is_open,
            "has_delivery": has_delivery,
            "min_order": min_order,
            "min_fee": min_fee,
            "hours_text": hours_text,
            "branches_count": len(branches),
        })

    return render(request, "public_site/home.html", {"cards": cards, "q": q, "open_now": open_now})

def restaurant_detail(request, slug):
    restaurant = get_object_or_404(Restaurant, slug=slug, is_active=True)
    branches = restaurant.branches.filter(is_active=True).order_by("name_ru")
    return render(request, "public_site/restaurant_detail.html", {"restaurant": restaurant, "branches": branches})



def branch_menu(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    lang = (get_language() or "ru")[:2]

    # меню
    categories = BranchCategory.objects.filter(branch=branch, is_active=True).order_by("sort_order", "id")
    menu = []
    for bc in categories:
        rows = BranchCategoryItem.objects.select_related("branch_item__item").filter(
            branch_category=bc,
            branch_item__is_available=True,
        ).order_by("sort_order", "id")

        menu.append({
            "branch_category": bc,
            "items": rows,  # здесь row.branch_item и row.branch_item.item
        })

    # корзина
    cart = get_cart(request, branch.id)
    _, total, qty_total = cart_details(branch, cart)

    return render(request, "public_site/branch_menu.html", {
        "branch": branch,
        "menu": menu,
        "cart_qty": qty_total,
        "cart_total": total,
    })

@require_POST
def cart_add(request, branch_id: int, branch_item_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    bi = get_object_or_404(BranchItem, id=branch_item_id, branch=branch, is_available=True)

    qty = int(request.POST.get("qty", 1))
    if qty < 1:
        qty = 1

    add_to_cart(request, branch.id, bi.id, qty)
    return redirect("public_site:branch_menu", branch_id=branch.id)

def cart_detail(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    cart = get_cart(request, branch.id)
    rows, subtotal, qty_total = cart_details(branch, cart)

    delivery_fee = branch.delivery_fee if branch.delivery_enabled else Decimal("0")
    total = subtotal + delivery_fee

    return render(request, "public_site/cart_detail.html", {
        "branch": branch,
        "rows": rows,
        "qty_total": qty_total,
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "total": total,
    })

@require_POST
def cart_update(request, branch_id: int, branch_item_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    qty = int(request.POST.get("qty", 1))
    set_qty(request, branch.id, branch_item_id, qty)
    return redirect("public_site:cart_detail", branch_id=branch.id)

@require_POST
def cart_remove(request, branch_id: int, branch_item_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    set_qty(request, branch.id, branch_item_id, 0)
    return redirect("public_site:cart_detail", branch_id=branch.id)

@require_POST
def checkout(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    cart = get_cart(request, branch.id)
    rows, subtotal, qty_total = cart_details(branch, cart)

    if qty_total == 0:
        messages.error(request, _("Корзина пуста."))
        return redirect("public_site:cart_detail", branch_id=branch.id)

    order_type = Order.Type.DELIVERY if branch.delivery_enabled else Order.Type.PICKUP

    name = (request.POST.get("name") or "").strip()
    phone = (request.POST.get("phone") or "").strip()
    address = (request.POST.get("address") or "").strip()
    comment = (request.POST.get("comment") or "").strip()

    if not name or not phone:
        messages.error(request, _("Укажите имя и телефон."))
        return redirect("public_site:cart_detail", branch_id=branch.id)
    payment_method = request.POST.get("payment_method") or Order.PaymentMethod.CASH
   
    if payment_method not in [Order.PaymentMethod.CASH, Order.PaymentMethod.ONLINE]:
        payment_method = Order.PaymentMethod.CASH


    if order_type == Order.Type.DELIVERY:
        if not address:
            messages.error(request, _("Укажите адрес доставки."))
            return redirect("public_site:cart_detail", branch_id=branch.id)
        if subtotal < branch.min_order_amount:
            messages.error(request, _("Минимальная сумма заказа для доставки: %(min)s") % {"min": branch.min_order_amount})
            return redirect("public_site:cart_detail", branch_id=branch.id)

    delivery_fee = branch.delivery_fee if order_type == Order.Type.DELIVERY else Decimal("0")
    total = subtotal + delivery_fee

    order = Order.objects.create(
        branch=branch,
        type=order_type,
        status=Order.Status.NEW,
        customer_name=name,
        customer_phone=phone,
        delivery_address=address if order_type == Order.Type.DELIVERY else "",
        comment=comment,
        total_amount=total,
        payment_method=payment_method,
        payment_status=Order.PaymentStatus.UNPAID,
    )

    for r in rows:
        bi = r["branch_item"]
        qty = r["qty"]
        OrderItem.objects.create(
            order=order,
            item=bi.item,
            qty=qty,
            price_snapshot=bi.price,
            line_total=bi.price * qty
        )

    notify_new_order.delay(order.id)
    clear_cart(request, branch.id)
    return redirect("public_site:checkout_success", branch_id=branch.id, order_id=order.id)

def checkout_success(request, branch_id: int, order_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    order = get_object_or_404(Order, id=order_id, branch=branch)
    return render(request, "public_site/checkout_success.html", {"branch": branch, "order": order})

# def branch_menu(request, branch_id: int):
#     branch = get_object_or_404(Branch, id=branch_id, is_active=True)
#     lang = get_language() or "ru"

#     categories = BranchCategory.objects.filter(branch=branch, is_active=True).order_by("sort_order", "id")

#     menu = []
#     for bc in categories:
#         rows = BranchCategoryItem.objects.select_related("branch_item__item").filter(
#             branch_category=bc,
#             branch_item__is_available=True,
#         ).order_by("sort_order", "id")

#         menu.append({
#             "category_name": tr(bc.category, "name", lang),
#             "items": [{
#                 "branch_item_id": x.branch_item_id,
#                 "name": tr(x.branch_item.item, "name", lang),
#                 "description": tr(x.branch_item.item, "description", lang),
#                 "price": x.branch_item.price,
#             } for x in rows]
#         })

#     return render(request, "public_site/branch_menu.html", {"branch": branch, "menu": menu})
