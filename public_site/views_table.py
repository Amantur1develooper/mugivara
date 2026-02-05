
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


def table_cart(request, token: str):
    place = get_object_or_404(Place, token=token, is_active=True)
    branch = place.floor.branch

    cart = get_cart(request, branch.id)
    rows, subtotal, qty_total = cart_details(branch, cart)

    total = subtotal  # ✅ без доставки

    return render(request, "public_site/table_cart.html", {
        "branch": branch,
        "place": place,
        "rows": rows,
        "qty_total": qty_total,
        "subtotal": subtotal,
        "total": total,
        "token": token,
    })











from decimal import Decimal
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils.translation import gettext as _

from reservations.models import Place
from core.models import Branch
from catalog.models import BranchCategory, BranchCategoryItem, BranchItem
from orders.models import Order, OrderItem

from public_site.cart import get_table_cart, set_table_cart, clear_table_cart, table_cart_totals


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
    })


@require_POST
def table_add_to_cart(request, token: str, branch_item_id: int):
    place = get_object_or_404(Place, token=token, is_active=True)
    branch = place.floor.branch
    bi = get_object_or_404(BranchItem, id=branch_item_id, branch=branch, is_available=True)

    qty = int(request.POST.get("qty") or 1)
    qty = max(1, min(qty, 99))

    cart = get_table_cart(request, token)
    key = str(bi.id)
    cart[key] = int(cart.get(key, 0)) + qty
    set_table_cart(request, token, cart)

    rows, subtotal, qty_total = table_cart_totals(branch, cart)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "qty": qty_total, "total": str(subtotal)})

    return redirect("table_menu", token=token)



@require_POST
def table_checkout(request, token: str):
    place = get_object_or_404(Place, token=token, is_active=True)
    branch = place.floor.branch

    cart = get_table_cart(request, token)
    rows, subtotal, qty_total = table_cart_totals(branch, cart)
    if qty_total == 0:
        messages.error(request, _("Корзина пуста."))
        return redirect("table_cart", token=token)

    # ✅ поля необязательны
    name = (request.POST.get("name") or "").strip()
    phone = (request.POST.get("phone") or "").strip()
    comment = (request.POST.get("comment") or "").strip()

    order = Order.objects.create(
        branch=branch,
        type=Order.Type.DINE_IN,        # ✅ В заведении
        table_place=place,              # ✅ какой стол
        status=Order.Status.NEW,
        customer_name=name,
        customer_phone=phone,
        comment=comment,
        total_amount=subtotal,
        payment_method=Order.PaymentMethod.CASH,
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
            line_total=bi.price * qty,
        )

    clear_table_cart(request, token)

    # ⚠️ ВАЖНО: уведомление в телегу НЕ дублируем!
    # Уведомление должно уходить либо через signals.py, либо здесь — но не в двух местах.

    return redirect("table_success", token=token, order_id=order.id)


def table_success(request, token: str, order_id: int):
    place = get_object_or_404(Place, token=token, is_active=True)
    branch = place.floor.branch
    order = get_object_or_404(Order, id=order_id, branch=branch)

    return render(request, "public_site/table_success.html", {
        "branch": branch,
        "place": place,
        "order": order,
        "token": token,
    })
