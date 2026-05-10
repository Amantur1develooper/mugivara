from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from django.db.models import Count, Max, Sum, Q
from datetime import timedelta
from core.models import Restaurant, Branch, Membership, PromoCode, PageView
from catalog.models import (
    BranchItem, BranchCategory, BranchCategoryItem,
    Item, ItemCategory, Category, MenuSet, BranchMenuSet,
    DishConstructor, ConstructorGroup, ConstructorIngredient,
)
from catalog.services import ensure_links_for_branch_item
from reservations.models import Floor, Place


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
    from orders.models import Order

    restaurants = _user_restaurants(request.user).prefetch_related("branches")

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start  = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    data = []
    for r in restaurants:
        branches = list(r.branches.filter(is_active=True).order_by("name_ru"))
        branch_ids = [b.id for b in branches]

        def _sum(qs):
            return qs.aggregate(s=Sum("total_amount"))["s"] or 0

        base = Order.objects.filter(branch_id__in=branch_ids).exclude(status=Order.Status.CANCELLED)
        rev = {
            "today":  _sum(base.filter(created_at__gte=today_start)),
            "week":   _sum(base.filter(created_at__gte=week_start)),
            "month":  _sum(base.filter(created_at__gte=month_start)),
            "today_cnt":  base.filter(created_at__gte=today_start).count(),
            "week_cnt":   base.filter(created_at__gte=week_start).count(),
            "month_cnt":  base.filter(created_at__gte=month_start).count(),
        }
        data.append({"restaurant": r, "branches": branches, "rev": rev})

    from karaoke.models import KaraokeVenue, KaraokeMembership
    user = request.user
    if user.is_staff or user.is_superuser:
        karaoke_venues = list(KaraokeVenue.objects.prefetch_related("rooms").all())
    else:
        ids = KaraokeMembership.objects.filter(user=user).values_list("venue_id", flat=True)
        karaoke_venues = list(KaraokeVenue.objects.filter(id__in=ids).prefetch_related("rooms"))

    return render(request, "dashboard/home.html", {"data": data, "karaoke_venues": karaoke_venues})


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
        restaurant.about_ru     = request.POST.get("about_ru", "").strip()
        restaurant.external_url = request.POST.get("external_url", "").strip()
        restaurant.phone        = request.POST.get("phone", "").strip()
        restaurant.whatsapp     = request.POST.get("whatsapp", "").strip()
        restaurant.instagram    = request.POST.get("instagram", "").strip()
        restaurant.telegram     = request.POST.get("telegram", "").strip()
        restaurant.map_url      = request.POST.get("map_url", "").strip()
        restaurant.tiktok       = request.POST.get("tiktok", "").strip()

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

        branch.delivery_enabled    = request.POST.get("delivery_enabled") == "on"
        branch.min_order_amount    = dec("min_order_amount")
        branch.delivery_fee        = dec("delivery_fee")
        branch.free_delivery_from  = dec("free_delivery_from")
        branch.is_open_24h         = request.POST.get("is_open_24h") == "on"
        branch.pay_cash_enabled    = request.POST.get("pay_cash_enabled") == "on"
        branch.pay_online_enabled  = request.POST.get("pay_online_enabled") == "on"

        ot = request.POST.get("open_time", "").strip()
        ct = request.POST.get("close_time", "").strip()
        branch.open_time  = ot or None
        branch.close_time = ct or None

        branch.external_url = request.POST.get("external_url", "").strip()

        lat_raw = request.POST.get("lat", "").strip()
        lon_raw = request.POST.get("lon", "").strip()
        branch.lat = lat_raw if lat_raw else None
        branch.lon = lon_raw if lon_raw else None

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
            name_ky=request.POST.get("name_ky", "").strip(),
            name_en=request.POST.get("name_en", "").strip(),
            description_ru=description,
            description_ky=request.POST.get("description_ky", "").strip(),
            description_en=request.POST.get("description_en", "").strip(),
            base_price=price,
        )
        if photo:
            item.photo = photo
        item.save()

        # создаём BranchItem
        bi = BranchItem.objects.create(
            branch=branch,
            item=item,
            price=price,
            is_available=True,
        )

        # привязываем к категории если выбрана
        branch_cat_id = request.POST.get("branch_category_id")

        # создание новой категории inline
        if branch_cat_id == "__new__":
            new_cat_ru = request.POST.get("new_cat_ru", "").strip()
            if new_cat_ru:
                # Ищем или создаём глобальную Category в MenuSet ресторана
                menu_set = MenuSet.objects.filter(restaurant=restaurant).first()
                if not menu_set:
                    menu_set = MenuSet.objects.create(restaurant=restaurant, name="Меню")
                # Привязываем MenuSet к филиалу если ещё не привязан
                BranchMenuSet.objects.get_or_create(branch=branch, menu_set=menu_set)
                cat, _ = Category.objects.get_or_create(
                    menu_set=menu_set,
                    name_ru=new_cat_ru,
                    defaults={
                        "name_ky": request.POST.get("new_cat_ky", "").strip() or new_cat_ru,
                        "name_en": request.POST.get("new_cat_en", "").strip() or new_cat_ru,
                    },
                )
                max_order = BranchCategory.objects.filter(branch=branch).aggregate(m=Max("sort_order"))["m"] or 0
                bc, _ = BranchCategory.objects.get_or_create(
                    branch=branch,
                    category=cat,
                    defaults={"sort_order": max_order + 1, "is_active": True},
                )
                BranchCategoryItem.objects.get_or_create(
                    branch_category=bc, branch_item=bi, defaults={"sort_order": 0}
                )
                ItemCategory.objects.get_or_create(item=item, category=cat, defaults={"sort_order": 0})
            else:
                ensure_links_for_branch_item(bi)

        elif branch_cat_id:
            try:
                bc = BranchCategory.objects.get(id=branch_cat_id, branch=branch)
                ItemCategory.objects.get_or_create(
                    item=item, category=bc.category, defaults={"sort_order": 0}
                )
                BranchCategoryItem.objects.get_or_create(
                    branch_category=bc, branch_item=bi, defaults={"sort_order": 0}
                )
            except BranchCategory.DoesNotExist:
                pass
        else:
            ensure_links_for_branch_item(bi)

        messages.success(request, f"Блюдо «{name}» добавлено")
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
    branch = bi.branch

    branch_categories = (
        BranchCategory.objects
        .filter(branch=branch, is_active=True)
        .select_related("category")
        .order_by("sort_order", "id")
    )
    current_bci = bi.categories_in_branch.select_related("branch_category").first()
    current_cat_id = current_bci.branch_category_id if current_bci else None

    if request.method == "POST":
        name = request.POST.get("name_ru", "").strip()
        if name:
            item.name_ru = name
        item.name_ky = request.POST.get("name_ky", "").strip()
        item.name_en = request.POST.get("name_en", "").strip()
        item.description_ru = request.POST.get("description_ru", "").strip()
        item.description_ky = request.POST.get("description_ky", "").strip()
        item.description_en = request.POST.get("description_en", "").strip()

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

        # Update category assignment
        new_cat_id = request.POST.get("branch_category_id", "").strip()
        if new_cat_id:
            try:
                new_bc = BranchCategory.objects.get(id=int(new_cat_id), branch=branch)
                # Remove from all other categories in this branch, assign to new one
                bi.categories_in_branch.exclude(branch_category=new_bc).delete()
                BranchCategoryItem.objects.get_or_create(branch_category=new_bc, branch_item=bi)
            except (BranchCategory.DoesNotExist, ValueError):
                pass
        else:
            # "Без категории" — remove all category assignments
            bi.categories_in_branch.all().delete()

        messages.success(request, "Блюдо обновлено")
        return redirect("dashboard:branch_items", branch_id=bi.branch_id)

    return render(request, "dashboard/item_edit.html", {
        "bi": bi,
        "item": item,
        "branch_categories": branch_categories,
        "current_cat_id": current_cat_id,
    })


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
    # Выручка — только стоимость блюд (без доставки)
    total_revenue = (
        OrderItem.objects
        .filter(order__in=order_qs_period)
        .aggregate(s=Sum("line_total"))["s"] or 0
    )
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
        .annotate(cnt=Count("id", distinct=True), revenue=Sum("items__line_total"))
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
        .annotate(items_total=Sum("items__line_total"))
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


# ── MENU SETS (сеты категорий) ────────────────────────────────────────────────

def _has_restaurant_access(user, restaurant):
    if user.is_superuser:
        return True
    return Membership.objects.filter(user=user, restaurant=restaurant).exists()


@login_required(login_url="dashboard:login")
def menu_sets(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    if not _has_restaurant_access(request.user, restaurant):
        return redirect("dashboard:home")
    sets = (
        MenuSet.objects
        .filter(restaurant=restaurant)
        .prefetch_related("categories")
        .order_by("id")
    )
    return render(request, "dashboard/menu_sets.html", {
        "restaurant": restaurant,
        "sets": sets,
    })


@require_POST
@login_required(login_url="dashboard:login")
def menu_set_add(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    if not _has_restaurant_access(request.user, restaurant):
        return JsonResponse({"ok": False}, status=403)
    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Укажите название сета"})
    ms = MenuSet.objects.create(restaurant=restaurant, name=name, is_active=True)
    return JsonResponse({"ok": True, "id": ms.id, "name": ms.name})


@require_POST
@login_required(login_url="dashboard:login")
def menu_set_rename(request, menu_set_id):
    ms = get_object_or_404(MenuSet, id=menu_set_id)
    if not _has_restaurant_access(request.user, ms.restaurant):
        return JsonResponse({"ok": False}, status=403)
    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Название не может быть пустым"})
    ms.name = name
    ms.save(update_fields=["name", "updated_at"])
    return JsonResponse({"ok": True, "name": ms.name})


@require_POST
@login_required(login_url="dashboard:login")
def menu_set_delete(request, menu_set_id):
    ms = get_object_or_404(MenuSet, id=menu_set_id)
    if not _has_restaurant_access(request.user, ms.restaurant):
        return JsonResponse({"ok": False}, status=403)
    ms.delete()
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url="dashboard:login")
def ms_category_add(request, menu_set_id):
    ms = get_object_or_404(MenuSet, id=menu_set_id)
    if not _has_restaurant_access(request.user, ms.restaurant):
        return JsonResponse({"ok": False}, status=403)
    name_ru = request.POST.get("name_ru", "").strip()
    if not name_ru:
        return JsonResponse({"ok": False, "error": "Укажите название категории"})
    cat = Category.objects.create(
        menu_set=ms,
        name_ru=name_ru,
        name_ky=request.POST.get("name_ky", "").strip(),
        name_en=request.POST.get("name_en", "").strip(),
    )
    return JsonResponse({"ok": True, "id": cat.id, "name_ru": cat.name_ru,
                         "name_ky": cat.name_ky, "name_en": cat.name_en})


@require_POST
@login_required(login_url="dashboard:login")
def ms_category_edit(request, category_id):
    cat = get_object_or_404(Category, id=category_id)
    if not _has_restaurant_access(request.user, cat.menu_set.restaurant):
        return JsonResponse({"ok": False}, status=403)
    name_ru = request.POST.get("name_ru", "").strip()
    if not name_ru:
        return JsonResponse({"ok": False, "error": "Название не может быть пустым"})
    cat.name_ru = name_ru
    cat.name_ky = request.POST.get("name_ky", "").strip()
    cat.name_en = request.POST.get("name_en", "").strip()
    cat.save(update_fields=["name_ru", "name_ky", "name_en", "updated_at"])
    return JsonResponse({"ok": True, "name_ru": cat.name_ru,
                         "name_ky": cat.name_ky, "name_en": cat.name_en})


@require_POST
@login_required(login_url="dashboard:login")
def ms_category_delete(request, category_id):
    cat = get_object_or_404(Category, id=category_id)
    if not _has_restaurant_access(request.user, cat.menu_set.restaurant):
        return JsonResponse({"ok": False}, status=403)
    cat.delete()
    return JsonResponse({"ok": True})


# ── TABLES (столики) ──────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def branch_tables(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:home")
    floors = branch.floors.prefetch_related("places").order_by("sort_order", "id")
    return render(request, "dashboard/tables.html", {"branch": branch, "floors": floors})


@require_POST
@login_required(login_url="dashboard:login")
def floor_add(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return JsonResponse({"ok": False}, status=403)
    name = request.POST.get("name", "").strip() or "Зал"
    floor = Floor.objects.create(branch=branch, name_ru=name)
    return JsonResponse({"ok": True, "id": floor.id, "name": floor.name_ru})


@require_POST
@login_required(login_url="dashboard:login")
def floor_delete(request, floor_id):
    floor = get_object_or_404(Floor, id=floor_id)
    if not _has_branch_access(request.user, floor.branch):
        return JsonResponse({"ok": False}, status=403)
    floor.delete()
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url="dashboard:login")
def table_add(request, floor_id):
    floor = get_object_or_404(Floor, id=floor_id)
    if not _has_branch_access(request.user, floor.branch):
        return JsonResponse({"ok": False}, status=403)

    seats = max(1, int(request.POST.get("seats") or 2))
    bulk = request.POST.get("bulk") == "1"
    created = []

    if bulk:
        prefix = request.POST.get("prefix", "Стол").strip() or "Стол"
        start  = max(1, int(request.POST.get("start") or 1))
        count  = min(50, max(1, int(request.POST.get("count") or 1)))
        for i in range(start, start + count):
            p = Place.objects.create(floor=floor, title=f"{prefix} {i}", seats=seats)
            created.append({"id": p.id, "title": p.title, "seats": p.seats, "token": p.token})
    else:
        title = request.POST.get("title", "").strip()
        if not title:
            return JsonResponse({"ok": False, "error": "Название обязательно"})
        p = Place.objects.create(floor=floor, title=title, seats=seats)
        created.append({"id": p.id, "title": p.title, "seats": p.seats, "token": p.token})

    return JsonResponse({"ok": True, "tables": created})


@require_POST
@login_required(login_url="dashboard:login")
def table_delete(request, table_id):
    place = get_object_or_404(Place, id=table_id)
    if not _has_branch_access(request.user, place.floor.branch):
        return JsonResponse({"ok": False}, status=403)
    place.delete()
    return JsonResponse({"ok": True})


# ══════════════════════════════════════════════════════════════════════════════
# POS — КАССА
# ══════════════════════════════════════════════════════════════════════════════

import json as _json
from orders.models import Order, OrderItem
from django.db.models import Prefetch as _Prefetch


@login_required(login_url="dashboard:login")
def pos(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, branch)):
        return redirect("dashboard:home")

    categories = (
        BranchCategory.objects
        .filter(branch=branch, is_active=True)
        .select_related("category")
        .prefetch_related(
            _Prefetch(
                "items_in_category",
                queryset=(
                    BranchCategoryItem.objects
                    .select_related("branch_item__item")
                    .filter(branch_item__is_available=True)
                    .order_by("sort_order")
                ),
            )
        )
        .order_by("sort_order")
    )

    live_orders = (
        Order.objects
        .filter(branch=branch, status__in=[
            Order.Status.NEW, Order.Status.ACCEPTED,
            Order.Status.COOKING, Order.Status.READY,
        ])
        .prefetch_related("items__item")
        .order_by("-created_at")
    )

    return render(request, "dashboard/pos.html", {
        "branch": branch,
        "categories": categories,
        "live_orders": live_orders,
    })


@require_POST
@login_required(login_url="dashboard:login")
@transaction.atomic
def pos_order_create(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, branch)):
        return JsonResponse({"ok": False}, status=403)

    try:
        data = _json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "error": "bad json"}, status=400)

    items_data      = data.get("items", [])
    order_type      = data.get("type", Order.Type.DINE_IN)
    payment_method  = data.get("payment", Order.PaymentMethod.CASH)
    customer_name   = (data.get("name") or "").strip()
    comment         = (data.get("comment") or "").strip()

    if not items_data:
        return JsonResponse({"ok": False, "error": "Нет позиций"}, status=400)

    order = Order.objects.create(
        branch=branch,
        type=order_type,
        status=Order.Status.NEW,
        payment_method=payment_method,
        customer_name=customer_name,
        comment=comment,
    )

    total = Decimal("0")
    for it in items_data:
        try:
            bi  = BranchItem.objects.select_related("item").get(
                id=int(it["bi_id"]), branch=branch, is_available=True
            )
            qty = max(1, int(it.get("qty", 1)))
            line = bi.price * qty
            OrderItem.objects.create(
                order=order, item=bi.item,
                qty=qty, price_snapshot=bi.price, line_total=line,
            )
            total += line
            # Decrement stock if tracked
            if bi.stock is not None:
                bi.stock = max(0, bi.stock - qty)
                if bi.stock == 0:
                    bi.is_available = False
                bi.save(update_fields=["stock", "is_available"])
        except (BranchItem.DoesNotExist, ValueError, KeyError):
            continue

    order.total_amount = total
    order.status = Order.Status.CLOSED
    order.payment_status = Order.PaymentStatus.PAID
    order.save(update_fields=["total_amount", "status", "payment_status"])

    return JsonResponse({"ok": True, "order_id": order.id, "total": str(total)})


@require_POST
@login_required(login_url="dashboard:login")
def pos_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, order.branch)):
        return JsonResponse({"ok": False}, status=403)

    new_status  = request.POST.get("status")
    new_payment = request.POST.get("payment_status")

    fields = []
    if new_status and new_status in Order.Status.values:
        # Restore stock when cancelling a closed POS order
        if new_status == Order.Status.CANCELLED and order.status == Order.Status.CLOSED:
            for oi in order.items.select_related("item").all():
                try:
                    bi = BranchItem.objects.get(branch=order.branch, item=oi.item)
                    if bi.stock is not None:
                        bi.stock += oi.qty
                        bi.is_available = True
                        bi.save(update_fields=["stock", "is_available"])
                except BranchItem.DoesNotExist:
                    pass
        order.status = new_status
        fields.append("status")
    if new_payment and new_payment in Order.PaymentStatus.values:
        order.payment_status = new_payment
        fields.append("payment_status")
    if fields:
        fields.append("updated_at")
        order.save(update_fields=fields)

    return JsonResponse({
        "ok": True,
        "status": order.status,
        "payment_status": order.payment_status,
    })


@login_required(login_url="dashboard:login")
def pos_live_orders(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, branch)):
        return JsonResponse({"ok": False}, status=403)

    orders = (
        Order.objects
        .filter(branch=branch, status__in=[
            Order.Status.NEW, Order.Status.ACCEPTED,
            Order.Status.COOKING, Order.Status.READY,
        ])
        .prefetch_related("items__item", "constructor_items")
        .order_by("-created_at")
    )

    result = []
    for o in orders:
        items = [
            {"name": oi.item.name_ru, "qty": oi.qty, "line": str(oi.line_total)}
            for oi in o.items.all()
        ]
        for ci in o.constructor_items.all():
            ing_parts = []
            for sel in (ci.ingredients_snapshot or []):
                ing_names = ", ".join(i["name"] for i in sel.get("ings", []))
                ing_parts.append(f"{sel['gname']}: {ing_names}")
            detail = " · ".join(ing_parts)
            items.append({
                "name": f"🧩 {ci.constructor_name_snapshot}" + (f" ({detail})" if detail else ""),
                "qty":  ci.qty,
                "line": str(ci.line_total),
            })
        result.append({
            "id":             o.id,
            "type":           o.type,
            "type_label":     o.get_type_display(),
            "status":         o.status,
            "status_label":   o.get_status_display(),
            "customer":       o.customer_name,
            "phone":          o.customer_phone,
            "address":        o.delivery_address,
            "total":          str(o.total_amount),
            "payment":        o.payment_method,
            "payment_status": o.payment_status,
            "comment":        o.comment,
            "created":        o.created_at.strftime("%H:%M"),
            "items": items,
        })

    return JsonResponse({"ok": True, "orders": result})


@login_required(login_url="dashboard:login")
def pos_receipt(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__item").select_related("branch__restaurant"),
        id=order_id,
    )
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, order.branch)):
        return redirect("dashboard:home")
    return render(request, "dashboard/receipt.html", {"order": order})


# ── POS Inventory ────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def pos_inventory(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, branch)):
        return redirect("dashboard:home")

    if request.method == "POST":
        # AJAX bulk update: [{bi_id, stock}, ...]
        import json as _json2
        try:
            updates = _json2.loads(request.body)
        except Exception:
            return JsonResponse({"ok": False, "error": "bad json"}, status=400)
        for u in updates:
            try:
                bi = BranchItem.objects.get(id=int(u["bi_id"]), branch=branch)
                raw = u.get("stock")
                if raw == "" or raw is None:
                    bi.stock = None         # unlimited
                    bi.is_available = True
                else:
                    val = int(raw)
                    bi.stock = max(0, val)
                    bi.is_available = (bi.stock > 0)
                bi.save(update_fields=["stock", "is_available"])
            except Exception:
                continue
        return JsonResponse({"ok": True})

    # GET — load all branch items grouped by category
    categories = (
        BranchCategory.objects
        .filter(branch=branch, is_active=True)
        .select_related("category")
        .prefetch_related(
            _Prefetch(
                "items_in_category",
                queryset=BranchCategoryItem.objects.select_related(
                    "branch_item__item"
                ).order_by("sort_order"),
            )
        )
        .order_by("sort_order")
    )
    return render(request, "dashboard/pos_inventory.html", {
        "branch": branch,
        "categories": categories,
    })


# ── POS Report ───────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def pos_report(request, branch_id):
    from datetime import date as _date, datetime as _dt
    from django.db.models import Sum as _Sum, Q as _Q
    from django.db.models.functions import TruncDate
    from orders.models import ConstructorOrderItem

    branch = get_object_or_404(Branch, id=branch_id)
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, branch)):
        return redirect("dashboard:home")

    today = _date.today()
    date_from_str = request.GET.get("from", str(today))
    date_to_str   = request.GET.get("to",   str(today))
    try:
        date_from = _dt.strptime(date_from_str, "%Y-%m-%d").date()
        date_to   = _dt.strptime(date_to_str,   "%Y-%m-%d").date()
    except ValueError:
        date_from = date_to = today
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    base_qs = Order.objects.filter(
        branch=branch,
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    )

    # Закрытые (учитываются в выручке)
    closed = base_qs.filter(status=Order.Status.CLOSED)
    # Отменённые
    cancelled = base_qs.filter(status=Order.Status.CANCELLED)
    # Активные (ещё не закрыты)
    active = base_qs.filter(status__in=[
        Order.Status.NEW, Order.Status.ACCEPTED,
        Order.Status.COOKING, Order.Status.READY,
    ])

    # ── Выручка без стоимости доставки ──
    def _revenue(qs):
        agg = qs.aggregate(amt=_Sum("total_amount"), fee=_Sum("delivery_fee"))
        return (agg["amt"] or Decimal("0")) - (agg["fee"] or Decimal("0"))

    total_revenue   = _revenue(closed)
    total_orders    = closed.count()
    cancelled_count = cancelled.count()
    cancelled_sum   = _revenue(cancelled)

    # ── Онлайн vs Офлайн ──
    # Онлайн = заказ через QR-стол (table_place не null) или delivery/pickup
    online_qs  = closed.filter(
        _Q(table_place__isnull=False) |
        _Q(type__in=[Order.Type.DELIVERY, Order.Type.PICKUP])
    )
    offline_qs = closed.filter(
        table_place__isnull=True,
        type=Order.Type.DINE_IN,
    )
    online_revenue  = _revenue(online_qs)
    offline_revenue = _revenue(offline_qs)
    online_count    = online_qs.count()
    offline_count   = offline_qs.count()

    # ── По способу оплаты (тоже без доставки) ──
    pay_cash   = _revenue(closed.filter(payment_method="cash"))
    pay_online = _revenue(closed.filter(payment_method="online"))

    # ── Топ блюд (обычные + конструктор) ──
    regular_items = (
        OrderItem.objects
        .filter(order__in=closed)
        .values("item__name_ru")
        .annotate(total_qty=_Sum("qty"), total_rev=_Sum("line_total"))
    )
    cx_items = (
        ConstructorOrderItem.objects
        .filter(order__in=closed)
        .values("constructor_name_snapshot")
        .annotate(total_qty=_Sum("qty"), total_rev=_Sum("line_total"))
    )
    # объединяем в Python и сортируем
    top_items = []
    for r in regular_items:
        top_items.append({"name": r["item__name_ru"], "qty": r["total_qty"], "rev": r["total_rev"] or Decimal("0")})
    for r in cx_items:
        name = (r["constructor_name_snapshot"] or "Собери сам") + " 🧩"
        top_items.append({"name": name, "qty": r["total_qty"], "rev": r["total_rev"] or Decimal("0")})
    top_items.sort(key=lambda x: x["rev"], reverse=True)
    top_items = top_items[:20]

    # ── Разбивка по дням ──
    daily_raw = (
        closed
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(cnt=Count("id"), rev=_Sum("total_amount"), fee=_Sum("delivery_fee"))
        .order_by("day")
    )
    cancelled_daily = {
        row["day"]: row["cnt"]
        for row in cancelled
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(cnt=Count("id"))
    }
    online_daily = {
        row["day"]: row["cnt"]
        for row in online_qs
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(cnt=Count("id"))
    }
    offline_daily = {
        row["day"]: row["cnt"]
        for row in offline_qs
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(cnt=Count("id"))
    }
    daily = [
        {
            "day":       row["day"],
            "cnt":       row["cnt"],
            "rev":       (row["rev"] or Decimal("0")) - (row["fee"] or Decimal("0")),
            "cancelled": cancelled_daily.get(row["day"], 0),
            "online":    online_daily.get(row["day"], 0),
            "offline":   offline_daily.get(row["day"], 0),
        }
        for row in daily_raw
    ]

    return render(request, "dashboard/pos_report.html", {
        "branch":           branch,
        "date_from":        date_from,
        "date_to":          date_to,
        "total_revenue":    total_revenue,
        "total_orders":     total_orders,
        "cancelled_count":  cancelled_count,
        "cancelled_sum":    cancelled_sum,
        "online_revenue":   online_revenue,
        "offline_revenue":  offline_revenue,
        "online_count":     online_count,
        "offline_count":    offline_count,
        "pay_cash":         pay_cash,
        "pay_online_amt":   pay_online,
        "top_items":        top_items,
        "daily":            daily,
    })


# ── POS History ───────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def pos_history(request, branch_id):
    from datetime import date as _date, datetime as _dt
    branch = get_object_or_404(Branch, id=branch_id)
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, branch)):
        return redirect("dashboard:home")

    today = _date.today()
    date_str = request.GET.get("date", str(today))
    try:
        sel_date = _dt.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        sel_date = today

    orders = (
        Order.objects
        .filter(branch=branch, created_at__date=sel_date)
        .prefetch_related("items__item", "constructor_items")
        .order_by("-created_at")
    )

    return render(request, "dashboard/pos_history.html", {
        "branch":    branch,
        "orders":    orders,
        "sel_date":  sel_date,
        "today":     today,
    })


@require_POST
@login_required(login_url="dashboard:login")
def pos_order_cancel(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, order.branch)):
        return JsonResponse({"ok": False}, status=403)

    if order.status == Order.Status.CANCELLED:
        return JsonResponse({"ok": False, "error": "Уже отменён"})

    # Restore stock for closed POS orders
    if order.status == Order.Status.CLOSED:
        for oi in order.items.select_related("item").all():
            try:
                bi = BranchItem.objects.get(branch=order.branch, item=oi.item)
                if bi.stock is not None:
                    bi.stock += oi.qty
                    bi.is_available = True
                    bi.save(update_fields=["stock", "is_available"])
            except BranchItem.DoesNotExist:
                pass

    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])

    return JsonResponse({"ok": True})


# ── КОНСТРУКТОР БЛЮД ──────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def constructor_list(request, branch_id):
    from catalog.models import BranchItem
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:home")
    constructors = branch.dish_constructors.prefetch_related(
        "groups__ingredients__branch_item__item"
    ).order_by("sort_order", "id")
    branch_items = (
        BranchItem.objects.select_related("item")
        .filter(branch=branch, is_available=True)
        .order_by("item__name_ru")
    )
    return render(request, "dashboard/constructor.html", {
        "branch": branch,
        "constructors": constructors,
        "branch_items": branch_items,
    })


@require_POST
@login_required(login_url="dashboard:login")
def constructor_add(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return JsonResponse({"ok": False}, status=403)
    name       = request.POST.get("name", "").strip()
    base_price = request.POST.get("base_price", "0").strip() or "0"
    desc       = request.POST.get("description", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Введите название"})
    from decimal import InvalidOperation
    try:
        bp = Decimal(base_price)
    except InvalidOperation:
        bp = Decimal("0")
    cx = DishConstructor.objects.create(branch=branch, name=name, base_price=bp, description=desc)
    photo = request.FILES.get("photo")
    if photo:
        cx.photo = photo
        cx.save()
    return JsonResponse({"ok": True, "id": cx.id, "name": cx.name, "base_price": str(cx.base_price),
                         "photo_url": cx.photo.url if cx.photo else ""})


@require_POST
@login_required(login_url="dashboard:login")
def constructor_photo_update(request, cx_id):
    cx = get_object_or_404(DishConstructor, id=cx_id)
    if not _has_branch_access(request.user, cx.branch):
        return JsonResponse({"ok": False}, status=403)
    photo = request.FILES.get("photo")
    if not photo:
        return JsonResponse({"ok": False, "error": "Нет файла"})
    cx.photo = photo
    cx.save()
    return JsonResponse({"ok": True, "photo_url": cx.photo.url})


@require_POST
@login_required(login_url="dashboard:login")
def constructor_delete(request, cx_id):
    cx = get_object_or_404(DishConstructor, id=cx_id)
    if not _has_branch_access(request.user, cx.branch):
        return JsonResponse({"ok": False}, status=403)
    cx.delete()
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url="dashboard:login")
def constructor_toggle(request, cx_id):
    cx = get_object_or_404(DishConstructor, id=cx_id)
    if not _has_branch_access(request.user, cx.branch):
        return JsonResponse({"ok": False}, status=403)
    cx.is_active = not cx.is_active
    cx.save(update_fields=["is_active"])
    return JsonResponse({"ok": True, "is_active": cx.is_active})


@require_POST
@login_required(login_url="dashboard:login")
def constructor_group_add(request, cx_id):
    cx = get_object_or_404(DishConstructor, id=cx_id)
    if not _has_branch_access(request.user, cx.branch):
        return JsonResponse({"ok": False}, status=403)
    name       = request.POST.get("name", "").strip()
    min_select = int(request.POST.get("min_select", 1) or 1)
    max_select = int(request.POST.get("max_select", 1) or 1)
    if not name:
        return JsonResponse({"ok": False, "error": "Введите название группы"})
    g = ConstructorGroup.objects.create(constructor=cx, name=name, min_select=min_select, max_select=max_select)
    return JsonResponse({"ok": True, "id": g.id, "name": g.name, "min_select": g.min_select, "max_select": g.max_select})


@require_POST
@login_required(login_url="dashboard:login")
def constructor_group_delete(request, group_id):
    g = get_object_or_404(ConstructorGroup, id=group_id)
    if not _has_branch_access(request.user, g.constructor.branch):
        return JsonResponse({"ok": False}, status=403)
    g.delete()
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url="dashboard:login")
def constructor_ingredient_add(request, group_id):
    g = get_object_or_404(ConstructorGroup, id=group_id)
    if not _has_branch_access(request.user, g.constructor.branch):
        return JsonResponse({"ok": False}, status=403)
    name  = request.POST.get("name", "").strip()
    desc  = request.POST.get("description", "").strip()
    price_raw = request.POST.get("price", "0").strip() or "0"
    if not name:
        return JsonResponse({"ok": False, "error": "Введите название"})
    from decimal import InvalidOperation
    try:
        price = Decimal(price_raw)
    except InvalidOperation:
        price = Decimal("0")
    photo = request.FILES.get("photo")
    ing = ConstructorIngredient(group=g, name=name, description=desc, price=price)
    if photo:
        ing.photo = photo
    ing.save()
    return JsonResponse({"ok": True, "id": ing.id, "name": ing.name, "description": ing.description,
                         "price": str(ing.price), "photo_url": ing.photo.url if ing.photo else ""})


@require_POST
@login_required(login_url="dashboard:login")
def constructor_ingredient_from_menu(request, group_id):
    """Добавить позицию в категорию конструктора из существующего блюда меню."""
    from catalog.models import BranchItem
    g = get_object_or_404(ConstructorGroup, id=group_id)
    if not _has_branch_access(request.user, g.constructor.branch):
        return JsonResponse({"ok": False}, status=403)
    bi_id = request.POST.get("branch_item_id")
    bi = get_object_or_404(BranchItem, id=bi_id, branch=g.constructor.branch)
    # Не добавлять дублей
    if ConstructorIngredient.objects.filter(group=g, branch_item=bi).exists():
        return JsonResponse({"ok": False, "error": "Уже добавлено"})
    ing = ConstructorIngredient.objects.create(group=g, branch_item=bi)
    return JsonResponse({
        "ok": True,
        "id": ing.id,
        "name": ing.display_name,
        "description": ing.display_description,
        "price": str(ing.display_price),
        "photo_url": ing.display_photo_url,
    })


@require_POST
@login_required(login_url="dashboard:login")
def constructor_ingredient_delete(request, ing_id):
    ing = get_object_or_404(ConstructorIngredient, id=ing_id)
    if not _has_branch_access(request.user, ing.group.constructor.branch):
        return JsonResponse({"ok": False}, status=403)
    ing.delete()
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url="dashboard:login")
def constructor_ingredient_update(request, ing_id):
    """Обновить цену (и имя, если ручной) ингредиента."""
    ing = get_object_or_404(ConstructorIngredient, id=ing_id)
    if not _has_branch_access(request.user, ing.group.constructor.branch):
        return JsonResponse({"ok": False}, status=403)
    price_raw = request.POST.get("price", "").strip()
    if price_raw != "":
        try:
            ing.price = Decimal(price_raw)
        except Exception:
            return JsonResponse({"ok": False, "error": "Неверная цена"})
    if not ing.branch_item_id:
        name = request.POST.get("name", "").strip()
        if name:
            ing.name = name
    ing.save()
    return JsonResponse({"ok": True, "price": str(ing.display_price), "name": ing.display_name})


@require_POST
@login_required(login_url="dashboard:login")
def constructor_group_update(request, group_id):
    """Обновить min/max группы."""
    g = get_object_or_404(ConstructorGroup, id=group_id)
    if not _has_branch_access(request.user, g.constructor.branch):
        return JsonResponse({"ok": False}, status=403)
    try:
        min_s = int(request.POST.get("min_select", g.min_select))
        max_s = int(request.POST.get("max_select", g.max_select))
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "Неверные значения"})
    g.min_select = min_s
    g.max_select = max_s
    g.save()
    return JsonResponse({"ok": True, "min_select": g.min_select, "max_select": g.max_select})
