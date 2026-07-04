from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Sum, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    PrintBranch, PrintCategory, PrintCenter, PrintMembership,
    PrintOptionGroup, PrintOptionValue, PrintOrder, PrintProduct,
    PrintProductPhoto, PrintProductVariant, PrintPromoCode,
)

LOGIN_URL = "dashboard:login"


# ── helpers ────────────────────────────────────────────────────────────────

def _fmt(value):
    try:
        d = Decimal(str(value))
        return int(d) if d == d.to_integral_value() else float(d.normalize())
    except Exception:
        return value


def _dec(val, default="0"):
    try:
        return Decimal(val or default)
    except InvalidOperation:
        return Decimal(default)


def _user_centers(user):
    ids = PrintMembership.objects.filter(user=user).values_list("center_id", flat=True)
    return PrintCenter.objects.filter(id__in=ids)


def _has_center_access(user, center):
    if user.is_superuser:
        return True
    return PrintMembership.objects.filter(user=user, center=center).exists()


def _has_branch_access(user, branch):
    return _has_center_access(user, branch.center)


# ── HOME ─────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def printshop_home(request):
    if request.user.is_superuser:
        centers = PrintCenter.objects.all().prefetch_related("branches")
    else:
        centers = _user_centers(request.user).prefetch_related("branches")

    data = []
    for center in centers:
        branches = list(center.branches.order_by("name_ru"))
        product_count = center.products.count()
        new_orders = PrintOrder.objects.filter(
            branch__center=center, status=PrintOrder.Status.NEW
        ).count()
        data.append({
            "center": center, "branches": branches,
            "product_count": product_count, "new_orders": new_orders,
        })

    return render(request, "dashboard/printshop/home.html", {"data": data})


# ── CENTER EDIT ──────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def center_edit(request, center_id):
    center = get_object_or_404(PrintCenter, id=center_id)
    if not _has_center_access(request.user, center):
        return redirect("dashboard:printshop_home")

    if request.method == "POST":
        name = request.POST.get("name_ru", "").strip()
        if name:
            center.name_ru = name
        center.description_ru = request.POST.get("description_ru", "").strip()
        center.is_active = request.POST.get("is_active") == "on"
        if request.FILES.get("logo"):
            center.logo = request.FILES["logo"]
        center.save()
        messages.success(request, "Данные центра сохранены")
        return redirect("dashboard:printshop_center_edit", center_id=center.id)

    return render(request, "dashboard/printshop/center_edit.html", {"center": center})


# ── BRANCH EDIT ──────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def branch_edit(request, branch_id):
    branch = get_object_or_404(PrintBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:printshop_home")

    if request.method == "POST":
        branch.name_ru = request.POST.get("name_ru", branch.name_ru).strip()
        branch.address = request.POST.get("address", "").strip()
        branch.phone = request.POST.get("phone", "").strip()
        branch.whatsapp = request.POST.get("whatsapp", "").strip()
        branch.telegram = request.POST.get("telegram", "").strip()
        branch.taplink_url = request.POST.get("taplink_url", "").strip()
        branch.map_url = request.POST.get("map_url", "").strip()
        lat_raw = request.POST.get("lat", "").strip()
        lon_raw = request.POST.get("lon", "").strip()
        branch.lat = lat_raw or None
        branch.lon = lon_raw or None

        branch.delivery_enabled = request.POST.get("delivery_enabled") == "on"
        branch.min_order_amount = _dec(request.POST.get("min_order_amount"))
        free_delivery_raw = request.POST.get("free_delivery_from", "").strip()
        branch.free_delivery_from = _dec(free_delivery_raw) if free_delivery_raw else None
        branch.delivery_fee = _dec(request.POST.get("delivery_fee"))

        branch.tg_chat_id = request.POST.get("tg_chat_id", "").strip()
        tg_thread_raw = request.POST.get("tg_thread_id", "").strip()
        branch.tg_thread_id = int(tg_thread_raw) if tg_thread_raw.isdigit() else None

        branch.is_open_24h = request.POST.get("is_open_24h") == "on"
        ot = request.POST.get("open_time", "").strip()
        ct = request.POST.get("close_time", "").strip()
        branch.open_time = ot or None
        branch.close_time = ct or None
        branch.work_days = ",".join(request.POST.getlist("work_days"))

        branch.is_active = request.POST.get("is_active") == "on"

        if request.FILES.get("banner"):
            branch.banner = request.FILES["banner"]
        branch.save()
        messages.success(request, "Настройки филиала сохранены")
        return redirect("dashboard:printshop_branch_edit", branch_id=branch.id)

    work_days_list = branch.work_days.split(",") if branch.work_days else ["0", "1", "2", "3", "4", "5", "6"]
    return render(request, "dashboard/printshop/branch_edit.html", {
        "branch": branch, "center": branch.center, "work_days_list": work_days_list,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def branch_toggle(request, branch_id):
    branch = get_object_or_404(PrintBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:printshop_home")
    branch.is_active = not branch.is_active
    branch.save(update_fields=["is_active"])
    return redirect("dashboard:printshop_home")


# ── CATEGORIES ───────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def category_list(request, center_id):
    center = get_object_or_404(PrintCenter, id=center_id)
    if not _has_center_access(request.user, center):
        return redirect("dashboard:printshop_home")

    categories = center.categories.order_by("sort_order", "id")
    counts = (
        PrintProduct.objects.filter(center=center)
        .values("category_id").annotate(n=Count("id"))
    )
    count_map = {r["category_id"]: r["n"] for r in counts}
    cats_with_count = [(cat, count_map.get(cat.id, 0)) for cat in categories]

    return render(request, "dashboard/printshop/category_list.html", {
        "center": center, "cats_with_count": cats_with_count,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def category_add(request, center_id):
    center = get_object_or_404(PrintCenter, id=center_id)
    if not _has_center_access(request.user, center):
        return JsonResponse({"ok": False}, status=403)
    name = request.POST.get("name_ru", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Укажите название категории"})
    max_order = center.categories.aggregate(m=Max("sort_order"))["m"] or 0
    cat = PrintCategory.objects.create(center=center, name_ru=name, sort_order=max_order + 10, is_active=True)
    return JsonResponse({"ok": True, "id": cat.id, "name_ru": cat.name_ru})


@require_POST
@login_required(login_url=LOGIN_URL)
def category_rename(request, category_id):
    cat = get_object_or_404(PrintCategory, id=category_id)
    if not _has_center_access(request.user, cat.center):
        return JsonResponse({"ok": False}, status=403)
    name = request.POST.get("name_ru", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Название не может быть пустым"})
    cat.name_ru = name
    cat.save(update_fields=["name_ru"])
    return JsonResponse({"ok": True, "name_ru": cat.name_ru})


@require_POST
@login_required(login_url=LOGIN_URL)
def category_delete(request, category_id):
    cat = get_object_or_404(PrintCategory, id=category_id)
    if not _has_center_access(request.user, cat.center):
        return JsonResponse({"ok": False}, status=403)
    cat.delete()
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url=LOGIN_URL)
def category_reorder(request, center_id):
    center = get_object_or_404(PrintCenter, id=center_id)
    if not _has_center_access(request.user, center):
        return JsonResponse({"ok": False}, status=403)
    ids_raw = request.POST.get("order", "")
    try:
        ids = [int(x) for x in ids_raw.split(",") if x.strip()]
    except ValueError:
        return JsonResponse({"ok": False, "error": "bad ids"})
    for i, cat_id in enumerate(ids):
        PrintCategory.objects.filter(id=cat_id, center=center).update(sort_order=i * 10)
    return JsonResponse({"ok": True})


# ── PRODUCTS ─────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def product_list(request, center_id):
    center = get_object_or_404(PrintCenter, id=center_id)
    if not _has_center_access(request.user, center):
        return redirect("dashboard:printshop_home")

    products = list(
        center.products.select_related("category").order_by("category__sort_order", "sort_order", "id")
    )
    categories = list(center.categories.order_by("sort_order", "id"))

    cat_map = {}
    for p in products:
        cat_map.setdefault(p.category_id or 0, []).append(p)

    cat_sections = [{"cat": cat, "products": cat_map.get(cat.id, [])} for cat in categories]
    uncat_products = cat_map.get(0, [])

    return render(request, "dashboard/printshop/product_list.html", {
        "center": center, "categories": categories,
        "cat_sections": cat_sections, "uncat_products": uncat_products,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def product_add(request, center_id):
    center = get_object_or_404(PrintCenter, id=center_id)
    if not _has_center_access(request.user, center):
        return redirect("dashboard:printshop_home")

    name_ru = request.POST.get("name_ru", "").strip()
    if not name_ru:
        messages.error(request, "Укажите название товара")
        return redirect("dashboard:printshop_product_list", center_id=center.id)

    category_id = request.POST.get("category_id") or None
    category = PrintCategory.objects.filter(id=category_id, center=center).first() if category_id else None

    product = PrintProduct.objects.create(
        center=center, category=category, name_ru=name_ru,
        base_price=_dec(request.POST.get("base_price", "0")),
        is_available=True,
    )
    return redirect("dashboard:printshop_product_detail", product_id=product.id)


@login_required(login_url=LOGIN_URL)
def product_detail(request, product_id):
    product = get_object_or_404(PrintProduct, id=product_id)
    if not _has_center_access(request.user, product.center):
        return redirect("dashboard:printshop_home")

    if request.method == "POST":
        name_ru = request.POST.get("name_ru", "").strip()
        if name_ru:
            product.name_ru = name_ru
        product.description_ru = request.POST.get("description_ru", "").strip()
        product.sku = request.POST.get("sku", "").strip()
        product.base_price = _dec(request.POST.get("base_price", str(product.base_price)))

        category_id = request.POST.get("category_id") or None
        product.category = (
            PrintCategory.objects.filter(id=category_id, center=product.center).first() if category_id else None
        )

        product.is_available = request.POST.get("is_available") == "on"
        product.is_new = request.POST.get("is_new") == "on"
        product.is_popular = request.POST.get("is_popular") == "on"
        product.is_promo = request.POST.get("is_promo") == "on"

        if request.FILES.get("main_photo"):
            product.main_photo = request.FILES["main_photo"]
        product.save()
        messages.success(request, "Товар сохранён")
        return redirect("dashboard:printshop_product_detail", product_id=product.id)

    categories = product.center.categories.order_by("sort_order", "id")
    photos = product.photos.order_by("sort_order", "id")
    variants = product.variants.order_by("sort_order", "id")
    option_groups = product.option_groups.prefetch_related("values").order_by("sort_order", "id")

    return render(request, "dashboard/printshop/product_detail.html", {
        "product": product, "center": product.center, "categories": categories,
        "photos": photos, "variants": variants, "option_groups": option_groups,
        "photos_left": max(0, 5 - photos.count()),
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def product_toggle(request, product_id):
    product = get_object_or_404(PrintProduct, id=product_id)
    if not _has_center_access(request.user, product.center):
        return JsonResponse({"ok": False}, status=403)
    field = request.POST.get("field", "is_available")
    if field not in ("is_available", "is_new", "is_popular", "is_promo"):
        return JsonResponse({"ok": False, "error": "bad field"})
    setattr(product, field, not getattr(product, field))
    product.save(update_fields=[field])
    return JsonResponse({"ok": True, "field": field, "value": getattr(product, field)})


@require_POST
@login_required(login_url=LOGIN_URL)
def product_delete(request, product_id):
    product = get_object_or_404(PrintProduct, id=product_id)
    if not _has_center_access(request.user, product.center):
        return redirect("dashboard:printshop_home")
    center_id = product.center_id
    try:
        product.delete()
        messages.success(request, "Товар удалён")
    except Exception:
        messages.error(request, "Товар используется в заказах и не может быть удалён")
    return redirect("dashboard:printshop_product_list", center_id=center_id)


@require_POST
@login_required(login_url=LOGIN_URL)
def product_reorder(request, center_id):
    center = get_object_or_404(PrintCenter, id=center_id)
    if not _has_center_access(request.user, center):
        return JsonResponse({"ok": False}, status=403)
    ids_raw = request.POST.get("order", "")
    try:
        ids = [int(x) for x in ids_raw.split(",") if x.strip()]
    except ValueError:
        return JsonResponse({"ok": False, "error": "bad ids"})
    for i, pid in enumerate(ids):
        PrintProduct.objects.filter(id=pid, center=center).update(sort_order=i * 10)
    return JsonResponse({"ok": True})


# ── PRODUCT PHOTOS (gallery, max 5) ───────────────────────────────────────

@require_POST
@login_required(login_url=LOGIN_URL)
def photo_upload(request, product_id):
    product = get_object_or_404(PrintProduct, id=product_id)
    if not _has_center_access(request.user, product.center):
        return redirect("dashboard:printshop_home")

    if product.photos.count() >= 5:
        messages.error(request, "У товара уже 5 фото — максимум для галереи")
        return redirect("dashboard:printshop_product_detail", product_id=product.id)

    photo_file = request.FILES.get("photo")
    if not photo_file:
        messages.error(request, "Выберите файл")
        return redirect("dashboard:printshop_product_detail", product_id=product.id)

    max_order = product.photos.aggregate(m=Max("sort_order"))["m"] or 0
    PrintProductPhoto.objects.create(product=product, photo=photo_file, sort_order=max_order + 10)
    messages.success(request, "Фото добавлено")
    return redirect("dashboard:printshop_product_detail", product_id=product.id)


@require_POST
@login_required(login_url=LOGIN_URL)
def photo_delete(request, photo_id):
    photo = get_object_or_404(PrintProductPhoto, id=photo_id)
    if not _has_center_access(request.user, photo.product.center):
        return redirect("dashboard:printshop_home")
    product_id = photo.product_id
    photo.delete()
    return redirect("dashboard:printshop_product_detail", product_id=product_id)


# ── VARIANTS ─────────────────────────────────────────────────────────────

@require_POST
@login_required(login_url=LOGIN_URL)
def variant_add(request, product_id):
    product = get_object_or_404(PrintProduct, id=product_id)
    if not _has_center_access(request.user, product.center):
        return redirect("dashboard:printshop_home")
    label = request.POST.get("label", "").strip()
    if not label:
        messages.error(request, "Укажите название варианта")
        return redirect("dashboard:printshop_product_detail", product_id=product.id)
    max_order = product.variants.aggregate(m=Max("sort_order"))["m"] or 0
    is_default = request.POST.get("is_default") == "on"
    if is_default:
        product.variants.update(is_default=False)
    PrintProductVariant.objects.create(
        product=product, label=label, price=_dec(request.POST.get("price", "0")),
        is_default=is_default, sort_order=max_order + 10,
    )
    return redirect("dashboard:printshop_product_detail", product_id=product.id)


@require_POST
@login_required(login_url=LOGIN_URL)
def variant_edit(request, variant_id):
    variant = get_object_or_404(PrintProductVariant, id=variant_id)
    if not _has_center_access(request.user, variant.product.center):
        return redirect("dashboard:printshop_home")
    label = request.POST.get("label", "").strip()
    if label:
        variant.label = label
    variant.price = _dec(request.POST.get("price", str(variant.price)))
    variant.is_active = request.POST.get("is_active") == "on"
    is_default = request.POST.get("is_default") == "on"
    if is_default:
        variant.product.variants.exclude(id=variant.id).update(is_default=False)
    variant.is_default = is_default
    variant.save()
    return redirect("dashboard:printshop_product_detail", product_id=variant.product_id)


@require_POST
@login_required(login_url=LOGIN_URL)
def variant_delete(request, variant_id):
    variant = get_object_or_404(PrintProductVariant, id=variant_id)
    if not _has_center_access(request.user, variant.product.center):
        return redirect("dashboard:printshop_home")
    product_id = variant.product_id
    variant.delete()
    return redirect("dashboard:printshop_product_detail", product_id=product_id)


# ── OPTION GROUPS / VALUES ─────────────────────────────────────────────────

@require_POST
@login_required(login_url=LOGIN_URL)
def option_group_add(request, product_id):
    product = get_object_or_404(PrintProduct, id=product_id)
    if not _has_center_access(request.user, product.center):
        return redirect("dashboard:printshop_home")
    name = request.POST.get("name", "").strip()
    if not name:
        messages.error(request, "Укажите название группы")
        return redirect("dashboard:printshop_product_detail", product_id=product.id)
    max_order = product.option_groups.aggregate(m=Max("sort_order"))["m"] or 0
    PrintOptionGroup.objects.create(
        product=product, name=name,
        is_required=request.POST.get("is_required") == "on",
        allow_multiple=request.POST.get("allow_multiple") == "on",
        sort_order=max_order + 10,
    )
    return redirect("dashboard:printshop_product_detail", product_id=product.id)


@require_POST
@login_required(login_url=LOGIN_URL)
def option_group_delete(request, group_id):
    group = get_object_or_404(PrintOptionGroup, id=group_id)
    if not _has_center_access(request.user, group.product.center):
        return redirect("dashboard:printshop_home")
    product_id = group.product_id
    group.delete()
    return redirect("dashboard:printshop_product_detail", product_id=product_id)


@require_POST
@login_required(login_url=LOGIN_URL)
def option_value_add(request, group_id):
    group = get_object_or_404(PrintOptionGroup, id=group_id)
    if not _has_center_access(request.user, group.product.center):
        return redirect("dashboard:printshop_home")
    label = request.POST.get("label", "").strip()
    if not label:
        messages.error(request, "Укажите значение")
        return redirect("dashboard:printshop_product_detail", product_id=group.product_id)
    max_order = group.values.aggregate(m=Max("sort_order"))["m"] or 0
    PrintOptionValue.objects.create(
        group=group, label=label, price_delta=_dec(request.POST.get("price_delta", "0")),
        is_default=request.POST.get("is_default") == "on", sort_order=max_order + 10,
    )
    return redirect("dashboard:printshop_product_detail", product_id=group.product_id)


@require_POST
@login_required(login_url=LOGIN_URL)
def option_value_delete(request, value_id):
    value = get_object_or_404(PrintOptionValue, id=value_id)
    if not _has_center_access(request.user, value.group.product.center):
        return redirect("dashboard:printshop_home")
    product_id = value.group.product_id
    value.delete()
    return redirect("dashboard:printshop_product_detail", product_id=product_id)


# ── ORDERS ───────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def order_list(request, branch_id):
    branch = get_object_or_404(PrintBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:printshop_home")

    status_filter = request.GET.get("status", "")
    qs = PrintOrder.objects.filter(branch=branch).prefetch_related("items")
    if status_filter:
        qs = qs.filter(status=status_filter)
    orders = qs.order_by("-created_at")[:100]

    return render(request, "dashboard/printshop/orders.html", {
        "branch": branch, "center": branch.center, "orders": orders,
        "status_filter": status_filter, "status_choices": PrintOrder.Status.choices,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def order_status(request, order_id):
    order = get_object_or_404(PrintOrder, id=order_id)
    if not _has_branch_access(request.user, order.branch):
        return redirect("dashboard:printshop_home")
    new_status = request.POST.get("status")
    if new_status in dict(PrintOrder.Status.choices):
        order.status = new_status
        order.save(update_fields=["status"])
    return redirect("dashboard:printshop_order_list", branch_id=order.branch_id)


# ── PROMO CODES ──────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def promo_list(request, branch_id):
    branch = get_object_or_404(PrintBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:printshop_home")

    if request.method == "POST":
        code = request.POST.get("code", "").strip().upper()
        discount_type = request.POST.get("discount_type", "")
        discount_value = _dec(request.POST.get("discount_value"))
        valid_until = request.POST.get("valid_until") or None
        max_uses = int(request.POST.get("max_uses") or 0)

        if not code:
            messages.error(request, "Введите промокод")
        elif PrintPromoCode.objects.filter(branch=branch, code=code).exists():
            messages.error(request, f"Промокод «{code}» уже существует")
        else:
            PrintPromoCode.objects.create(
                branch=branch, code=code, discount_type=discount_type,
                discount_value=discount_value, valid_until=valid_until,
                max_uses=max_uses, is_active=True,
            )
            messages.success(request, f"Промокод «{code}» создан")
        return redirect("dashboard:printshop_promo_list", branch_id=branch.id)

    promos = PrintPromoCode.objects.filter(branch=branch).order_by("-created_at")
    return render(request, "dashboard/printshop/promos.html", {
        "branch": branch, "center": branch.center, "promos": promos,
        "discount_types": PrintPromoCode.DiscountType.choices,
        "today": timezone.localdate(),
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def promo_toggle(request, promo_id):
    promo = get_object_or_404(PrintPromoCode, id=promo_id)
    if not _has_branch_access(request.user, promo.branch):
        return redirect("dashboard:printshop_home")
    promo.is_active = not promo.is_active
    promo.save(update_fields=["is_active", "updated_at"])
    return redirect("dashboard:printshop_promo_list", branch_id=promo.branch_id)


@require_POST
@login_required(login_url=LOGIN_URL)
def promo_delete(request, promo_id):
    promo = get_object_or_404(PrintPromoCode, id=promo_id)
    if not _has_branch_access(request.user, promo.branch):
        return redirect("dashboard:printshop_home")
    branch_id = promo.branch_id
    promo.delete()
    messages.success(request, "Промокод удалён")
    return redirect("dashboard:printshop_promo_list", branch_id=branch_id)


# ── STATS ────────────────────────────────────────────────────────────────

# status -> (label, color) — same palette used in orders.html status badges
_STATUS_COLORS = {
    PrintOrder.Status.NEW: ("Новый", "#FF4D1C"),
    PrintOrder.Status.CONFIRMED: ("Подтвержден", "#2563EB"),
    PrintOrder.Status.IN_PROGRESS: ("В работе", "#7C3AED"),
    PrintOrder.Status.DONE: ("Завершен", "#00B896"),
    PrintOrder.Status.CANCELED: ("Отменен", "#8B96A8"),
}


@login_required(login_url=LOGIN_URL)
def stats(request, center_id):
    import json as _json
    from datetime import timedelta
    from django.db.models.functions import TruncDate

    center = get_object_or_404(PrintCenter, id=center_id)
    if not _has_center_access(request.user, center):
        return redirect("dashboard:printshop_home")

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    base = PrintOrder.objects.filter(branch__center=center).exclude(status=PrintOrder.Status.CANCELED)

    def _agg(qs):
        r = qs.aggregate(s=Sum("total"), n=Count("id"))
        return {"sum": r["s"] or 0, "count": r["n"] or 0}

    rev = {
        "today": _agg(base.filter(created_at__gte=today_start)),
        "week": _agg(base.filter(created_at__gte=week_start)),
        "month": _agg(base.filter(created_at__gte=month_start)),
        "all": _agg(base),
    }

    top_products = (
        base.values("items__product__name_ru")
        .annotate(qty=Sum("items__qty"), revenue=Sum("items__line_total"))
        .filter(items__product__isnull=False)
        .order_by("-revenue")[:10]
    )

    # ── daily revenue trend, last 30 days ──
    period_start = today_start - timedelta(days=29)
    daily_rows = (
        base.filter(created_at__gte=period_start)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(s=Sum("total"))
    )
    daily_map = {r["day"]: r["s"] or 0 for r in daily_rows}
    daily_labels, daily_values = [], []
    for i in range(30):
        day = (period_start + timedelta(days=i)).date()
        daily_labels.append(day.strftime("%d.%m"))
        daily_values.append(float(daily_map.get(day, 0)))

    # ── order status breakdown (all orders, incl. canceled) ──
    status_counts = dict(
        PrintOrder.objects.filter(branch__center=center)
        .values_list("status")
        .annotate(n=Count("id"))
    )
    total_orders = sum(status_counts.values())
    status_breakdown = [
        {
            "status": status, "label": label, "color": color,
            "count": status_counts.get(status, 0),
            "pct": round(status_counts.get(status, 0) / total_orders * 100) if total_orders else 0,
        }
        for status, (label, color) in _STATUS_COLORS.items()
    ]

    return render(request, "dashboard/printshop/stats.html", {
        "center": center, "rev": rev, "top_products": top_products,
        "daily_labels": _json.dumps(daily_labels, ensure_ascii=False),
        "daily_values": _json.dumps(daily_values),
        "status_breakdown": status_breakdown,
        "total_orders": total_orders,
    })
