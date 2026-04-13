from decimal import Decimal, InvalidOperation
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db.models import Sum, Count, Q, Max
from django.db import models as _models

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

    stocks = list(
        StoreStock.objects
        .filter(branch=branch)
        .select_related("product", "product__category")
        .order_by("product__category__sort_order", "product__id")
    )
    categories = list(branch.store.categories.filter(is_active=True).order_by("sort_order", "id"))

    # Группируем по категориям (включая пустые!)
    stock_map = {}
    for s in stocks:
        cid = s.product.category_id or 0
        stock_map.setdefault(cid, []).append(s)

    cat_sections = [
        {"cat": cat, "stocks": stock_map.get(cat.id, [])}
        for cat in categories
    ]
    uncat_stocks = stock_map.get(0, [])

    return render(request, "dashboard/shops/product_list.html", {
        "branch":       branch,
        "store":        branch.store,
        "stocks":       stocks,
        "categories":   categories,
        "cat_sections": cat_sections,
        "uncat_stocks": uncat_stocks,
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


# ── PRODUCT ADD / EDIT / DELETE / TOGGLE ─────────────────────────────────────

@require_POST
@login_required(login_url=LOGIN_URL)
def shop_product_add(request, branch_id):
    branch = get_object_or_404(StoreBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return JsonResponse({"ok": False}, status=403)

    name_ru = request.POST.get("name_ru", "").strip()
    if not name_ru:
        return JsonResponse({"ok": False, "error": "Укажите название товара"})

    category_id = request.POST.get("category_id") or None
    category = None
    if category_id:
        try:
            category = StoreCategory.objects.get(id=category_id, store=branch.store)
        except StoreCategory.DoesNotExist:
            pass

    product = StoreProduct(
        store=branch.store,
        category=category,
        name_ru=name_ru,
        name_ky=request.POST.get("name_ky", "").strip(),
        name_en=request.POST.get("name_en", "").strip(),
        price=_dec(request.POST.get("price", "0")),
        unit=request.POST.get("unit", "pcs"),
        is_active=True,
    )
    if request.FILES.get("photo"):
        product.photo = request.FILES["photo"]
    product.save()

    qty = _dec(request.POST.get("qty", "0"))
    stock = StoreStock.objects.create(branch=branch, product=product, qty=qty)

    return JsonResponse({
        "ok": True,
        "stock_id": stock.id,
        "product_id": product.id,
        "name_ru": product.name_ru,
        "name_ky": product.name_ky,
        "name_en": product.name_en,
        "price": str(product.price),
        "qty": str(stock.qty),
        "unit": product.unit,
        "unit_display": product.get_unit_display(),
        "photo_url": product.photo.url if product.photo else "",
        "is_active": product.is_active,
        "category_id": category.id if category else 0,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def shop_product_edit(request, stock_id):
    stock = get_object_or_404(StoreStock, id=stock_id)
    if not _has_branch_access(request.user, stock.branch):
        return JsonResponse({"ok": False}, status=403)

    product = stock.product
    name_ru = request.POST.get("name_ru", "").strip()
    if name_ru:
        product.name_ru = name_ru
    product.name_ky = request.POST.get("name_ky", "").strip()
    product.name_en = request.POST.get("name_en", "").strip()
    product.price = _dec(request.POST.get("price", str(product.price)))
    product.unit = request.POST.get("unit", product.unit)

    category_id = request.POST.get("category_id") or None
    if category_id:
        try:
            product.category = StoreCategory.objects.get(id=category_id, store=stock.branch.store)
        except StoreCategory.DoesNotExist:
            product.category = None
    else:
        product.category = None

    if request.FILES.get("photo"):
        product.photo = request.FILES["photo"]
    product.save()

    stock.qty = _dec(request.POST.get("qty", str(stock.qty)))
    stock.save(update_fields=["qty"])

    return JsonResponse({
        "ok": True,
        "name_ru": product.name_ru,
        "name_ky": product.name_ky,
        "name_en": product.name_en,
        "price": str(product.price),
        "qty": str(stock.qty),
        "unit_display": product.get_unit_display(),
        "photo_url": product.photo.url if product.photo else "",
        "category_id": product.category_id or 0,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def shop_product_delete(request, stock_id):
    stock = get_object_or_404(StoreStock, id=stock_id)
    if not _has_branch_access(request.user, stock.branch):
        return JsonResponse({"ok": False}, status=403)
    try:
        stock.product.delete()
    except Exception:
        return JsonResponse({"ok": False, "error": "Товар используется в заказах и не может быть удалён"})
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url=LOGIN_URL)
def shop_product_toggle(request, stock_id):
    stock = get_object_or_404(StoreStock, id=stock_id)
    if not _has_branch_access(request.user, stock.branch):
        return JsonResponse({"ok": False}, status=403)
    p = stock.product
    p.is_active = not p.is_active
    p.save(update_fields=["is_active"])
    return JsonResponse({"ok": True, "is_active": p.is_active})


# ── CATEGORY ADD / RENAME / DELETE ────────────────────────────────────────────

@require_POST
@login_required(login_url=LOGIN_URL)
def shop_category_add(request, branch_id):
    branch = get_object_or_404(StoreBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return JsonResponse({"ok": False}, status=403)
    name = request.POST.get("name_ru", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Укажите название категории"})
    max_order = branch.store.categories.aggregate(m=Max("sort_order"))["m"] or 0
    cat = StoreCategory.objects.create(
        store=branch.store,
        name_ru=name,
        sort_order=max_order + 10,
        is_active=True,
    )
    return JsonResponse({"ok": True, "id": cat.id, "name_ru": cat.name_ru})


@require_POST
@login_required(login_url=LOGIN_URL)
def shop_category_rename(request, category_id):
    cat = get_object_or_404(StoreCategory, id=category_id)
    if not _has_store_access(request.user, cat.store):
        return JsonResponse({"ok": False}, status=403)
    name = request.POST.get("name_ru", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Название не может быть пустым"})
    cat.name_ru = name
    cat.save(update_fields=["name_ru"])
    return JsonResponse({"ok": True, "name_ru": cat.name_ru})


@require_POST
@login_required(login_url=LOGIN_URL)
def shop_category_delete(request, category_id):
    cat = get_object_or_404(StoreCategory, id=category_id)
    if not _has_store_access(request.user, cat.store):
        return JsonResponse({"ok": False}, status=403)
    cat.delete()   # StoreProduct.category = SET_NULL, товары остаются
    return JsonResponse({"ok": True})


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
