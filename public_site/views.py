from django.db.models import Q, F
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
from reservations.models import Booking, Floor, Place
from django.views.decorators.http import require_POST
from decimal import Decimal
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from core.models import Branch
from catalog.models import BranchItem
from pharmacy.models import Pharmacy
from .cart import set_qty, get_cart, cart_details
from .cart import add_to_cart as cart_add, set_qty, clear_cart, get_cart, cart_details

from django.utils.translation import gettext as _

from catalog.models import BranchItem  # или Item, как у тебя в url

from decimal import Decimal
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from decimal import Decimal

@require_POST
def add_to_cart(request, branch_item_id):
    bi = get_object_or_404(BranchItem, id=branch_item_id, is_available=True)

    qty = int(request.POST.get("qty") or 1)
    qty = max(1, min(qty, 99))

    # ✅ единая логика корзины
    cart_add(request, bi.branch_id, bi.id, qty)

    cart = get_cart(request, bi.branch_id)
    rows, subtotal, qty_total = cart_details(bi.branch, cart)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "qty": qty_total, "total": str(subtotal)})

    return redirect(request.META.get("HTTP_REFERER", "/"))



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
# ─────────────────────────────────────────────────────────────────────────────
# ЗАМЕНИ существующую функцию home() в public_site/views.py на эту.
# Все остальные функции оставь без изменений.
# ─────────────────────────────────────────────────────────────────────────────
#
# Добавь импорты в начало файла (если их ещё нет):
#   from django.views.decorators.cache import cache_page
#   from shops.models import Store, StoreBranch
#
# ─────────────────────────────────────────────────────────────────────────────

from shops.models import Store, StoreBranch
from core.models import Restaurant, Branch


# Категории платформы — добавляй новые строки когда запускаешь новое направление

# ─────────────────────────────────────────────────────────────────────────────
# ЗАМЕНИ существующую функцию home() в public_site/views.py на эту.
# Все остальные функции оставь без изменений.
# ─────────────────────────────────────────────────────────────────────────────
#
# Добавь импорты в начало файла (если их ещё нет):
#   from django.views.decorators.cache import cache_page
#   from shops.models import Store, StoreBranch
#
# ─────────────────────────────────────────────────────────────────────────────

from shops.models import Store, StoreBranch
from core.models import Restaurant, Branch, Banner


# Категории платформы — добавляй новые строки когда запускаешь новое направление
PLATFORM_CATEGORIES = [
    {
        "key":         "pharmacy",
        "icon":        "🏥",
        "name_ru":     "Аптеки",
        "name_ky":     "Дарыканалар",
        "name_en":     "Pharmacy",
        "url":         "pharmacy:pharmacy_list",
        "color":       "#FF00FB",
        "is_active":   True,
        "coming_soon": False,
    },
    {
        "key":         "restaurants",
        "icon":        "🍽️",
        "name_ru":     "Рестораны",
        "name_ky":     "Ресторандар",
        "name_en":     "Restaurants",
        "url":         "public_site:restaurants_list",
        "color":       "#FF5C00",
        "is_active":   True,
        "coming_soon": False,
    },
    {
        "key":         "stores",
        "icon":        "🛍️",
        "name_ru":     "Магазины",
        "name_ky":     "Дүкөндөр",
        "name_en":     "Shops",
        "url":         "shops:store_list",
        "color":       "#C83217",
        "is_active":   True,
        "coming_soon": False,
    },
    {
        "key":         "rinok",
        "icon":        "🛒",
        "name_ru":     "Рынки",
        "name_ky":     "Базарлар",
        "name_en":     "Markets",
        "url":         "markets:market_list",
        "color":       "#7C3AED",
        "is_active":   True,
        "coming_soon": False,
    },
    {
        "key":         "hotels",
        "icon":        "🏨",
        "name_ru":     "Отели",
        "name_ky":     "Мейманканалар",
        "name_en":     "Hotels",
        "url":         "hotels:hotel_list",
        "color":       "#2563EB",
        "is_active":   True,
        "coming_soon": False,
    },
    {
        "key":         "eco",
        "icon":        "♻️",
        "name_ru":     "Эко-проекты",
        "name_ky":     "Эко-долборлор",
        "name_en":     "Eco projects",
        "url":         None,
        "color":       "#059669",
        "is_active":   False,
        "coming_soon": True,
    },
    {
        "key":         "barbershop",
        "icon":        "✂️",
        "name_ru":     "Барбершопы",
        "name_ky":     "Барбершоптор",
        "name_en":     "Barbershops",
        "url":         "barbershop:index",
        "color":       "#b45309",
        "is_active":   True,
        "coming_soon": False,
    },

]


def home(request):
    """
    Главная страница Webordo.
    Публичная — без авторизации.
    """
    from markets.models import Market
    from hotels.models import Hotel
    from legal.models import LegalOrg
    from eco.models import EcoProject
    from agency.models import Agency
    from karaoke.models import KaraokeVenue
    from barbershop.models import Barbershop
    from printshop.models import PrintCenter
    from simracing.models import SimRacingVenue

    # ── РЕСТОРАНЫ ────────────────────────────────────────────────────────────
    top_restaurants = list(
        Restaurant.objects
        .filter(is_active=True, branches__is_active=True)
        .distinct()
        .only("id", "name_ru", "name_ky", "name_en", "slug", "logo", "rating")
        .prefetch_related("branches")
        .order_by("-rating", "name_ru")[:8]
    )
    restaurant_cards = []
    for r in top_restaurants:
        branches = [b for b in r.branches.all() if b.is_active]
        is_open = any(b.is_open_now() for b in branches)
        has_delivery = any(b.delivery_enabled for b in branches)
        restaurant_cards.append({
            "obj": r, "is_open": is_open, "has_delivery": has_delivery,
        })

    # ── МАГАЗИНЫ ─────────────────────────────────────────────────────────────
    top_stores = list(
        Store.objects
        .filter(is_active=True, branches__is_active=True)
        .distinct()
        .only("id", "name_ru", "slug", "logo")
        .prefetch_related("branches")
        .order_by("name_ru")[:8]
    )
    store_cards = []
    for s in top_stores:
        branches = [b for b in s.branches.all() if b.is_active]
        has_delivery = any(b.delivery_enabled for b in branches)
        store_cards.append({"obj": s, "has_delivery": has_delivery})

    # ── РЫНКИ ────────────────────────────────────────────────────────────────
    market_cards = list(
        Market.objects.filter(is_active=True).order_by("sort_order", "name_ru")[:8]
    )

    # ── ОТЕЛИ ────────────────────────────────────────────────────────────────
    hotel_cards = list(
        Hotel.objects.filter(is_active=True, branches__is_active=True)
        .distinct()
        .prefetch_related("branches")
        .order_by("-rating", "name_ru")[:8]
    )

    # ── АПТЕКИ ───────────────────────────────────────────────────────────────
    pharmacy_cards = list(
        Pharmacy.objects.filter(is_active=True).order_by("name_ru")[:8]
    )

    # ── ЮРИСТЫ ───────────────────────────────────────────────────────────────
    legal_cards = list(
        LegalOrg.objects.filter(is_active=True).order_by("sort_order", "name")[:8]
    )

    # ── ЭКО-ПРОЕКТЫ ──────────────────────────────────────────────────────────
    eco_cards = list(
        EcoProject.objects.filter(is_active=True).order_by("sort_order", "name")[:8]
    )

    # ── IT АГЕНТСТВА ─────────────────────────────────────────────────────────
    agency_cards = list(
        Agency.objects.filter(is_active=True).order_by("sort_order", "name")[:8]
    )

    # ── KARAOKE ───────────────────────────────────────────────────────────────
    karaoke_cards = list(
        KaraokeVenue.objects.filter(is_active=True).order_by("sort_order", "name")[:12]
    )

    # ── СИМРЕЙСИНГ ───────────────────────────────────────────────────────────
    simracing_cards = list(
        SimRacingVenue.objects.filter(is_active=True).order_by("sort_order", "name")[:12]
    )

    # ── БАРБЕРШОПЫ ────────────────────────────────────────────────────────────
    barbershop_cards = list(
        Barbershop.objects.filter(is_active=True).order_by("sort_order", "name")[:12]
    )

    # ── ПОЛИГРАФИЯ ───────────────────────────────────────────────────────────
    printshop_cards = list(
        PrintCenter.objects.filter(is_active=True, branches__is_active=True)
        .distinct()
        .prefetch_related("branches")
        .order_by("name_ru")[:12]
    )

    # ── СТАТИСТИКА ────────────────────────────────────────────────────────────
    stats = {
        "restaurant_count": Restaurant.objects.filter(is_active=True).count(),
        "store_count":      Store.objects.filter(is_active=True).count(),
        "pharmacy_count":   Pharmacy.objects.filter(is_active=True).count(),
        "market_count":     Market.objects.filter(is_active=True).count(),
        "hotel_count":      Hotel.objects.filter(is_active=True).count(),
        "legal_count":      LegalOrg.objects.filter(is_active=True).count(),
        "eco_count":        EcoProject.objects.filter(is_active=True).count(),
        "agency_count":     Agency.objects.filter(is_active=True).count(),
        "karaoke_count":      KaraokeVenue.objects.filter(is_active=True).count(),
        "simracing_count":    SimRacingVenue.objects.filter(is_active=True).count(),
        "barbershop_count":   Barbershop.objects.filter(is_active=True).count(),
        "printshop_count":    PrintCenter.objects.filter(is_active=True).count(),
        "branch_count": (
            Branch.objects.filter(is_active=True).count()
            + StoreBranch.objects.filter(is_active=True).count()
        ),
    }
    stats["total"] = (
        stats["restaurant_count"] + stats["store_count"] + stats["pharmacy_count"]
        + stats["market_count"] + stats["hotel_count"] + stats["legal_count"]
        + stats["eco_count"] + stats["agency_count"] + stats["karaoke_count"]
        + stats["simracing_count"] + stats["barbershop_count"] + stats["printshop_count"]
    )

    try:
        from django.urls import reverse
        ad_banners = [
            {
                "obj": b,
                "click_url": reverse("public_site:banner_click", args=[b.id]) if b.link_url else "",
            }
            for b in Banner.objects.filter(is_active=True).order_by("sort_order")
        ]
    except Exception:
        ad_banners = []

    # ── КАРТА: все точки бизнесов ────────────────────────────────────────────
    import json as _json
    map_points = []
    from django.urls import reverse
    for b in Branch.objects.filter(is_active=True, lat__isnull=False, lon__isnull=False).select_related("restaurant"):
        try:
            url = reverse("public_site:restaurant_contacts", kwargs={"slug": b.restaurant.slug})
        except Exception:
            url = f"/ru/r/{b.restaurant.slug}/contacts/"
        map_points.append({
            "lat":   float(b.lat),
            "lon":   float(b.lon),
            "name":  b.name_ru,
            "biz":   b.restaurant.name_ru,
            "type":  "restaurant",
            "icon":  "🍽",
            "addr":  b.address,
            "url":   url,
        })
    for b in StoreBranch.objects.filter(is_active=True, lat__isnull=False, lon__isnull=False).select_related("store"):
        try:
            url = reverse("shops:store_detail", kwargs={"slug": b.store.slug})
        except Exception:
            url = f"/ru/shops/{b.store.slug}/"
        map_points.append({
            "lat":   float(b.lat),
            "lon":   float(b.lon),
            "name":  b.name_ru,
            "biz":   b.store.name_ru,
            "type":  "store",
            "icon":  "🏪",
            "addr":  b.address,
            "url":   url,
        })

    return render(request, "public_site/home.html", {
        "categories":       PLATFORM_CATEGORIES,
        "restaurant_cards": restaurant_cards,
        "store_cards":      store_cards,
        "market_cards":     market_cards,
        "ad_banners":       ad_banners,
        "hotel_cards":      hotel_cards,
        "pharmacy_cards":   pharmacy_cards,
        "legal_cards":      legal_cards,
        "eco_cards":        eco_cards,
        "agency_cards":     agency_cards,
        "karaoke_cards":      karaoke_cards,
        "simracing_cards":    simracing_cards,
        "barbershop_cards":   barbershop_cards,
        "printshop_cards":    printshop_cards,
        "stats":            stats,
        "map_points_json":  _json.dumps(map_points, ensure_ascii=False),
    })



def restaurants_list(request):
    """
    GET /restaurants/
    Страница со списком всех ресторанов платформы.
    Публичная — без авторизации.
    Поиск (?q=...) и фильтр ?open_now=1.
    """
    q        = (request.GET.get("q") or "").strip()
    open_now = request.GET.get("open_now") == "1"

    qs = (
        Restaurant.objects
        .filter(is_active=True)
        .prefetch_related("branches")
        .order_by("-rating", "name_ru")
    )

    if q:
        qs = qs.filter(Q(name_ru__icontains=q) | Q(name_ky__icontains=q) | Q(name_en__icontains=q))

    cards = []
    for r in qs:
        branches = [b for b in r.branches.all() if b.is_active]
        if not branches:
            continue

        is_open = any(b.is_open_now() for b in branches)
        if open_now and not is_open:
            continue

        delivery_branches  = [b for b in branches if b.delivery_enabled]
        has_delivery       = bool(delivery_branches)
        min_order          = min((b.min_order_amount for b in delivery_branches), default=None)
        min_fee            = min((b.delivery_fee    for b in delivery_branches), default=None)
        free_delivery_from = min(
            (b.free_delivery_from for b in delivery_branches if b.free_delivery_from and b.free_delivery_from > 0),
            default=None
        )
        promo_photo = next(
            (b.promo_photo for b in branches if b.promo_photo),
            None
        )

        # Время работы — показываем только если у всех филиалов одинаково
        hours_text = None
        hours_set  = set()
        for b in branches:
            if b.is_open_24h:
                hours_set.add("24/7")
            elif b.open_time and b.close_time:
                hours_set.add(f"{b.open_time.strftime('%H:%M')}–{b.close_time.strftime('%H:%M')}")
        if len(hours_set) == 1:
            hours_text = list(hours_set)[0]

        # Cover photo: берём первый филиал с cover_photo
        cover = None
        for b in branches:
            if b.cover_photo:
                cover = b.cover_photo
                break

        cards.append({
            "obj":               r,
            "is_open":           is_open,
            "has_delivery":      has_delivery,
            "min_order":         min_order,
            "min_fee":           min_fee,
            "free_delivery_from": free_delivery_from,
            "hours_text":        hours_text,
            "branches_count":    len(branches),
            "cover":             cover,
            "promo_photo":       promo_photo,
        })

    promo_cards = [c for c in cards if c["promo_photo"]]
    return render(request, "public_site/restaurants_list.html", {
        "cards":       cards,
        "promo_cards": promo_cards,
        "q":           q,
        "open_now":    open_now,
        "total":       len(cards),
    })
def restaurant_detail(request, slug):
    restaurant = get_object_or_404(Restaurant, slug=slug, is_active=True)
    branches = restaurant.branches.filter(is_active=True).order_by("name_ru")
    return render(request, "public_site/restaurant_detail.html", {"restaurant": restaurant, "branches": branches})



def _calc_delivery(branch, subtotal: Decimal) -> Decimal:
    """Реальная стоимость доставки с учётом акции бесплатной доставки."""
    if not branch.delivery_enabled:
        return Decimal("0")
    free_from = branch.free_delivery_from or Decimal("0")
    if free_from > 0 and subtotal >= free_from:
        return Decimal("0")
    return branch.delivery_fee or Decimal("0")


def _build_branch_menu_context(request, branch):
    """Shared logic for branch menu views."""
    from django.db.models import Prefetch
    from catalog.models import DishConstructor
    rows_prefetch = Prefetch(
        "items_in_category",
        queryset=BranchCategoryItem.objects
            .select_related("branch_item__item")
            .filter(branch_item__is_available=True)
            .order_by("sort_order", "-branch_item__item__order_count", "id"),
        to_attr="prefetched_items",
    )
    categories = list(
        BranchCategory.objects
        .filter(branch=branch, is_active=True)
        .prefetch_related(rows_prefetch)
        .order_by("sort_order", "id")
    )
    menu = []
    for bc in categories:
        if bc.prefetched_items:
            menu.append({"branch_category": bc, "items": bc.prefetched_items})

    # Конструкторы — только если есть активные с ингредиентами
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

    cart = get_cart(request, branch.id)
    _, subtotal, qty_total = cart_details(branch, cart)

    cx_cart = _get_branch_cx_cart(request, branch.id)
    cx_total = sum(Decimal(str(item["unit_price"])) * int(item["qty"]) for item in cx_cart)
    cx_qty = sum(int(item["qty"]) for item in cx_cart)

    return {
        "branch": branch,
        "menu": menu,
        "constructors": constructors,
        "cart_qty": qty_total + cx_qty,
        "cart_total": subtotal + cx_total,
    }


def branch_menu(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    ctx = _build_branch_menu_context(request, branch)
    return render(request, "public_site/branch_menu.html", ctx)


def restaurant_branch_menu(request, restaurant_slug: str, branch_id: int):
    """Clean URL: /restaurant-slug/<branch_id>/"""
    branch = get_object_or_404(
        Branch, id=branch_id,
        restaurant__slug=restaurant_slug,
        is_active=True,
    )
    ctx = _build_branch_menu_context(request, branch)
    ctx["restaurant_slug"] = restaurant_slug  # for back link in template
    return render(request, "public_site/branch_menu.html", ctx)



def cart_json(request, branch_id: int):
    """AJAX: вернуть содержимое корзины как JSON для модального окна."""
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    cart = get_cart(request, branch.id)
    rows, subtotal, qty_total = cart_details(branch, cart)

    from django.urls import reverse
    items = []
    for r in rows:
        bi = r["branch_item"]
        items.append({
            "bi_id":       bi.id,
            "name":        bi.item.name_ru,
            "price":       str(bi.price),
            "qty":         r["qty"],
            "line_total":  str(r["line_total"]),
            "update_url":  reverse("public_site:cart_update", args=[branch_id, bi.id]),
        })

    # Позиции из конструктора
    cx_cart = _get_branch_cx_cart(request, branch_id)
    cx_items = []
    cx_total = Decimal("0")
    cx_qty = 0
    for item in cx_cart:
        unit = Decimal(str(item["unit_price"]))
        qty  = int(item["qty"])
        line = unit * qty
        cx_total += line
        cx_qty   += qty
        detail = " · ".join(
            f"{s['gname']}: {', '.join(i['name'] for i in s.get('ings', []))}"
            for s in item.get("selections", [])
        )
        cx_items.append({
            "cx_idx":     item["idx"],
            "name":       item["cx_name"],
            "detail":     detail,
            "selections": [
                {"gname": s["gname"], "ings": [i["name"] for i in s.get("ings", [])]}
                for s in item.get("selections", [])
            ],
            "price":      str(unit),
            "qty":        qty,
            "line_total": str(line),
        })

    total_subtotal = subtotal + cx_total
    delivery_fee = _calc_delivery(branch, total_subtotal)
    total = total_subtotal + delivery_fee
    free_from = branch.free_delivery_from or Decimal("0")

    return JsonResponse({
        "ok":               True,
        "items":            items,
        "cx_items":         cx_items,
        "subtotal":         str(total_subtotal),
        "delivery_fee":     str(delivery_fee),
        "delivery_enabled": branch.delivery_enabled,
        "total":            str(total),
        "qty_total":        qty_total + cx_qty,
        "min_order_amount": str(branch.min_order_amount),
        "free_from":        str(free_from),
        "free_delivery_reached": delivery_fee == 0 and free_from > 0 and branch.delivery_enabled,
    })


def cart_detail(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    cart = get_cart(request, branch.id)
    rows, subtotal, qty_total = cart_details(branch, cart)

    cx_cart = _get_branch_cx_cart(request, branch_id)
    cx_qty = sum(int(x["qty"]) for x in cx_cart)
    cx_subtotal = sum(Decimal(str(x["unit_price"])) * int(x["qty"]) for x in cx_cart)

    delivery_fee = branch.delivery_fee if branch.delivery_enabled else Decimal("0")
    full_subtotal = subtotal + cx_subtotal
    total = full_subtotal + delivery_fee

    return render(request, "public_site/cart_detail.html", {
        "branch": branch,
        "rows": rows,
        "qty_total": qty_total + cx_qty,
        "subtotal": full_subtotal,
        "delivery_fee": delivery_fee,
        "total": total,
    })

from decimal import Decimal
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from core.models import Branch
from catalog.models import BranchItem
from .cart import set_qty, get_cart, cart_details

@require_POST
def cart_update(request, branch_id: int, branch_item_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)

    qty = int(request.POST.get("qty") or 0)
    qty = max(0, min(qty, 99))

    # применяем
    set_qty(request, branch.id, branch_item_id, qty)

    # считаем заново
    cart = get_cart(request, branch.id)
    rows, subtotal, qty_total = cart_details(branch, cart)

    delivery_fee = _calc_delivery(branch, subtotal)
    total = subtotal + delivery_fee
    free_from = branch.free_delivery_from or Decimal("0")

    # строка конкретного товара
    row_qty = 0
    line_total = Decimal("0")
    for r in rows:
        if r["branch_item"].id == branch_item_id:
            row_qty = int(r["qty"])
            line_total = r["line_total"]
            break

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "ok":           True,
            "row_qty":      row_qty,
            "line_total":   str(line_total),
            "subtotal":     str(subtotal),
            "delivery_fee": str(delivery_fee),
            "total":        str(total),
            "qty_total":    qty_total,
            "free_from":    str(free_from),
            "free_delivery_reached": delivery_fee == 0 and free_from > 0 and branch.delivery_enabled,
        })

    return redirect("public_site:cart_detail", branch_id=branch.id)


@require_POST
def cart_remove(request, branch_id: int, branch_item_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    bi = get_object_or_404(BranchItem, id=branch_item_id, branch=branch)

    set_qty(request, branch.id, bi.id, 0)

    cart = get_cart(request, branch.id)
    rows, subtotal, qty_total = cart_details(branch, cart)

    delivery_fee = branch.delivery_fee if branch.delivery_enabled else Decimal("0")
    total = subtotal + delivery_fee

    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    if is_ajax:
        return JsonResponse({
            "ok": True,
            "row_qty": 0,
            "line_total": "0",
            "subtotal": str(subtotal),
            "delivery_fee": str(delivery_fee),
            "total": str(total),
            "qty_total": qty_total,
        })

    return redirect("public_site:cart_detail", branch_id=branch.id)

from urllib.parse import quote
from decimal import Decimal
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.models import Branch
from orders.models import Order, OrderItem
from .cart import get_cart, cart_details, clear_cart

@require_POST
def checkout(request, branch_id: int):
    from django.db import transaction as db_transaction
    from catalog.models import DishConstructor
    from orders.models import ConstructorOrderItem
    branch = get_object_or_404(
        Branch.objects.select_related("restaurant"),
        id=branch_id, is_active=True,
    )
    cart = get_cart(request, branch.id)
    rows, subtotal, qty_total = cart_details(branch, cart)
    cx_cart = _get_branch_cx_cart(request, branch_id)
    cx_qty = sum(int(x["qty"]) for x in cx_cart)

    if qty_total == 0 and cx_qty == 0:
        messages.error(request, _("Корзина пуста."))
        return redirect("public_site:cart_detail", branch_id=branch.id)

    name = (request.POST.get("name") or "").strip()
    phone = (request.POST.get("phone") or "").strip()
    address = (request.POST.get("address") or "").strip()
    comment = (request.POST.get("comment") or "").strip()

    # обязательные поля
    if not name:
        messages.error(request, _("Укажите ваше имя."))
        return redirect("public_site:cart_detail", branch_id=branch.id)
    if not phone:
        messages.error(request, _("Укажите телефон."))
        return redirect("public_site:cart_detail", branch_id=branch.id)
    if not address:
        messages.error(request, _("Укажите адрес / стол / кабинку."))
        return redirect("public_site:cart_detail", branch_id=branch.id)

    payment_method = request.POST.get("payment_method") or Order.PaymentMethod.CASH
    if payment_method not in [Order.PaymentMethod.CASH, Order.PaymentMethod.ONLINE]:
        payment_method = Order.PaymentMethod.CASH

    # если у филиала есть доставка — считаем как доставка, иначе самовывоз
    order_type = Order.Type.DELIVERY if branch.delivery_enabled else Order.Type.PICKUP

    # полный подытог = обычные блюда + конструктор
    cx_subtotal = sum(Decimal(str(x["unit_price"])) * int(x["qty"]) for x in cx_cart)
    full_subtotal = subtotal + cx_subtotal

    # проверка минималки только для доставки
    if order_type == Order.Type.DELIVERY and full_subtotal < branch.min_order_amount:
        messages.error(
            request,
            _("Минимальная сумма заказа для доставки: %(min)s") % {"min": branch.min_order_amount}
        )
        return redirect("public_site:cart_detail", branch_id=branch.id)

    if order_type == Order.Type.DELIVERY:
        free_from = branch.free_delivery_from or Decimal("0")
        if free_from > 0 and full_subtotal >= free_from:
            delivery_fee = Decimal("0")
        else:
            delivery_fee = branch.delivery_fee
    else:
        delivery_fee = Decimal("0")

    # промокод
    from core.models import PromoCode
    promo_code_str = (request.POST.get("promo_code") or "").strip().upper()
    promo = None
    promo_discount = Decimal("0")
    promo_msg_line = ""
    if promo_code_str:
        try:
            promo = PromoCode.objects.get(branch=branch, code=promo_code_str)
            valid, _ = promo.is_valid()
            if valid:
                if promo.discount_type == PromoCode.DiscountType.FREE_DELIVERY:
                    delivery_fee = Decimal("0")
                    promo_msg_line = f"Промокод {promo.code}: бесплатная доставка"
                elif promo.discount_type == PromoCode.DiscountType.PERCENT:
                    promo_discount = (full_subtotal * promo.discount_value / Decimal("100")).quantize(Decimal("1"))
                    promo_msg_line = f"Промокод {promo.code}: −{promo.discount_value}% (−{promo_discount} сом)"
                elif promo.discount_type == PromoCode.DiscountType.FIXED:
                    promo_discount = min(promo.discount_value, full_subtotal)
                    promo_msg_line = f"Промокод {promo.code}: −{promo_discount} сом"
            else:
                promo = None
        except PromoCode.DoesNotExist:
            promo = None

    total = full_subtotal - promo_discount + delivery_fee

    # Весь блок — одна транзакция
    with db_transaction.atomic():
        order = Order.objects.create(
            branch=branch,
            type=order_type,
            status=Order.Status.NEW,
            customer_name=name,
            customer_phone=phone,
            delivery_address=address,
            comment=comment,
            total_amount=total,
            delivery_fee=delivery_fee,
            payment_method=payment_method,
            payment_status=Order.PaymentStatus.UNPAID,
        )

        # увеличиваем рейтинг ресторана (cap 9.9 — max_digits=3,decimal_places=1)
        from django.db.models import Case, When, Value
        Restaurant.objects.filter(pk=branch.restaurant_id).update(
            rating=Case(
                When(rating__lt=Decimal("9.8"), then=F("rating") + Decimal("0.1")),
                default=Decimal("9.9"),
            )
        )

        # учитываем использование промокода
        if promo:
            PromoCode.objects.filter(pk=promo.pk).update(used_count=F("used_count") + 1)

        # сохраняем обычные позиции
        lines = []
        for i, r in enumerate(rows, start=1):
            bi = r["branch_item"]
            qty = r["qty"]
            line_total = bi.price * qty
            OrderItem.objects.create(
                order=order,
                item=bi.item,
                qty=qty,
                price_snapshot=bi.price,
                line_total=line_total,
            )
            item_name = getattr(bi.item, "name_ru", None) or str(bi.item)
            lines.append(f"{i}) {item_name} × {qty} = {line_total} сом")

        # сохраняем позиции конструктора
        for cx_item in cx_cart:
            qty = int(cx_item["qty"])
            unit_price = Decimal(str(cx_item["unit_price"]))
            line_total = unit_price * qty
            cx_obj = DishConstructor.objects.filter(id=cx_item["cx_id"]).first()
            if cx_obj:
                ConstructorOrderItem.objects.create(
                    order=order,
                    constructor=cx_obj,
                    constructor_name_snapshot=cx_item["cx_name"],
                    qty=qty,
                    unit_price=unit_price,
                    line_total=line_total,
                    ingredients_snapshot=cx_item.get("selections", []),
                )
            n = len(lines) + 1
            detail_parts = [
                f"  • {s['gname']}: {', '.join(i['name'] for i in s.get('ings', []))}"
                for s in cx_item.get("selections", [])
            ]
            entry = f"{n}) 🧩 {cx_item['cx_name']} × {qty} = {line_total} сом"
            if detail_parts:
                entry += "\n" + "\n".join(detail_parts)
            lines.append(entry)

    # очищаем обе корзины
    clear_cart(request, branch.id)
    _save_branch_cx_cart(request, branch_id, [])

    # готовим сообщение
    type_text = "Доставка" if order_type == Order.Type.DELIVERY else "Самовывоз"
    msg = (
        f"🧾 Новый заказ #{order.id}\n"
        f"Филиал: {branch.name_ru}\n"
        f"Тип: {type_text}\n"
        f"Имя: {name}\n"
        f"Телефон: {phone}\n"
        f"Адрес/стол: {address}\n"
    )
    if comment:
        msg += f"Комментарий: {comment}\n"

    msg += "\nСостав:\n" + "\n".join(lines) + "\n"
    msg += f"\nПодытог: {full_subtotal} сом"
    if promo_msg_line:
        msg += f"\n{promo_msg_line}"
    if order_type == Order.Type.DELIVERY:
        msg += f"\nДоставка: {delivery_fee} сом"
    msg += f"\nИтого: {total} сом"

    # Редирект в WhatsApp / WhatsApp Business:
    # приоритет: whatsapp ресторана → телефон филиала → телефон ресторана
    wa_raw = (
        branch.restaurant.whatsapp
        or branch.phone
        or branch.restaurant.phone
        or ""
    )
    wa_number = "".join(ch for ch in wa_raw if ch.isdigit())
    if wa_number:
        # wa.me открывает и обычный WhatsApp, и WhatsApp Business — какое приложение установлено
        whatsapp_url = f"https://wa.me/{wa_number}?text={quote(msg)}"
        return redirect(whatsapp_url)

    # если номера нет — страница успеха
    return redirect("public_site:checkout_success", branch_id=branch.id, order_id=order.id)

from urllib.parse import quote
from django.shortcuts import get_object_or_404, render
from orders.models import Order, OrderItem, ConstructorOrderItem
from core.models import Branch

def checkout_success(request, branch_id: int, order_id: int):
    branch = get_object_or_404(
        Branch.objects.select_related("restaurant"),
        id=branch_id, is_active=True,
    )
    order = get_object_or_404(Order, id=order_id, branch=branch)

    items = (OrderItem.objects
             .filter(order=order)
             .select_related("item")
             .order_by("id"))

    cx_items = (ConstructorOrderItem.objects
                .filter(order=order)
                .order_by("id"))

    lines = []
    subtotal = Decimal("0")

    preview_lines = []
    items_count = 0

    for i, oi in enumerate(items, start=1):
        name = getattr(oi.item, "name_ru", None) or str(oi.item)
        line = f"{i}) {name} × {oi.qty} = {oi.line_total} сом"
        lines.append(line)

        subtotal += oi.line_total
        items_count += 1

        # preview: 1–2 строки
        if len(preview_lines) < 2:
            preview_lines.append(f"{name} × {oi.qty}")

    for coi in cx_items:
        n = len(lines) + 1
        cx_name = coi.constructor_name_snapshot
        detail_parts = [
            f"  • {s['gname']}: {', '.join(i['name'] for i in s.get('ings', []))}"
            for s in (coi.ingredients_snapshot or [])
        ]
        entry = f"{n}) 🧩 {cx_name} × {coi.qty} = {coi.line_total} сом"
        if detail_parts:
            entry += "\n" + "\n".join(detail_parts)
        lines.append(entry)
        subtotal += coi.line_total
        items_count += 1
        if len(preview_lines) < 2:
            preview_lines.append(f"🧩 {cx_name} × {coi.qty}")

    is_delivery = (order.type == Order.Type.DELIVERY)
    delivery_fee = branch.delivery_fee if (is_delivery and branch.delivery_enabled) else Decimal("0")
    total = order.total_amount

    payment_map = {
        Order.PaymentMethod.CASH: "Наличные",
        Order.PaymentMethod.ONLINE: "Онлайн",
    }
    payment_text = payment_map.get(order.payment_method, "Наличные")
    type_text = "Доставка" if is_delivery else "Самовывоз"

    msg = (
        f"🧾 Новый заказ #{order.id}\n"
        f"Филиал: {branch.name_ru}\n"
        f"Тип: {type_text}\n"
        f"Имя: {order.customer_name}\n"
        f"Телефон: {order.customer_phone}\n"
        f"Адрес/стол: {order.delivery_address}\n"
        f"Оплата: {payment_text}\n"
    )
    if getattr(order, "comment", ""):
        msg += f"Комментарий: {order.comment}\n"

    msg += "\nСостав:\n" + "\n".join(lines)
    msg += f"\n\nПодытог: {subtotal} сом"
    if is_delivery:
        msg += f"\nДоставка: {delivery_fee} сом"
    msg += f"\nИтого: {total} сом"

    encoded = quote(msg)

    wa_raw = (
        branch.restaurant.whatsapp
        or branch.phone
        or branch.restaurant.phone
        or ""
    )
    wa_number = "".join(ch for ch in wa_raw if ch.isdigit())

    whatsapp_web_url = f"https://wa.me/{wa_number}?text={encoded}" if wa_number else f"https://wa.me/?text={encoded}"
    whatsapp_deeplink = f"whatsapp://send?phone={wa_number}&text={encoded}" if wa_number else f"whatsapp://send?text={encoded}"

    call_url = f"tel:{branch.phone}" if branch.phone else ""

    return render(request, "public_site/checkout_success.html", {
        "branch": branch,
        "order": order,
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "total": total,
        "whatsapp_url": whatsapp_web_url,
        "whatsapp_deeplink": whatsapp_deeplink,
        "call_url": call_url,
        "is_delivery": is_delivery,
        "items_preview": preview_lines,
        "items_count": items_count,
        "msg_text": msg,  # для копирования
    })





def about(request):
    return render(request, "public_site/about.html")


def privacy(request):
    return render(request, "public_site/privacy.html")

from django.db.models import Prefetch
from core.models import Restaurant, Branch

def contacts(request):
    restaurants = (
        Restaurant.objects.filter(is_active=True)
        .prefetch_related(
            Prefetch(
                "branches",
                queryset=Branch.objects.filter(is_active=True).order_by("name_ru"),
            )
        )
        .order_by("-rating", "name_ru")
    )
    return render(request, "public_site/contacts.html", {"restaurants": restaurants})


def reservation(request):
    return render(request, "public_site/reservation.html")





from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

def hall_plan(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    floors = Floor.objects.filter(branch=branch, is_active=True).prefetch_related("places").order_by("sort_order","id")

    busy_ids = set(
        Booking.objects.filter(branch=branch, status__in=[Booking.Status.ACTIVE, Booking.Status.ARRIVED])
        .values_list("place_id", flat=True)
    )

    floors_data = []
    for f in floors:
        places = []
        for p in f.places.filter(is_active=True):
            places.append({"obj": p, "busy": p.id in busy_ids})
        floors_data.append({"floor": f, "places": places})

    return render(request, "public_site/hall_plan.html", {
        "branch": branch,
        "floors_data": floors_data,
    })

@require_POST
@login_required
def place_move(request, place_id: int):
    p = get_object_or_404(Place, id=place_id, is_active=True)
    try:
        x = int(request.POST.get("x"))
        y = int(request.POST.get("y"))
    except:
        return JsonResponse({"ok": False}, status=400)

    p.x = max(0, min(x, 2000))
    p.y = max(0, min(y, 2000))
    p.save(update_fields=["x","y","updated_at"])
    return JsonResponse({"ok": True, "x": p.x, "y": p.y})

@require_POST
@login_required
def booking_set_status(request, booking_id: int, status: str):
    booking = get_object_or_404(Booking, id=booking_id)
    allowed = {Booking.Status.ACTIVE, Booking.Status.ARRIVED, Booking.Status.CLEARED, Booking.Status.CANCELLED}
    if status not in allowed:
        return JsonResponse({"ok": False}, status=400)
    booking.status = status
    booking.save(update_fields=["status","updated_at"])
    return redirect(request.META.get("HTTP_REFERER", "/"))


from django.shortcuts import render, get_object_or_404
from core.models import Restaurant

def restaurant_contacts(request, slug: str):
    restaurant = get_object_or_404(Restaurant, slug=slug, is_active=True)
    branches = restaurant.branches.filter(is_active=True).order_by("name_ru")

    return render(request, "public_site/restaurant_contacts.html", {
        "restaurant": restaurant,
        "branches": branches,
    })

from django.shortcuts import render, get_object_or_404
from core.models import Restaurant

def restaurant_about(request, slug: str):
    restaurant = get_object_or_404(Restaurant, slug=slug, is_active=True)
    return render(request, "public_site/restaurant_about.html", {"restaurant": restaurant})


@require_POST
def validate_promo(request, branch_id: int):
    from core.models import PromoCode
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    code = (request.POST.get("code") or "").strip().upper()

    if not code:
        return JsonResponse({"ok": False, "error": "Введите промокод"})

    try:
        promo = PromoCode.objects.get(branch=branch, code=code)
    except PromoCode.DoesNotExist:
                                
        return JsonResponse({"ok": False, "error": "Промокод не найден"})

    valid, reason = promo.is_valid()
    if not valid:
        return JsonResponse({"ok": False, "error": reason})

    return JsonResponse({
        "ok": True,
        "discount_type": promo.discount_type,
        "discount_value": str(promo.discount_value),
        "label": promo.get_discount_type_display(),
    })


def banner_click(request, banner_id: int):
    """Считает клик и редиректит на целевой URL баннера."""
    from django.http import HttpResponseRedirect, HttpResponseNotFound
    from django.db.models import F

    try:
        banner = Banner.objects.filter(id=banner_id, is_active=True).only("link_url").get()
    except Banner.DoesNotExist:
        return HttpResponseNotFound()

    Banner.objects.filter(id=banner_id).update(click_count=F("click_count") + 1)

    if banner.link_url:
        return HttpResponseRedirect(banner.link_url)
    return HttpResponseRedirect("/")


# ── КОНСТРУКТОР БЛЮД (ветка branch_menu) ──────────────────────────────────────

def _cx_cart_key(branch_id: int) -> str:
    return f"cx_cart_{branch_id}"


def _get_branch_cx_cart(request, branch_id: int) -> list:
    return request.session.get(_cx_cart_key(branch_id), [])


def _save_branch_cx_cart(request, branch_id: int, cart: list):
    request.session[_cx_cart_key(branch_id)] = cart
    request.session.modified = True


@require_POST
def constructor_cx_update(request, branch_id: int):
    """Inc/dec/remove constructor cart item for branch menu."""
    idx    = int(request.POST.get("idx") or -1)
    action = (request.POST.get("action") or "").strip()

    cart = _get_branch_cx_cart(request, branch_id)
    item = next((x for x in cart if x["idx"] == idx), None)
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
        cart = [x for x in cart if x["idx"] != idx]
        new_line = Decimal("0")
        new_qty  = 0
    else:
        new_line = unit_price * new_qty
        item["line_total"] = str(new_line)

    _save_branch_cx_cart(request, branch_id, cart)

    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    reg_cart = get_cart(request, branch_id)
    _, reg_subtotal, reg_qty = cart_details(branch, reg_cart)
    cx_total = sum(Decimal(str(x["unit_price"])) * int(x["qty"]) for x in cart)
    cx_qty   = sum(int(x["qty"]) for x in cart)

    total_sub = reg_subtotal + cx_total
    delivery  = _calc_delivery(branch, total_sub)

    return JsonResponse({
        "ok":        True,
        "item_qty":  new_qty,
        "line_total": str(new_line),
        "subtotal":  str(total_sub),
        "total":     str(total_sub + delivery),
        "qty_total": reg_qty + cx_qty,
    })


@require_POST
def constructor_add_to_cart(request, branch_id: int):
    import json
    from catalog.models import DishConstructor

    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    cx_id = request.POST.get("cx_id")
    cx = get_object_or_404(DishConstructor, id=cx_id, branch=branch, is_active=True)

    try:
        selections_raw = json.loads(request.POST.get("selections", "{}"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Неверные данные"}, status=400)

    groups = cx.groups.prefetch_related("ingredients").order_by("sort_order", "id")
    selections = []
    total_price = Decimal("0")

    for g in groups:
        raw = selections_raw.get(str(g.id), {})

        # Обратная совместимость: старый формат [id, id] → {id: 1}
        if isinstance(raw, list):
            raw = {str(i): 1 for i in raw if i}

        # qty-dict: {str(ing_id): qty}
        qty_map = {}
        for k, v in raw.items():
            try:
                qty_map[int(k)] = max(0, int(v))
            except (ValueError, TypeError):
                pass
        qty_map = {k: v for k, v in qty_map.items() if v > 0}

        total_qty = sum(qty_map.values())

        if g.min_select and total_qty < g.min_select:
            return JsonResponse(
                {"ok": False, "error": f"Выберите минимум {g.min_select} в «{g.name}»"}, status=400
            )
        if g.max_select > 0 and total_qty > g.max_select:
            return JsonResponse(
                {"ok": False, "error": f"Максимум {g.max_select} в «{g.name}»"}, status=400
            )

        if not qty_map:
            continue

        ings_data = []
        for ing in g.ingredients.select_related("branch_item__item").filter(
            is_active=True, id__in=qty_map.keys()
        ):
            qty = qty_map.get(ing.id, 1)
            ings_data.append({
                "id":    ing.id,
                "name":  ing.display_name,
                "price": str(ing.display_price),
                "qty":   qty,
            })
            total_price += ing.display_price * qty

        if ings_data:
            selections.append({"gid": g.id, "gname": g.name, "ings": ings_data})

    unit_price = total_price

    cart = _get_branch_cx_cart(request, branch_id)
    idx = max((item["idx"] for item in cart), default=-1) + 1
    cart.append({
        "idx":        idx,
        "cx_id":      cx.id,
        "cx_name":    cx.name,
        "base_price": str(cx.base_price),
        "selections": selections,
        "unit_price": str(unit_price),
        "qty":        1,
        "line_total": str(unit_price),
    })
    _save_branch_cx_cart(request, branch_id, cart)

    reg_cart = get_cart(request, branch_id)
    _, reg_subtotal, reg_qty = cart_details(branch, reg_cart)
    cx_total = sum(Decimal(str(x["unit_price"])) * int(x["qty"]) for x in cart)
    cx_qty   = sum(int(x["qty"]) for x in cart)
    total_sub = reg_subtotal + cx_total
    delivery  = _calc_delivery(branch, total_sub)

    return JsonResponse({
        "ok":       True,
        "qty_total": reg_qty + cx_qty,
        "total":     str(total_sub + delivery),
    })


@require_POST
def constructor_remove_from_cart(request, branch_id: int, cx_index: int):
    cart = _get_branch_cx_cart(request, branch_id)
    cart = [item for item in cart if item["idx"] != cx_index]
    _save_branch_cx_cart(request, branch_id, cart)
    return JsonResponse({"ok": True})


def constructor_build_page(request, branch_id: int, cx_id: int):
    """Отдельная страница для сборки блюда покупателем."""
    from catalog.models import DishConstructor
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    cx = get_object_or_404(DishConstructor, id=cx_id, branch=branch, is_active=True)
    groups = list(
        cx.groups.prefetch_related("ingredients__branch_item__item")
                 .order_by("sort_order", "id")
    )
    # фильтруем группы без активных позиций
    groups = [g for g in groups if g.ingredients.filter(is_active=True).exists()]

    cx_cart   = _get_branch_cx_cart(request, branch_id)
    reg_cart  = get_cart(request, branch_id)
    _, reg_sub, reg_qty = cart_details(branch, reg_cart)
    cx_total  = sum(Decimal(str(i["unit_price"])) * int(i["qty"]) for i in cx_cart)
    cx_qty    = sum(int(i["qty"]) for i in cx_cart)

    return render(request, "public_site/constructor_build.html", {
        "branch": branch,
        "cx": cx,
        "groups": groups,
        "cart_qty":   reg_qty + cx_qty,
        "cart_total": reg_sub + cx_total,
        "add_url": f"/{ branch_id }/constructor/add/",
    })

