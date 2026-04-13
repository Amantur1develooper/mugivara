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
from core.models import Restaurant, Branch, AdBanner


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
        "karaoke_count":    KaraokeVenue.objects.filter(is_active=True).count(),
        "branch_count": (
            Branch.objects.filter(is_active=True).count()
            + StoreBranch.objects.filter(is_active=True).count()
        ),
    }
    stats["total"] = (
        stats["restaurant_count"] + stats["store_count"] + stats["pharmacy_count"]
        + stats["market_count"] + stats["hotel_count"] + stats["legal_count"]
        + stats["eco_count"] + stats["agency_count"] + stats["karaoke_count"]
    )

    try:
        ad_banners = [
            {
                "obj": b,
                "click_url": f"/ads/{b.id}/click/" if b.link_url else "",
            }
            for b in AdBanner.objects.filter(is_active=True).order_by("sort_order")
        ]
    except Exception:
        ad_banners = []

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
        "karaoke_cards":    karaoke_cards,
        "stats":            stats,
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

    cart = get_cart(request, branch.id)
    _, total, qty_total = cart_details(branch, cart)
    return {"branch": branch, "menu": menu, "cart_qty": qty_total, "cart_total": total}


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
    delivery_fee = _calc_delivery(branch, subtotal)
    total = subtotal + delivery_fee
    free_from = branch.free_delivery_from or Decimal("0")

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
    return JsonResponse({
        "ok":               True,
        "items":            items,
        "subtotal":         str(subtotal),
        "delivery_fee":     str(delivery_fee),
        "delivery_enabled": branch.delivery_enabled,
        "total":            str(total),
        "qty_total":        qty_total,
        "min_order_amount": str(branch.min_order_amount),
        "free_from":        str(free_from),
        "free_delivery_reached": delivery_fee == 0 and free_from > 0 and branch.delivery_enabled,
    })


def cart_detail(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    cart = get_cart(request, branch.id)
    rows, subtotal, qty_total = cart_details(branch, cart)

    delivery_fee = branch.delivery_fee if branch.delivery_enabled else Decimal("0")
    total = subtotal + delivery_fee
    print("SESSION CART =", request.session.get("cart"))

    return render(request, "public_site/cart_detail.html", {
        "branch": branch,
        "rows": rows,
        "qty_total": qty_total,
        "subtotal": subtotal,
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
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    cart = get_cart(request, branch.id)
    rows, subtotal, qty_total = cart_details(branch, cart)

    if qty_total == 0:
        messages.error(request, _("Корзина пуста."))
        return redirect("public_site:cart_detail", branch_id=branch.id)

    name = (request.POST.get("name") or "").strip() or _("Гость")
    phone = (request.POST.get("phone") or "").strip()
    address = (request.POST.get("address") or "").strip()
    comment = (request.POST.get("comment") or "").strip()

    # обязательные поля
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

    # проверка минималки только для доставки
    if order_type == Order.Type.DELIVERY and subtotal < branch.min_order_amount:
        messages.error(
            request,
            _("Минимальная сумма заказа для доставки: %(min)s") % {"min": branch.min_order_amount}
        )
        return redirect("public_site:cart_detail", branch_id=branch.id)

    if order_type == Order.Type.DELIVERY:
        free_from = branch.free_delivery_from or Decimal("0")
        if free_from > 0 and subtotal >= free_from:
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
                    promo_discount = (subtotal * promo.discount_value / Decimal("100")).quantize(Decimal("1"))
                    promo_msg_line = f"Промокод {promo.code}: −{promo.discount_value}% (−{promo_discount} сом)"
                elif promo.discount_type == PromoCode.DiscountType.FIXED:
                    promo_discount = min(promo.discount_value, subtotal)
                    promo_msg_line = f"Промокод {promo.code}: −{promo_discount} сом"
            else:
                promo = None
        except PromoCode.DoesNotExist:
            promo = None

    total = subtotal - promo_discount + delivery_fee

    # Весь блок — одна транзакция, чтобы on_commit (TG-уведомление)
    # сработал уже после того как все OrderItem-ы сохранены.
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
            payment_method=payment_method,
            payment_status=Order.PaymentStatus.UNPAID,
        )

        # увеличиваем рейтинг ресторана
        Restaurant.objects.filter(pk=branch.restaurant_id).update(rating=F("rating") + Decimal("0.1"))

        # учитываем использование промокода
        if promo:
            PromoCode.objects.filter(pk=promo.pk).update(used_count=F("used_count") + 1)

        # сохраняем позиции
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
                line_total=line_total
            )

            item_name = getattr(bi.item, "name_ru", None) or str(bi.item)
            lines.append(f"{i}) {item_name} × {qty} = {line_total} сом")

    # очищаем корзину (после коммита транзакции)
    clear_cart(request, branch.id)

    # готовим сообщение
    type_text = "Доставка" if order_type == Order.Type.DELIVERY else "Самовывоз"
    msg = (
        f"🧾 Новый заказ #{order.id}\n"
        f"Филиал: {getattr(branch, 'name_ru', None) or branch.name}\n"
        f"Тип: {type_text}\n"
        f"Имя: {name}\n"
        f"Телефон: {phone}\n"
        f"Адрес/стол: {address}\n"
    )
    if comment:
        msg += f"Комментарий: {comment}\n"

    msg += "\nСостав:\n" + "\n".join(lines) + "\n"
    msg += f"\nПодытог: {subtotal} сом"
    if promo_msg_line:
        msg += f"\n{promo_msg_line}"
    if order_type == Order.Type.DELIVERY:
        msg += f"\nДоставка: {delivery_fee} сом"
    msg += f"\nИтого: {total} сом"

    # редирект в WhatsApp филиала
    wa_number = "".join(ch for ch in (branch.phone or "") if ch.isdigit())
    if wa_number:
        whatsapp_url = f"https://wa.me/{wa_number}?text={quote(msg)}"
        return redirect(whatsapp_url)

    # если телефона нет — просто показываем страницу успеха (fallback)
    return redirect("public_site:checkout_success", branch_id=branch.id, order_id=order.id)

from urllib.parse import quote
from django.shortcuts import get_object_or_404, render
from orders.models import Order, OrderItem
from core.models import Branch
from urllib.parse import quote
from decimal import Decimal
from django.shortcuts import get_object_or_404, render
from orders.models import Order, OrderItem
from core.models import Branch
from urllib.parse import quote
from decimal import Decimal
from django.shortcuts import get_object_or_404, render
from orders.models import Order, OrderItem
from core.models import Branch

def checkout_success(request, branch_id: int, order_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    order = get_object_or_404(Order, id=order_id, branch=branch)

    items = (OrderItem.objects
             .filter(order=order)
             .select_related("item")
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
        f"Филиал: {getattr(branch, 'name_ru', None) or branch.name}\n"
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

    wa_number = "".join(ch for ch in (branch.phone or "") if ch.isdigit())

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


def ad_banner_click(request, banner_id: int):
    """Считает клик по баннеру и перенаправляет на целевой URL."""
    from django.http import HttpResponseRedirect, HttpResponseNotFound
    from core.models import AdBanner
    from django.db.models import F

    try:
        banner = AdBanner.objects.filter(id=banner_id, is_active=True).only("link_url").get()
    except AdBanner.DoesNotExist:
        return HttpResponseNotFound()

    # Атомарный инкремент — без race condition
    AdBanner.objects.filter(id=banner_id).update(click_count=F("click_count") + 1)

    if banner.link_url:
        return HttpResponseRedirect(banner.link_url)
    return HttpResponseRedirect("/")

