from decimal import Decimal, InvalidOperation
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db.models import Sum, Count, Q

from .models import (
    Store, StoreBranch, StoreCategory, StoreProduct,
    StoreStock, StoreOrder, StoreOrderItem, StoreMembership,
)

LOGIN_URL = "dashboard:login"


# ── helpers ───────────────────────────────────────────────────────────────────

def _user_stores(user):
    ids = StoreMembership.objects.filter(user=user).values_list("store_id", flat=True)
    return Store.objects.filter(id__in=ids)


def _has_store_access(user, store):
    if user.is_superuser:
        return True
    return StoreMembership.objects.filter(user=user, store=store).exists()


def _has_branch_access(user, branch):
    return _has_store_access(user, branch.store)


def _dec(val, default="0"):
    try:
        return Decimal(val or default)
    except InvalidOperation:
        return Decimal(default)


# ── HOME ──────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def shop_home(request):
    if request.user.is_superuser:
        stores = Store.objects.all().prefetch_related("branches")
    else:
        stores = _user_stores(request.user).prefetch_related("branches")

    data = []
    for store in stores:
        branches = list(store.branches.filter(is_active=True).order_by("name_ru"))
        new_orders = StoreOrder.objects.filter(
            branch__store=store, status=StoreOrder.Status.NEW
        ).count()
        data.append({"store": store, "branches": branches, "new_orders": new_orders})

    return render(request, "dashboard/shops/home.html", {"data": data})


# ── STORE EDIT ────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def shop_store_edit(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    if not _has_store_access(request.user, store):
        return redirect("dashboard:shop_home")

    if request.method == "POST":
        name = request.POST.get("name_ru", "").strip()
        if name:
            store.name_ru = name
        store.about_ru = request.POST.get("about_ru", "").strip()
        store.is_active = request.POST.get("is_active") == "on"
        if request.FILES.get("logo"):
            store.logo = request.FILES["logo"]
        store.save()
        messages.success(request, "Данные магазина сохранены")
        return redirect("dashboard:shop_store_edit", store_id=store.id)

    return render(request, "dashboard/shops/store_edit.html", {"store": store})


# ── BRANCH EDIT ───────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def shop_branch_edit(request, branch_id):
    branch = get_object_or_404(StoreBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:shop_home")

    if request.method == "POST":
        branch.name_ru          = request.POST.get("name_ru", branch.name_ru).strip()
        branch.address          = request.POST.get("address", "").strip()
        branch.phone            = request.POST.get("phone", "").strip()
        branch.map_url          = request.POST.get("map_url", "").strip()
        branch.is_active        = request.POST.get("is_active") == "on"
        branch.delivery_enabled = request.POST.get("delivery_enabled") == "on"
        branch.delivery_fee     = _dec(request.POST.get("delivery_fee"))
        branch.min_order_amount = _dec(request.POST.get("min_order_amount"))
        if request.FILES.get("cover_photo"):
            branch.cover_photo = request.FILES["cover_photo"]
        branch.save()
        messages.success(request, "Настройки филиала сохранены")
        return redirect("dashboard:shop_branch_edit", branch_id=branch.id)

    return render(request, "dashboard/shops/branch_edit.html", {
        "branch": branch, "store": branch.store,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def shop_branch_toggle(request, branch_id):
    branch = get_object_or_404(StoreBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:shop_home")
    branch.is_active = not branch.is_active
    branch.save(update_fields=["is_active"])
    return redirect("dashboard:shop_home")


# ── PRODUCTS ──────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def shop_product_list(request, branch_id):
    branch = get_object_or_404(StoreBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:shop_home")

    stocks = (
        StoreStock.objects
        .filter(branch=branch)
        .select_related("product", "product__category")
        .order_by("product__category__sort_order", "product__id")
    )
    categories = branch.store.categories.filter(is_active=True).order_by("sort_order", "id")

    return render(request, "dashboard/shops/product_list.html", {
        "branch": branch,
        "store": branch.store,
        "stocks": stocks,
        "categories": categories,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def shop_stock_update(request, stock_id):
    stock = get_object_or_404(StoreStock, id=stock_id)
    if not _has_branch_access(request.user, stock.branch):
        return JsonResponse({"ok": False}, status=403)
    try:
        qty = Decimal(request.POST.get("qty", ""))
        if qty < 0:
            raise ValueError
    except Exception:
        return JsonResponse({"ok": False, "error": "Некорректное значение"})
    stock.qty = qty
    stock.save(update_fields=["qty"])
    return JsonResponse({"ok": True, "qty": str(stock.qty)})


@require_POST
@login_required(login_url=LOGIN_URL)
def shop_price_update(request, stock_id):
    stock = get_object_or_404(StoreStock, id=stock_id)
    if not _has_branch_access(request.user, stock.branch):
        return JsonResponse({"ok": False}, status=403)
    try:
        price = Decimal(request.POST.get("price", ""))
        if price < 0:
            raise ValueError
    except Exception:
        return JsonResponse({"ok": False, "error": "Некорректная цена"})
    stock.product.price = price
    stock.product.save(update_fields=["price"])
    return JsonResponse({"ok": True, "price": str(price)})


# ── ORDERS ────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def shop_orders(request, branch_id):
    branch = get_object_or_404(StoreBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:shop_home")

    status_filter = request.GET.get("status", "")
    qs = StoreOrder.objects.filter(branch=branch).prefetch_related("items__product")
    if status_filter:
        qs = qs.filter(status=status_filter)
    orders = qs.order_by("-created_at")[:100]

    return render(request, "dashboard/shops/orders.html", {
        "branch": branch,
        "store": branch.store,
        "orders": orders,
        "status_filter": status_filter,
        "status_choices": StoreOrder.Status.choices,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def shop_order_status(request, order_id):
    order = get_object_or_404(StoreOrder, id=order_id)
    if not _has_branch_access(request.user, order.branch):
        return redirect("dashboard:shop_home")
    new_status = request.POST.get("status")
    if new_status in dict(StoreOrder.Status.choices):
        order.status = new_status
        order.save(update_fields=["status"])
    return redirect("dashboard:shop_orders", branch_id=order.branch_id)
