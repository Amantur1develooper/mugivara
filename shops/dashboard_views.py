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

def _fmt(value):
    """Decimal → int если целое, иначе float без лишних нулей."""
    try:
        d = Decimal(str(value))
        return int(d) if d == d.to_integral_value() else float(d.normalize())
    except Exception:
        return value

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

    from django.db.models import Count as _Count, Q as _Q

    data = []
    for store in stores:
        branches_qs = store.branches.filter(is_active=True).order_by("name_ru")
        branches_qs = branches_qs.annotate(
            total_products=_Count("stocks", distinct=True),
            out_of_stock=_Count("stocks", filter=_Q(stocks__qty=0), distinct=True),
            low_stock=_Count(
                "stocks",
                filter=_Q(stocks__qty__gt=0, stocks__qty__lte=3),
                distinct=True,
            ),
        )
        branches = list(branches_qs)
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
        store.youtube_url = request.POST.get("youtube_url", "").strip()
        store.order_phone = request.POST.get("order_phone", "").strip()
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
        branch.phone2           = request.POST.get("phone2", "").strip()
        branch.map_url          = request.POST.get("map_url", "").strip()
        branch.city             = request.POST.get("city", branch.city).strip()
        lat_raw = request.POST.get("lat", "").strip()
        lon_raw = request.POST.get("lon", "").strip()
        branch.lat = lat_raw if lat_raw else None
        branch.lon = lon_raw if lon_raw else None
        branch.is_active        = request.POST.get("is_active") == "on"
        branch.delivery_enabled = request.POST.get("delivery_enabled") == "on"
        branch.delivery_fee     = _dec(request.POST.get("delivery_fee"))
        branch.min_order_amount = _dec(request.POST.get("min_order_amount"))
        # часы работы
        branch.is_open_24h = request.POST.get("is_open_24h") == "on"
        ot = request.POST.get("open_time", "").strip()
        ct = request.POST.get("close_time", "").strip()
        branch.open_time  = ot or None
        branch.close_time = ct or None
        work_days_list = request.POST.getlist("work_days")
        branch.work_days = ",".join(work_days_list)
        if request.FILES.get("cover_photo"):
            branch.cover_photo = request.FILES["cover_photo"]
        branch.save()
        messages.success(request, "Настройки филиала сохранены")
        return redirect("dashboard:shop_branch_edit", branch_id=branch.id)

    work_days_list = branch.work_days.split(",") if branch.work_days else ["0","1","2","3","4","5","6"]
    return render(request, "dashboard/shops/branch_edit.html", {
        "branch": branch, "store": branch.store,
        "work_days_list": work_days_list,
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
    return JsonResponse({"ok": True, "qty": _fmt(stock.qty)})


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
    return JsonResponse({"ok": True, "price": _fmt(price)})


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
        description_ru=request.POST.get("description_ru", "").strip(),
        price=_dec(request.POST.get("price", "0")),
        unit=request.POST.get("unit", "pcs"),
        barcode=request.POST.get("barcode", "").strip(),
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
        "price": _fmt(product.price),
        "qty": _fmt(stock.qty),
        "unit": product.unit,
        "unit_display": product.get_unit_display(),
        "photo_url": product.photo.url if product.photo else "",
        "is_active": product.is_active,
        "category_id": category.id if category else 0,
        "barcode": product.barcode,
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
    product.description_ru = request.POST.get("description_ru", product.description_ru).strip()
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

    product.barcode = request.POST.get("barcode", "").strip()
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
        "price": _fmt(product.price),
        "qty": _fmt(stock.qty),
        "unit_display": product.get_unit_display(),
        "photo_url": product.photo.url if product.photo else "",
        "category_id": product.category_id or 0,
        "barcode": product.barcode,
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


# ── CATEGORY LIST PAGE ───────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def shop_category_list(request, branch_id):
    branch = get_object_or_404(StoreBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:shop_home")
    categories = branch.store.categories.order_by("sort_order", "id")
    # product count per category
    from django.db.models import Count
    counts = (
        StoreStock.objects
        .filter(branch=branch, product__is_active=True)
        .values("product__category_id")
        .annotate(n=Count("id"))
    )
    count_map = {r["product__category_id"]: r["n"] for r in counts}
    cats_with_count = [(cat, count_map.get(cat.id, 0)) for cat in categories]
    return render(request, "dashboard/shops/category_list.html", {
        "branch": branch,
        "store": branch.store,
        "cats_with_count": cats_with_count,
    })


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


@require_POST
@login_required(login_url=LOGIN_URL)
def shop_category_reorder(request, branch_id):
    """Принимает order=id1,id2,id3 и обновляет sort_order категорий."""
    branch = get_object_or_404(StoreBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return JsonResponse({"ok": False}, status=403)
    ids_raw = request.POST.get("order", "")
    try:
        ids = [int(x) for x in ids_raw.split(",") if x.strip()]
    except ValueError:
        return JsonResponse({"ok": False, "error": "bad ids"})
    store = branch.store
    for i, cat_id in enumerate(ids):
        StoreCategory.objects.filter(id=cat_id, store=store).update(sort_order=i * 10)
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


# ── POS ───────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def shop_pos(request, branch_id):
    branch = get_object_or_404(StoreBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:shop_home")

    categories = list(branch.store.categories.filter(is_active=True).order_by("sort_order", "id"))
    stocks = (
        StoreStock.objects
        .filter(branch=branch, product__is_active=True)
        .select_related("product", "product__category")
        .order_by("product__category__sort_order", "product__id")
    )
    # Live online orders (NEW / CONFIRMED)
    live_orders = (
        StoreOrder.objects
        .filter(branch=branch, status__in=[StoreOrder.Status.NEW, StoreOrder.Status.CONFIRMED])
        .prefetch_related("items__product")
        .order_by("created_at")
    )
    return render(request, "dashboard/shops/pos.html", {
        "branch":      branch,
        "store":       branch.store,
        "categories":  categories,
        "stocks":      stocks,
        "live_orders": live_orders,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def shop_pos_order_create(request, branch_id):
    import json as _j
    branch = get_object_or_404(StoreBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return JsonResponse({"ok": False}, status=403)

    try:
        data = _j.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "error": "bad json"}, status=400)

    items_data     = data.get("items", [])
    payment_method = data.get("payment", "cash")
    comment        = (data.get("comment") or "").strip()

    if not items_data:
        return JsonResponse({"ok": False, "error": "Нет позиций"}, status=400)

    order = StoreOrder.objects.create(
        branch=branch,
        order_type=StoreOrder.Type.PICKUP,
        mode=StoreOrder.Mode.IN_STORE,
        status=StoreOrder.Status.DONE,
        payment_method=payment_method,
        comment=comment,
        phone="-",
    )

    subtotal = Decimal("0")
    for it in items_data:
        try:
            stock = StoreStock.objects.select_related("product").get(
                id=int(it["stock_id"]), branch=branch, product__is_active=True
            )
            qty = max(Decimal("1"), Decimal(str(it.get("qty", 1))))
            price = stock.product.price
            line = price * qty
            StoreOrderItem.objects.create(
                order=order, product=stock.product,
                qty=qty, unit=stock.product.unit, price=price, line_total=line,
            )
            subtotal += line
            # Decrement stock (don't go below 0)
            stock.qty = max(Decimal("0"), stock.qty - qty)
            stock.save(update_fields=["qty"])
        except Exception:
            continue

    order.subtotal = subtotal
    order.total    = subtotal
    order.save(update_fields=["subtotal", "total"])

    return JsonResponse({"ok": True, "order_id": order.id, "total": str(subtotal)})


@login_required(login_url=LOGIN_URL)
def shop_pos_live_orders(request, branch_id):
    branch = get_object_or_404(StoreBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return JsonResponse({"ok": False}, status=403)

    orders = (
        StoreOrder.objects
        .filter(branch=branch, status__in=[StoreOrder.Status.NEW, StoreOrder.Status.CONFIRMED])
        .prefetch_related("items__product")
        .order_by("created_at")
    )
    result = []
    for o in orders:
        result.append({
            "id":      o.id,
            "status":  o.status,
            "type":    o.order_type,
            "name":    o.name,
            "phone":   o.phone,
            "address": o.address,
            "total":   str(o.total),
            "payment": o.payment_method,
            "comment": o.comment,
            "created": o.created_at.strftime("%H:%M"),
            "items": [
                {"name": oi.product.name_ru, "qty": str(oi.qty), "line": str(oi.line_total)}
                for oi in o.items.all()
            ],
        })
    return JsonResponse({"ok": True, "orders": result})


@require_POST
@login_required(login_url=LOGIN_URL)
def shop_pos_order_status(request, order_id):
    order = get_object_or_404(StoreOrder, id=order_id)
    if not _has_branch_access(request.user, order.branch):
        return JsonResponse({"ok": False}, status=403)
    new_status = request.POST.get("status")
    if new_status in dict(StoreOrder.Status.choices):
        order.status = new_status
        order.save(update_fields=["status"])
    return JsonResponse({"ok": True, "status": order.status})


@login_required(login_url=LOGIN_URL)
def shop_pos_receipt(request, order_id):
    order = get_object_or_404(
        StoreOrder.objects.prefetch_related("items__product").select_related("branch__store"),
        id=order_id,
    )
    if not _has_branch_access(request.user, order.branch):
        return redirect("dashboard:shop_home")
    return render(request, "dashboard/shops/receipt.html", {"order": order})


@login_required(login_url=LOGIN_URL)
def shop_pos_history(request, branch_id):
    from datetime import date as _date, datetime as _dt
    branch = get_object_or_404(StoreBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:shop_home")

    today = _date.today()
    date_str = request.GET.get("date", str(today))
    try:
        sel_date = _dt.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        sel_date = today

    orders = (
        StoreOrder.objects
        .filter(branch=branch, created_at__date=sel_date)
        .prefetch_related("items__product")
        .order_by("-created_at")
    )

    return render(request, "dashboard/shops/pos_history.html", {
        "branch":   branch,
        "store":    branch.store,
        "orders":   orders,
        "sel_date": sel_date,
        "today":    today,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def shop_pos_order_cancel(request, order_id):
    order = get_object_or_404(StoreOrder, id=order_id)
    if not _has_branch_access(request.user, order.branch):
        return JsonResponse({"ok": False}, status=403)

    if order.status == StoreOrder.Status.CANCELED:
        return JsonResponse({"ok": False, "error": "Уже отменён"})

    # Restore stock for done (closed) POS orders
    if order.status == StoreOrder.Status.DONE:
        for oi in order.items.select_related("product").all():
            try:
                stock = StoreStock.objects.get(branch=order.branch, product=oi.product)
                stock.qty += oi.qty
                stock.save(update_fields=["qty"])
            except StoreStock.DoesNotExist:
                pass

    order.status = StoreOrder.Status.CANCELED
    order.save(update_fields=["status"])

    return JsonResponse({"ok": True})


# ── BRANCH DUPLICATE ─────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def shop_branch_duplicate(request, branch_id):
    """
    Только для суперпользователей.
    GET  — страница подтверждения с выбором целевого магазина.
    POST — создаёт полную копию филиала: новые категории, товары (название,
           описание, цена, фото) и остатки. Всё автономно в БД.
    """
    branch = get_object_or_404(StoreBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:shop_home")

    all_stores = _user_stores(request.user).order_by("name_ru") if not request.user.is_superuser else Store.objects.all().order_by("name_ru")

    if request.method == "GET":
        return render(request, "dashboard/shops/branch_duplicate.html", {
            "branch": branch,
            "store": branch.store,
            "all_stores": all_stores,
        })

    # POST — выполняем копирование
    target_store_id = request.POST.get("target_store_id")
    new_name = request.POST.get("new_name", "").strip() or f"{branch.name_ru} (копия)"

    try:
        target_store = Store.objects.get(pk=target_store_id)
    except (Store.DoesNotExist, TypeError, ValueError):
        target_store = branch.store

    if not _has_store_access(request.user, target_store):
        messages.error(request, "Нет доступа к выбранному магазину")
        return redirect("dashboard:shop_branch_duplicate", branch_id=branch.id)

    # 1. Новый филиал
    new_branch = StoreBranch.objects.create(
        store=target_store,
        name_ru=new_name,
        city=branch.city,
        address=branch.address,
        phone=branch.phone,
        phone2=branch.phone2,
        map_url=branch.map_url,
        lat=branch.lat,
        lon=branch.lon,
        delivery_enabled=branch.delivery_enabled,
        delivery_fee=branch.delivery_fee,
        min_order_amount=branch.min_order_amount,
        tg_group_chat_id=branch.tg_group_chat_id,
        tg_thread_id=branch.tg_thread_id,
        tg_manager_chat_id=branch.tg_manager_chat_id,
        is_active=False,
    )

    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    import os

    def _copy_file(src_field, dest_field):
        """Надёжно копирует файл через default_storage (работает с любым бэкендом)."""
        if not src_field:
            return
        try:
            fname = os.path.basename(src_field.name)
            with default_storage.open(src_field.name, "rb") as f:
                dest_field.save(fname, ContentFile(f.read()), save=True)
        except Exception:
            pass

    # 2. Копируем обложку филиала
    if branch.cover_photo:
        _copy_file(branch.cover_photo, new_branch.cover_photo)

    # 3. Полностью дублируем категории, товары и остатки
    stocks = StoreStock.objects.filter(branch=branch).select_related(
        "product", "product__category"
    )
    cat_map = {}  # old StoreCategory.pk → new StoreCategory

    for stock in stocks:
        old_product = stock.product
        old_cat = old_product.category

        # Категория — переиспользуем существующую или создаём новую
        if old_cat:
            if old_cat.pk not in cat_map:
                new_cat, _ = StoreCategory.objects.get_or_create(
                    store=target_store,
                    name_ru=old_cat.name_ru,
                    defaults={
                        "name_ky": old_cat.name_ky,
                        "name_en": old_cat.name_en,
                        "sort_order": old_cat.sort_order,
                        "is_active": old_cat.is_active,
                    },
                )
                cat_map[old_cat.pk] = new_cat
            new_cat = cat_map[old_cat.pk]
        else:
            new_cat = None

        # Товар — новая независимая запись со всеми полями
        new_product = StoreProduct.objects.create(
            store=target_store,
            category=new_cat,
            name_ru=old_product.name_ru,
            name_ky=old_product.name_ky,
            name_en=old_product.name_en,
            description_ru=old_product.description_ru,
            description_ky=old_product.description_ky,
            description_en=old_product.description_en,
            price=old_product.price,
            unit=old_product.unit,
            barcode=old_product.barcode,
            is_active=old_product.is_active,
        )

        # Фото товара — копируем через default_storage (не зависит от курсора файла)
        if old_product.photo:
            _copy_file(old_product.photo, new_product.photo)

        # Остаток на складе нового филиала
        StoreStock.objects.create(
            branch=new_branch,
            product=new_product,
            qty=stock.qty,
        )

    total = StoreStock.objects.filter(branch=new_branch).count()
    messages.success(
        request,
        f"Филиал «{new_branch.name_ru}» создан — скопировано {total} товаров. "
        "Откройте настройки и активируйте его когда будете готовы."
    )
    return redirect("dashboard:shop_branch_edit", branch_id=new_branch.id)


# ── STORE DUPLICATE (clone entire network) ───────────────────────────────────

@login_required(login_url=LOGIN_URL)
def shop_store_duplicate(request, store_id):
    """Только для суперпользователей. Клонирует весь магазин: все филиалы,
    категории, товары (с фото), остатки — полностью независимые записи в БД."""
    if not request.user.is_superuser:
        return redirect("dashboard:shop_home")

    source_store = get_object_or_404(Store, id=store_id)

    if request.method == "GET":
        branches = source_store.branches.prefetch_related(
            "stocks__product"
        ).order_by("name_ru")
        total_products = StoreStock.objects.filter(branch__store=source_store).count()
        return render(request, "dashboard/shops/store_duplicate.html", {
            "store": source_store,
            "branches": branches,
            "total_products": total_products,
        })

    # POST
    new_name = request.POST.get("new_name", "").strip() or f"{source_store.name_ru} (копия)"
    new_slug = request.POST.get("new_slug", "").strip()
    if not new_slug:
        from django.utils.text import slugify
        base = slugify(new_name)[:200]
        new_slug = base
        n = 1
        while Store.objects.filter(slug=new_slug).exists():
            new_slug = f"{base}-{n}"; n += 1

    if Store.objects.filter(slug=new_slug).exists():
        messages.error(request, f"Slug «{new_slug}» уже занят — выберите другой.")
        return redirect("dashboard:shop_store_duplicate", store_id=source_store.id)

    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    import os

    def _copy_file(src_field, dest_field):
        if not src_field:
            return
        try:
            fname = os.path.basename(src_field.name)
            with default_storage.open(src_field.name, "rb") as f:
                dest_field.save(fname, ContentFile(f.read()), save=True)
        except Exception:
            pass

    # 1. Новый магазин
    new_store = Store.objects.create(
        name_ru=new_name,
        slug=new_slug,
        about_ru=source_store.about_ru,
        youtube_url=source_store.youtube_url,
        instagram_url=source_store.instagram_url,
        instagram_url_2=source_store.instagram_url_2,
        order_phone=source_store.order_phone,
        is_active=False,
    )
    if source_store.logo:
        _copy_file(source_store.logo, new_store.logo)

    # 2. Добавляем членство суперпользователя
    StoreMembership.objects.get_or_create(user=request.user, store=new_store)

    branches_created = 0
    products_created = 0

    for branch in source_store.branches.all().order_by("id"):
        new_branch = StoreBranch.objects.create(
            store=new_store,
            name_ru=branch.name_ru,
            name_ky=branch.name_ky,
            name_en=branch.name_en,
            city=branch.city,
            address=branch.address,
            phone=branch.phone,
            phone2=branch.phone2,
            map_url=branch.map_url,
            lat=branch.lat,
            lon=branch.lon,
            delivery_enabled=branch.delivery_enabled,
            delivery_fee=branch.delivery_fee,
            min_order_amount=branch.min_order_amount,
            tg_group_chat_id=branch.tg_group_chat_id,
            tg_thread_id=branch.tg_thread_id,
            tg_manager_chat_id=branch.tg_manager_chat_id,
            is_active=False,
        )
        if branch.cover_photo:
            _copy_file(branch.cover_photo, new_branch.cover_photo)
        branches_created += 1

        stocks = StoreStock.objects.filter(branch=branch).select_related(
            "product", "product__category"
        )
        cat_map = {}

        for stock in stocks:
            old_product = stock.product
            old_cat = old_product.category

            if old_cat:
                if old_cat.pk not in cat_map:
                    new_cat = StoreCategory.objects.create(
                        store=new_store,
                        name_ru=old_cat.name_ru,
                        name_ky=old_cat.name_ky,
                        name_en=old_cat.name_en,
                        sort_order=old_cat.sort_order,
                        is_active=old_cat.is_active,
                    )
                    cat_map[old_cat.pk] = new_cat
                new_cat = cat_map[old_cat.pk]
            else:
                new_cat = None

            new_product = StoreProduct.objects.create(
                store=new_store,
                category=new_cat,
                name_ru=old_product.name_ru,
                name_ky=old_product.name_ky,
                name_en=old_product.name_en,
                description_ru=old_product.description_ru,
                description_ky=old_product.description_ky,
                description_en=old_product.description_en,
                price=old_product.price,
                unit=old_product.unit,
                barcode=old_product.barcode,
                is_active=old_product.is_active,
            )
            if old_product.photo:
                _copy_file(old_product.photo, new_product.photo)

            StoreStock.objects.create(
                branch=new_branch,
                product=new_product,
                qty=stock.qty,
            )
            products_created += 1

    messages.success(
        request,
        f"Сеть «{new_store.name_ru}» создана: {branches_created} филиал(ов), "
        f"{products_created} товаров. Активируйте магазин в настройках когда будете готовы."
    )
    return redirect("dashboard:shop_store_edit", store_id=new_store.id)


# ── BARCODE LOOKUP ────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def shop_barcode_lookup(request, branch_id):
    """GET ?barcode=XXX — ищет товар в магазине по штрих-коду."""
    branch = get_object_or_404(StoreBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return JsonResponse({"ok": False}, status=403)

    code = request.GET.get("barcode", "").strip()
    if not code:
        return JsonResponse({"ok": False, "error": "empty"})

    try:
        stock = StoreStock.objects.select_related("product").get(
            branch=branch, product__barcode=code
        )
        p = stock.product
        return JsonResponse({
            "ok": True,
            "found": True,
            "stock_id": stock.id,
            "product_id": p.id,
            "name_ru": p.name_ru,
            "price": _fmt(p.price),
            "qty": _fmt(stock.qty),
            "unit_display": p.get_unit_display(),
            "photo_url": p.photo.url if p.photo else "",
            "barcode": p.barcode,
        })
    except StoreStock.DoesNotExist:
        return JsonResponse({"ok": True, "found": False, "barcode": code})
