from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from django.db.models import Count, Max
from datetime import timedelta
from core.models import Restaurant, Branch, Membership, PromoCode, PageView
from catalog.models import (
    BranchItem, BranchCategory, BranchCategoryItem,
    Item, ItemCategory, Category, MenuSet,
)
from catalog.services import ensure_links_for_branch_item


def _user_restaurants(user):
    ids = Membership.objects.filter(user=user).values_list("restaurant_id", flat=True)
    return Restaurant.objects.filter(id__in=ids)


def _has_branch_access(user, branch):
    return Membership.objects.filter(user=user, restaurant=branch.restaurant).exists()


# ── AUTH ─────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")

    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username", "").strip(),
            password=request.POST.get("password", ""),
        )
        if user:
            login(request, user)
            return redirect("dashboard:home")
        messages.error(request, "Неверный логин или пароль")

    return render(request, "dashboard/login.html")


def logout_view(request):
    logout(request)
    return redirect("dashboard:login")


# ── HOME ─────────────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def home(request):
    restaurants = _user_restaurants(request.user).prefetch_related("branches")
    data = []
    for r in restaurants:
        branches = list(r.branches.filter(is_active=True).order_by("name_ru"))
        data.append({"restaurant": r, "branches": branches})
    return render(request, "dashboard/home.html", {"data": data})


# ── RESTAURANT ───────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def restaurant_edit(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    if not Membership.objects.filter(user=request.user, restaurant=restaurant).exists():
        return redirect("dashboard:home")

    if request.method == "POST":
        name = request.POST.get("name_ru", "").strip()
        if name:
            restaurant.name_ru = name
        restaurant.about_ru = request.POST.get("about_ru", "").strip()
        restaurant.external_url = request.POST.get("external_url", "").strip()

        logo = request.FILES.get("logo")
        if logo:
            restaurant.logo = logo

        restaurant.save()
        messages.success(request, "Данные ресторана сохранены")
        return redirect("dashboard:restaurant_edit", restaurant_id=restaurant.id)

    return render(request, "dashboard/restaurant_edit.html", {"restaurant": restaurant})


# ── BRANCH SETTINGS ──────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def branch_edit(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:home")

    if request.method == "POST":
        def dec(key, default="0"):
            try:
                return Decimal(request.POST.get(key) or default)
            except InvalidOperation:
                return Decimal(default)

        branch.delivery_enabled   = request.POST.get("delivery_enabled") == "on"
        branch.min_order_amount   = dec("min_order_amount")
        branch.delivery_fee       = dec("delivery_fee")
        branch.free_delivery_from = dec("free_delivery_from")
        branch.is_open_24h        = request.POST.get("is_open_24h") == "on"

        ot = request.POST.get("open_time", "").strip()
        ct = request.POST.get("close_time", "").strip()
        branch.open_time  = ot or None
        branch.close_time = ct or None

        branch.external_url = request.POST.get("external_url", "").strip()

        photo = request.FILES.get("promo_photo")
        if photo:
            branch.promo_photo = photo

        cover = request.FILES.get("cover_photo")
        if cover:
            branch.cover_photo = cover

        branch.save()

        c = getattr(branch, "photo_compression", None)
        if c:
            messages.success(
                request,
                f"Настройки сохранены | Фото акции: {c['before_kb']} KB → {c['after_kb']} KB "
                f"(−{c['saved_pct']}%, {c['orig_size']} → {c['new_size']})"
            )
        else:
            messages.success(request, "Настройки филиала сохранены")
        return redirect("dashboard:branch_edit", branch_id=branch.id)

    return render(request, "dashboard/branch_edit.html", {"branch": branch})


# ── BRANCH MENU (prices + list) ───────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def branch_items(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:home")

    categories = (
        BranchCategory.objects
        .filter(branch=branch, is_active=True)
        .select_related("category")
        .order_by("sort_order", "id")
    )

    menu = []
    for bc in categories:
        items = (
            BranchCategoryItem.objects
            .filter(branch_category=bc)
            .select_related("branch_item__item")
            .order_by("sort_order", "id")
        )
        menu.append({"category": bc, "items": list(items)})

    return render(request, "dashboard/branch_items.html", {
        "branch": branch,
        "menu": menu,
    })


# ── ADD ITEM ─────────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def item_add(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:home")

    restaurant = branch.restaurant
    categories = (
        BranchCategory.objects
        .filter(branch=branch, is_active=True)
        .select_related("category")
        .order_by("sort_order", "id")
    )

    if request.method == "POST":
        name = request.POST.get("name_ru", "").strip()
        if not name:
            messages.error(request, "Укажите название блюда")
            return redirect("dashboard:item_add", branch_id=branch.id)

        try:
            price = Decimal(request.POST.get("price") or "0")
        except InvalidOperation:
            price = Decimal("0")

        description = request.POST.get("description_ru", "").strip()
        photo = request.FILES.get("photo")

        # создаём Item
        item = Item(
            restaurant=restaurant,
            name_ru=name,
            description_ru=description,
            base_price=price,
        )
        if photo:
            item.photo = photo
        item.save()

        c = item.photo_compression
        if c:
            photo_msg = (
                f" | Фото: {c['before_kb']} KB → {c['after_kb']} KB "
                f"(−{c['saved_pct']}%, {c['orig_size']} → {c['new_size']})"
            )
        else:
            photo_msg = ""

        # создаём BranchItem
        bi = BranchItem.objects.create(
            branch=branch,
            item=item,
            price=price,
            is_available=True,
        )

        # привязываем к категории если выбрана
        branch_cat_id = request.POST.get("branch_category_id")
        if branch_cat_id:
            try:
                bc = BranchCategory.objects.get(id=branch_cat_id, branch=branch)
                # создаём ItemCategory (связь Item <-> Category)
                ic, _ = ItemCategory.objects.get_or_create(
                    item=item,
                    category=bc.category,
                    defaults={"sort_order": 0},
                )
                # создаём BranchCategoryItem
                BranchCategoryItem.objects.get_or_create(
                    branch_category=bc,
                    branch_item=bi,
                    defaults={"sort_order": 0},
                )
            except BranchCategory.DoesNotExist:
                pass
        else:
            # без категории — просто пробуем автосвязи
            ensure_links_for_branch_item(bi)

        messages.success(request, f"Блюдо «{name}» добавлено{photo_msg}")
        return redirect("dashboard:branch_items", branch_id=branch.id)

    return render(request, "dashboard/item_add.html", {
        "branch": branch,
        "categories": categories,
    })


# ── EDIT ITEM ─────────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def item_edit(request, branch_item_id):
    bi = get_object_or_404(BranchItem, id=branch_item_id)
    if not _has_branch_access(request.user, bi.branch):
        return redirect("dashboard:home")

    item = bi.item

    if request.method == "POST":
        name = request.POST.get("name_ru", "").strip()
        if name:
            item.name_ru = name
        item.description_ru = request.POST.get("description_ru", "").strip()

        try:
            bi.price = Decimal(request.POST.get("price") or "0")
        except InvalidOperation:
            pass
        bi.is_available = request.POST.get("is_available") == "on"

        photo = request.FILES.get("photo")
        if photo:
            item.photo = photo

        item.save()
        bi.save(update_fields=["price", "is_available", "updated_at"])

        c = item.photo_compression
        if c:
            photo_msg = (
                f" | Фото: {c['before_kb']} KB → {c['after_kb']} KB "
                f"(−{c['saved_pct']}%, {c['orig_size']} → {c['new_size']})"
            )
            messages.success(request, f"Блюдо обновлено{photo_msg}")
        else:
            messages.success(request, "Блюдо обновлено")
        return redirect("dashboard:branch_items", branch_id=bi.branch_id)

    return render(request, "dashboard/item_edit.html", {"bi": bi, "item": item})


# ── AJAX: update price ────────────────────────────────────────────────────────

@require_POST
@login_required(login_url="dashboard:login")
def update_item_price(request, branch_item_id):
    bi = get_object_or_404(BranchItem, id=branch_item_id)
    if not _has_branch_access(request.user, bi.branch):
        return JsonResponse({"ok": False}, status=403)
    try:
        price = Decimal(request.POST.get("price", ""))
        if price < 0:
            raise ValueError
    except Exception:
        return JsonResponse({"ok": False, "error": "Некорректная цена"})

    bi.price = price
    bi.save(update_fields=["price", "updated_at"])
    return JsonResponse({"ok": True, "price": str(bi.price)})


# ── AJAX: toggle availability ─────────────────────────────────────────────────

@require_POST
@login_required(login_url="dashboard:login")
def toggle_item(request, branch_item_id):
    bi = get_object_or_404(BranchItem, id=branch_item_id)
    if not _has_branch_access(request.user, bi.branch):
        return JsonResponse({"ok": False}, status=403)

    bi.is_available = not bi.is_available
    bi.save(update_fields=["is_available", "updated_at"])
    return JsonResponse({"ok": True, "is_available": bi.is_available})


# ── PROMO CODES ───────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def promo_list(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:home")

    if request.method == "POST":
        code = request.POST.get("code", "").strip().upper()
        discount_type = request.POST.get("discount_type", "")
        discount_value = Decimal(request.POST.get("discount_value") or "0")
        valid_until = request.POST.get("valid_until") or None
        max_uses = int(request.POST.get("max_uses") or 0)

        if not code:
            messages.error(request, "Введите промокод")
        elif PromoCode.objects.filter(branch=branch, code=code).exists():
            messages.error(request, f"Промокод «{code}» уже существует")
        else:
            PromoCode.objects.create(
                branch=branch,
                code=code,
                discount_type=discount_type,
                discount_value=discount_value,
                valid_until=valid_until,
                max_uses=max_uses,
                is_active=True,
            )
            messages.success(request, f"Промокод «{code}» создан")
        return redirect("dashboard:promo_list", branch_id=branch.id)

    promos = PromoCode.objects.filter(branch=branch).order_by("-created_at")
    today = timezone.localdate()
    return render(request, "dashboard/promo_list.html", {
        "branch": branch,
        "promos": promos,
        "today": today,
        "discount_types": PromoCode.DiscountType.choices,
    })


@require_POST
@login_required(login_url="dashboard:login")
def promo_toggle(request, promo_id):
    promo = get_object_or_404(PromoCode, id=promo_id)
    if not _has_branch_access(request.user, promo.branch):
        return redirect("dashboard:home")
    promo.is_active = not promo.is_active
    promo.save(update_fields=["is_active", "updated_at"])
    return redirect("dashboard:promo_list", branch_id=promo.branch_id)


@require_POST
@login_required(login_url="dashboard:login")
def promo_delete(request, promo_id):
    promo = get_object_or_404(PromoCode, id=promo_id)
    if not _has_branch_access(request.user, promo.branch):
        return redirect("dashboard:home")
    promo.delete()
    messages.success(request, "Промокод удалён")
    return redirect("dashboard:promo_list", branch_id=promo.branch_id)



# ── ANALYTICS ────────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def analytics(request):
    from orders.models import Order
    from shops.models import StoreOrder, StoreMembership
    from pharmacy.models import PharmacyOrder, PharmacyMembership
    from hotels.models import HotelBooking, HotelMembership
    from django.db.models import Sum

    user     = request.user
    is_super = user.is_superuser

    now = timezone.now()
    period = request.GET.get("period", "30")
    try:
        days = int(period)
    except ValueError:
        days = 30
    days = max(1, min(days, 365))
    since = now - timedelta(days=days)

    # ── ID организаций пользователя ───────────────────────────────────────────
    if is_super:
        my_restaurant_ids = my_hotel_ids = my_store_ids = my_pharmacy_ids = None
    else:
        my_restaurant_ids = list(
            Membership.objects.filter(user=user).values_list("restaurant_id", flat=True)
        )
        my_hotel_ids = list(
            HotelMembership.objects.filter(user=user).values_list("hotel_id", flat=True)
        )
        my_store_ids = list(
            StoreMembership.objects.filter(user=user).values_list("store_id", flat=True)
        )
        my_pharmacy_ids = list(
            PharmacyMembership.objects.filter(user=user).values_list("pharmacy_id", flat=True)
        )

    # ── Посещаемость ──────────────────────────────────────────────────────────
    pv_qs = PageView.objects.filter(timestamp__gte=since)

    allowed_sections = None
    if not is_super:
        allowed_sections = set()
        if my_restaurant_ids: allowed_sections.add("restaurant")
        if my_hotel_ids:       allowed_sections.add("hotels")
        if my_store_ids:       allowed_sections.add("shops")
        if my_pharmacy_ids:    allowed_sections.add("pharmacy")
        if allowed_sections:
            pv_qs = pv_qs.filter(section__in=allowed_sections)

    by_section = (
        pv_qs.values("section")
             .annotate(total=Count("id"), unique=Count("ip_hash", distinct=True))
             .order_by("-total")
    )
    section_labels = dict(PageView.SECTION_CHOICES)
    sections_data = [
        {
            "section": row["section"],
            "label": section_labels.get(row["section"], row["section"]),
            "total": row["total"],
            "unique": row["unique"],
        }
        for row in by_section
    ]
    total_views  = pv_qs.count()
    total_unique = pv_qs.values("ip_hash").distinct().count()

    chart_days  = min(days, 60)
    chart_since = now - timedelta(days=chart_days)
    daily_qs = (
        PageView.objects
        .filter(timestamp__gte=chart_since)
        .extra(select={"day": "DATE(timestamp)"})
        .values("day")
        .annotate(cnt=Count("id"))
        .order_by("day")
    )
    if not is_super and allowed_sections:
        daily_qs = daily_qs.filter(section__in=allowed_sections)
    daily_labels = [str(r["day"]) for r in daily_qs]
    daily_values = [r["cnt"] for r in daily_qs]

    # ── Базовые queryset-ы заказов (уже отфильтрованы по доступу) ─────────────
    if is_super:
        rest_qs  = Order.objects.all()
        shop_qs  = StoreOrder.objects.all()
        ph_qs    = PharmacyOrder.objects.all()
        hotel_qs = HotelBooking.objects.all()
    else:
        rest_qs  = Order.objects.filter(branch__restaurant_id__in=my_restaurant_ids)
        shop_qs  = StoreOrder.objects.filter(branch__store_id__in=my_store_ids)
        ph_qs    = PharmacyOrder.objects.filter(branch__pharmacy_id__in=my_pharmacy_ids)
        hotel_qs = HotelBooking.objects.filter(branch__hotel_id__in=my_hotel_ids)

    def _agg(qs, name_field, revenue_field, period_since):
        rows_all = list(
            qs.values(name_field)
              .annotate(cnt=Count("id"), revenue=Sum(revenue_field))
              .order_by("-cnt")
        )
        total_all    = qs.count()
        total_period = qs.filter(created_at__gte=period_since).count()
        norm = [
            {"name": r[name_field] or "—", "cnt": r["cnt"], "revenue": r.get("revenue") or 0}
            for r in rows_all
        ]
        return norm, total_all, total_period

    rest_rows,  rest_total_all,  rest_total_period  = _agg(rest_qs,  "branch__restaurant__name_ru", "total_amount", since)
    shop_rows,  shop_total_all,  shop_total_period  = _agg(shop_qs,  "branch__store__name_ru",      "total",        since)
    ph_rows,    ph_total_all,    ph_total_period    = _agg(ph_qs,    "branch__pharmacy__name_ru",   "total_amount", since)
    hotel_rows, hotel_total_all, hotel_total_period = _agg(hotel_qs, "branch__hotel__name_ru",      "total",        since)

    grand_period = rest_total_period + shop_total_period + ph_total_period + hotel_total_period
    grand_all    = rest_total_all    + shop_total_all    + ph_total_all    + hotel_total_all

    all_order_sections = [
        {"icon": "🍽",  "label": "Рестораны", "total_period": rest_total_period,  "total_all": rest_total_all,  "rows_all": rest_rows},
        {"icon": "🏪",  "label": "Магазины",  "total_period": shop_total_period,  "total_all": shop_total_all,  "rows_all": shop_rows},
        {"icon": "💊",  "label": "Аптеки",    "total_period": ph_total_period,    "total_all": ph_total_all,    "rows_all": ph_rows},
        {"icon": "🏨",  "label": "Отели",     "total_period": hotel_total_period, "total_all": hotel_total_all, "rows_all": hotel_rows},
    ]

    # Обычный пользователь видит только разделы, к которым у него есть доступ и данные
    if not is_super:
        order_sections = [s for s in all_order_sections if s["total_all"] > 0]
    else:
        order_sections = all_order_sections

    return render(request, "dashboard/analytics.html", {
        "period": days,
        "is_super": is_super,
        "sections_data": sections_data,
        "total_views": total_views,
        "total_unique": total_unique,
        "daily_labels": daily_labels,
        "daily_values": daily_values,
        "order_sections": order_sections,
        "grand_period": grand_period,
        "grand_all": grand_all,
    })


# ── ORDERS ANALYTICS ─────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def orders_analytics(request):
    from orders.models import Order, OrderItem
    from django.db.models import Sum, Count
    from django.utils import timezone
    from datetime import timedelta, date

    user     = request.user
    is_super = user.is_superuser

    # ── фильтры ──────────────────────────────────────────────────────────────
    period = request.GET.get("period", "30")
    try:
        days = int(period)
    except ValueError:
        days = 30
    days = max(1, min(days, 365))

    now   = timezone.now()
    since = now - timedelta(days=days)

    # ── доступные рестораны ───────────────────────────────────────────────────
    if is_super:
        restaurants = Restaurant.objects.filter(branches__orders__isnull=False).distinct().order_by("name_ru")
        restaurant_id = request.GET.get("restaurant")
        if restaurant_id and restaurant_id.isdigit():
            order_qs = Order.objects.filter(branch__restaurant_id=int(restaurant_id))
        else:
            order_qs = Order.objects.all()
            restaurant_id = None
    else:
        my_ids = list(Membership.objects.filter(user=user).values_list("restaurant_id", flat=True))
        restaurants = Restaurant.objects.filter(id__in=my_ids).order_by("name_ru")
        order_qs    = Order.objects.filter(branch__restaurant_id__in=my_ids)
        restaurant_id = None

    # ── применяем фильтр по периоду ───────────────────────────────────────────
    order_qs_period = order_qs.filter(created_at__gte=since)

    # ── KPI ──────────────────────────────────────────────────────────────────
    total_orders  = order_qs_period.count()
    total_revenue = order_qs_period.aggregate(s=Sum("total_amount"))["s"] or 0
    total_items   = (
        OrderItem.objects
        .filter(order__in=order_qs_period)
        .aggregate(s=Sum("qty"))["s"] or 0
    )

    # ── топ блюд за период ────────────────────────────────────────────────────
    top_items = (
        OrderItem.objects
        .filter(order__in=order_qs_period)
        .values("item__name_ru")
        .annotate(qty_total=Sum("qty"), order_count=Count("order", distinct=True))
        .order_by("-qty_total")[:30]
    )

    # ── динамика по дням ──────────────────────────────────────────────────────
    chart_days  = min(days, 60)
    chart_since = now - timedelta(days=chart_days)
    daily_qs = (
        order_qs
        .filter(created_at__gte=chart_since)
        .extra(select={"day": 'DATE("orders_order"."created_at")'})
        .values("day")
        .annotate(cnt=Count("id"), revenue=Sum("total_amount"))
        .order_by("day")
    )
    chart_labels  = [str(r["day"]) for r in daily_qs]
    chart_orders  = [r["cnt"] for r in daily_qs]
    chart_revenue = [float(r["revenue"] or 0) for r in daily_qs]

    # ── список всех заказов (пагинация) ───────────────────────────────────────
    from django.core.paginator import Paginator

    orders_list = (
        order_qs_period
        .select_related("branch", "branch__restaurant")
        .prefetch_related("items__item")
        .order_by("-created_at")
    )
    paginator = Paginator(orders_list, 30)
    page_num  = request.GET.get("page", 1)
    page_obj  = paginator.get_page(page_num)

    return render(request, "dashboard/orders.html", {
        "period":        days,
        "is_super":      is_super,
        "restaurants":   restaurants,
        "restaurant_id": restaurant_id,
        "total_orders":  total_orders,
        "total_revenue": total_revenue,
        "total_items":   total_items,
        "top_items":     list(top_items),
        "chart_labels":  chart_labels,
        "chart_orders":  chart_orders,
        "chart_revenue": chart_revenue,
        "page_obj":      page_obj,
    })


# ── CATEGORIES ────────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def branch_categories(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:home")

    active_bcs = list(
        BranchCategory.objects
        .filter(branch=branch)
        .select_related("category__menu_set")
        .order_by("sort_order", "id")
    )
    added_cat_ids = {bc.category_id for bc in active_bcs}

    # Все категории ресторана, ещё не добавленные в филиал
    all_cats = (
        Category.objects
        .filter(menu_set__restaurant=branch.restaurant)
        .select_related("menu_set")
        .order_by("menu_set__name", "name_ru")
    )
    available_cats = [c for c in all_cats if c.id not in added_cat_ids]

    return render(request, "dashboard/branch_categories.html", {
        "branch": branch,
        "categories": active_bcs,
        "available_cats": available_cats,
    })


@require_POST
@login_required(login_url="dashboard:login")
def category_add(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return JsonResponse({"ok": False}, status=403)

    category_id = request.POST.get("category_id")
    try:
        cat = Category.objects.select_related("menu_set").get(
            id=category_id, menu_set__restaurant=branch.restaurant
        )
        max_order = BranchCategory.objects.filter(branch=branch).aggregate(
            m=Max("sort_order")
        )["m"] or 0
        bc, created = BranchCategory.objects.get_or_create(
            branch=branch,
            category=cat,
            defaults={"sort_order": max_order + 10, "is_active": True},
        )
        return JsonResponse({
            "ok": True,
            "bc_id": bc.id,
            "cat_id": cat.id,
            "name": cat.name_ru,
            "menu_set": cat.menu_set.name,
            "sort_order": bc.sort_order,
            "is_active": bc.is_active,
        })
    except Category.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Категория не найдена"})


@require_POST
@login_required(login_url="dashboard:login")
def category_toggle(request, bc_id):
    bc = get_object_or_404(BranchCategory, id=bc_id)
    if not _has_branch_access(request.user, bc.branch):
        return JsonResponse({"ok": False}, status=403)
    bc.is_active = not bc.is_active
    bc.save(update_fields=["is_active", "updated_at"])
    return JsonResponse({"ok": True, "is_active": bc.is_active})


@require_POST
@login_required(login_url="dashboard:login")
def category_reorder(request, bc_id):
    bc = get_object_or_404(BranchCategory, id=bc_id)
    if not _has_branch_access(request.user, bc.branch):
        return JsonResponse({"ok": False}, status=403)
    try:
        sort_order = int(request.POST.get("sort_order", bc.sort_order))
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "invalid"})
    bc.sort_order = sort_order
    bc.save(update_fields=["sort_order", "updated_at"])
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url="dashboard:login")
def category_remove(request, bc_id):
    bc = get_object_or_404(BranchCategory, id=bc_id)
    if not _has_branch_access(request.user, bc.branch):
        return JsonResponse({"ok": False}, status=403)
    bc.delete()
    return JsonResponse({"ok": True})
