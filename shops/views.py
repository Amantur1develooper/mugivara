from django.shortcuts import render
from django.utils.translation import gettext as _
# shops/views.py
from django.db import transaction
from django.db.models import F, Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.db import transaction
from .cart import dec, get_cart, get_mode, get_shop_cart, clear_shop_cart, save_cart, set_mode  # ✅ добавь это
from django.db.models import Prefetch
from .models import Store, StoreBranch, StoreCategory, StoreProduct, StoreStock
from urllib.parse import quote
import re
import urllib.parse
from decimal import Decimal
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.db import transaction
from .models import Store, StoreBranch, StoreCategory, StoreProduct, StoreStock, StoreOrder, StoreOrderItem, StoreConstructorOrderItem, StorePromotion
from .cart import get_cart, save_cart, set_mode, get_mode, dec, get_shop_cart, clear_shop_cart, get_cx_cart, save_cx_cart, clear_cx_cart
from . import constructor_utils
from .pricing import PromoResolver
import json
import uuid

# from .cart import get_cart, save_cart, set_mode, get_mode, dec

def _add_if_field(model, data: dict, field_name: str, value):
    """Добавляет поле в data только если оно реально есть в модели."""
    return field_name in {f.name for f in model._meta.get_fields() if hasattr(f, "name")} and data.setdefault(field_name, value) is None

def store_detail(request, slug):
    store = get_object_or_404(Store, slug=slug, is_active=True)
    branches = store.branches.filter(is_active=True).order_by("city", "name_ru")
    return render(request, "shops/store_detail.html", {"store": store, "branches": branches})


def branch_catalog(request, branch_id):
    branch = get_object_or_404(StoreBranch, id=branch_id, is_active=True)
    store = branch.store

    # категории
    categories = store.categories.filter(is_active=True).order_by("sort_order", "id")

    # товары + остатки для этого филиала
    stocks = (
        StoreStock.objects
        .filter(branch=branch, product__is_active=True)
        .select_related("product", "product__category")
    )

    # сгруппуем в шаблоне: category -> products
    return render(request, "shops/branch_catalog.html", {
        "store": store,
        "branch": branch,
        "categories": categories,
        "stocks": stocks,
    })




def _clean_phone(phone: str) -> str:
    # оставим только + и цифры
    p = "".join(ch for ch in (phone or "") if ch.isdigit() or ch == "+")
    return p

def _is_valid_kg_phone(phone: str) -> bool:
    # +996 + 9 цифр = 13 символов
    return isinstance(phone, str) and len(phone) == 13 and phone.startswith("+996") and phone[4:].isdigit()


def store_list(request):
    import json
    q = (request.GET.get("q") or "").strip()
    stores = Store.objects.filter(is_active=True)
    if q:
        stores = stores.filter(name_ru__icontains=q)

    map_points = []
    for b in StoreBranch.objects.filter(is_active=True, lat__isnull=False, lon__isnull=False).select_related("store"):
        map_points.append({
            "lat": float(b.lat),
            "lon": float(b.lon),
            "name": b.name_ru,
            "store": b.store.name_ru,
            "address": b.address,
            "store_url": f"/ru/shops/{b.store.slug}/",
        })

    return render(request, "shops/store_list.html", {
        "stores": stores,
        "q": q,
        "map_points_json": json.dumps(map_points, ensure_ascii=False),
    })


def store_detail(request, slug):
    store = get_object_or_404(Store, slug=slug, is_active=True)
    branches = store.branches.filter(is_active=True).order_by("city", "name_ru")
    return render(request, "shops/store_detail.html", {"store": store, "branches": branches})


def branch_catalog_delivery(request, branch_id):
    branch = get_object_or_404(StoreBranch, id=branch_id, is_active=True)
    set_mode(request, branch_id, "delivery")
    return _branch_catalog(request, branch)

def branch_catalog_pickup(request, branch_id):
    branch = get_object_or_404(StoreBranch, id=branch_id, is_active=True)
    set_mode(request, branch_id, "pickup")
    return _branch_catalog(request, branch)

def _branch_catalog(request, branch: StoreBranch):
    store = branch.store
    mode = get_mode(request, branch.id)

    stocks = list(
        StoreStock.objects
        .filter(branch=branch, product__is_active=True, product__sell_direct=True)
        .select_related("product", "product__category")
        .order_by("product__category__sort_order", "product__id")
    )

    # Показываем только те категории, в которых у этого филиала реально есть товары
    # в прямой продаже — пустые категории и товары «только для Собери сам»
    # (product__sell_direct=False, например лента/упаковка) в витрине не показываются.
    categories = (
        store.categories
        .filter(is_active=True, products__is_active=True, products__sell_direct=True,
                products__stocks__branch=branch)
        .annotate(branch_products_count=Count(
            "products",
            filter=Q(products__is_active=True, products__sell_direct=True, products__stocks__branch=branch),
            distinct=True,
        ))
        .distinct()
        .order_by("sort_order", "id")
    )

    # Акции на сегодня — считаем скидку один раз на магазин и подставляем в каждую карточку
    promo = PromoResolver(store)
    for s in stocks:
        s.promo_price, s.promo_percent = promo.price_for(s.product)

    # cart badge
    cart = get_cart(request, branch.id)
    qty_total = sum(dec(v) for v in cart.values())
    total = Decimal("0")
    # быстро посчитаем total по текущим ценам (с учётом акции)
    price_map = {s.product_id: s.promo_price for s in stocks}
    for pid, q in cart.items():
        total += price_map.get(int(pid), Decimal("0")) * dec(q)

    # «Собери сам» — данные для витрины + учёт уже добавленного в бейдже корзины
    cx_data = constructor_utils.constructors_data(store)
    has_constructors = any(cx["ready"] for cx in cx_data.values())
    cx_cart = get_cx_cart(request, branch.id)
    for it in cx_cart:
        resolved = constructor_utils.resolve_cx_item(cx_data, it)
        if resolved:
            qty_total += resolved["qty"]
            total += resolved["line_total"]

    # Баннер акции на сегодня (человекочитаемый список)
    from datetime import date as _date
    today_promos = (
        StorePromotion.objects
        .filter(store=store, is_active=True, weekday=_date.today().weekday())
        .prefetch_related("categories")
    )
    promo_lines = []
    for p in today_promos:
        scope = "на все товары" if p.apply_to_all else ", ".join(c.name_ru for c in p.categories.all())
        if scope:
            promo_lines.append(f"{scope} −{p.discount_percent}%")

    return render(request, "shops/branch_catalog.html", {
        "store": store,
        "branch": branch,
        "mode": mode,
        "categories": categories,
        "stocks": stocks,
        "cart_qty": qty_total,
        "cart_total": total,
        "has_constructors": has_constructors,
        "constructors_json": constructor_utils.constructors_json(store) if has_constructors else "{}",
        "promo_lines": promo_lines,
    })


def cart_detail(request, branch_id):
    branch = get_object_or_404(StoreBranch, id=branch_id, is_active=True)
    mode = get_mode(request, branch_id)
    cart = get_cart(request, branch_id)

    product_ids = [int(pid) for pid in cart.keys()]
    stocks = (
        StoreStock.objects
        .filter(branch=branch, product_id__in=product_ids)
        .select_related("product", "product__category")
    )
    stock_map = {s.product_id: s for s in stocks}
    promo = PromoResolver(branch.store)

    rows = []
    subtotal = Decimal("0")
    qty_total = Decimal("0")

    for pid_str, qty_str in cart.items():
        pid = int(pid_str)
        s = stock_map.get(pid)
        if not s:
            continue
        qty = dec(qty_str)
        price, discount_percent = promo.price_for(s.product)
        line_total = price * qty
        subtotal += line_total
        qty_total += qty
        rows.append({
            "product": s.product,
            "stock": s,
            "qty": qty,
            "price": price,
            "orig_price": s.product.price,
            "discount_percent": discount_percent,
            "line_total": line_total,
        })

    # «Собери сам» — позиции считаем на сервере от актуальных данных конструктора
    cx_cart = get_cx_cart(request, branch_id)
    cx_data = constructor_utils.constructors_data(branch.store)
    cx_rows = []
    for it in cx_cart:
        resolved = constructor_utils.resolve_cx_item(cx_data, it)
        if not resolved:
            continue
        subtotal += resolved["line_total"]
        qty_total += resolved["qty"]
        cx_rows.append(resolved)

    delivery_fee = Decimal("0")
    if mode == "delivery" and branch.delivery_enabled:
        delivery_fee = branch.delivery_fee

    total = subtotal + delivery_fee

    min_order_amount = branch.min_order_amount or Decimal("0")
    below_min_order = (
        mode == "delivery" and branch.delivery_enabled
        and min_order_amount and subtotal < min_order_amount
    )
    min_order_remain = (min_order_amount - subtotal) if below_min_order else Decimal("0")

    return render(request, "shops/cart_detail.html", {
        "branch": branch,
        "mode": mode,
        "rows": rows,
        "cx_rows": cx_rows,
        "qty_total": qty_total,
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "total": total,
        "min_order_amount": min_order_amount,
        "below_min_order": below_min_order,
        "min_order_remain": min_order_remain,
        "min_order_error": request.GET.get("min_order_error") == "1",
    })


def cart_add(request, branch_id, product_id):
    branch = get_object_or_404(StoreBranch, id=branch_id, is_active=True)
    stock = get_object_or_404(
        StoreStock, branch=branch, product_id=product_id,
        product__is_active=True, product__sell_direct=True,
    )

    qty = dec(request.POST.get("qty") or "1")
    if qty <= 0:
        return JsonResponse({"ok": False, "error": "qty"})

    if stock.is_stopped:
        return JsonResponse({"ok": False, "error": "stopped"})

    cart = get_cart(request, branch_id)
    current = dec(cart.get(str(product_id), "0"))
    new_qty = current + qty

    # проверка остатков — пропускаем, если товар помечен «продавать без остатка»
    if not stock.product.sell_out_of_stock and new_qty > stock.qty:
        payload = {"ok": False, "error": "not_enough"}
        if branch.show_stock_qty:
            payload["available"] = str(stock.qty)
        return JsonResponse(payload)

    cart[str(product_id)] = str(new_qty)
    save_cart(request, branch_id, cart)

    # totals
    qty_total = sum(dec(v) for v in cart.values())
    # total считаем по товарам этой корзины (цена — с учётом акции на сегодня)
    pids = [int(pid) for pid in cart.keys()]
    products = StoreProduct.objects.filter(id__in=pids).only("id", "price", "category_id")
    promo = PromoResolver(branch.store)
    price_map = {p.id: promo.price_for(p)[0] for p in products}
    total = sum(price_map.get(int(pid), Decimal("0")) * dec(q) for pid, q in cart.items())

    return JsonResponse({"ok": True, "qty_total": str(qty_total), "total": str(total)})


def cart_update(request, branch_id, product_id):
    branch = get_object_or_404(StoreBranch, id=branch_id, is_active=True)
    stock = get_object_or_404(
        StoreStock, branch=branch, product_id=product_id,
        product__is_active=True, product__sell_direct=True,
    )

    qty = dec(request.POST.get("qty") or "0")
    cart = get_cart(request, branch_id)

    if qty <= 0:
        cart.pop(str(product_id), None)
    else:
        if stock.is_stopped:
            return JsonResponse({"ok": False, "error": "stopped"})
        if not stock.product.sell_out_of_stock and qty > stock.qty:
            payload = {"ok": False, "error": "not_enough"}
            if branch.show_stock_qty:
                payload["available"] = str(stock.qty)
            return JsonResponse(payload)
        cart[str(product_id)] = str(qty)

    save_cart(request, branch_id, cart)

    promo = PromoResolver(branch.store)

    qty_total = sum(dec(v) for v in cart.values())
    pids = [int(pid) for pid in cart.keys()]
    products = StoreProduct.objects.filter(id__in=pids).only("id", "price", "category_id")
    price_map = {p.id: promo.price_for(p)[0] for p in products}
    subtotal = sum(price_map.get(int(pid), Decimal("0")) * dec(q) for pid, q in cart.items())

    mode = get_mode(request, branch_id)
    delivery_fee = Decimal("0")
    if mode == "delivery" and branch.delivery_enabled:
        delivery_fee = branch.delivery_fee

    total = subtotal + delivery_fee

    row_price = promo.price_for(stock.product)[0] if qty > 0 else Decimal("0")
    line_total = row_price * qty if qty > 0 else Decimal("0")
    return JsonResponse({
        "ok": True,
        "row_qty": str(qty),
        "line_total": str(line_total),
        "qty_total": str(qty_total),
        "subtotal": str(subtotal),
        "delivery_fee": str(delivery_fee),
        "total": str(total),
    })


def cart_remove(request, branch_id, product_id):
    cart = get_cart(request, branch_id)
    cart.pop(str(product_id), None)
    save_cart(request, branch_id, cart)
    return JsonResponse({"ok": True})


def _combined_totals(request, branch):
    """qty_total/subtotal/total с учётом обычной корзины + «Собери сам» — для бейджа корзины."""
    cart = get_cart(request, branch.id)
    pids = [int(pid) for pid in cart.keys()]
    products = StoreProduct.objects.filter(id__in=pids).only("id", "price")
    price_map = {p.id: p.price for p in products}
    qty_total = sum(dec(v) for v in cart.values())
    subtotal = sum(price_map.get(int(pid), Decimal("0")) * dec(q) for pid, q in cart.items())

    cx_data = constructor_utils.constructors_data(branch.store)
    for it in get_cx_cart(request, branch.id):
        resolved = constructor_utils.resolve_cx_item(cx_data, it)
        if resolved:
            qty_total += resolved["qty"]
            subtotal += resolved["line_total"]

    mode = get_mode(request, branch.id)
    delivery_fee = branch.delivery_fee if (mode == "delivery" and branch.delivery_enabled) else Decimal("0")
    total = subtotal + delivery_fee
    return qty_total, subtotal, delivery_fee, total


# ── «Собери сам» в публичной витрине ────────────────────────────────────────

def cx_cart_add(request, branch_id, cx_id):
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)
    branch = get_object_or_404(StoreBranch, id=branch_id, is_active=True)
    cx_data = constructor_utils.constructors_data(branch.store)
    cx = cx_data.get(cx_id)
    if not cx or not cx["ready"]:
        return JsonResponse({"ok": False, "error": "not_available"})

    try:
        selections = json.loads(request.POST.get("selections") or "{}")
        if not isinstance(selections, dict):
            selections = {}
    except Exception:
        selections = {}
    try:
        qty = max(1, int(dec(request.POST.get("qty") or "1")))
    except Exception:
        qty = 1

    err = constructor_utils.validate_cx_selections(cx, selections)
    if err:
        return JsonResponse({"ok": False, "error": "validation", "message": err})

    cx_cart = get_cx_cart(request, branch_id)
    cx_cart.append({
        "item_id": uuid.uuid4().hex[:10],
        "cx_id": cx_id,
        "qty": qty,
        "selections": selections,
    })
    save_cx_cart(request, branch_id, cx_cart)

    qty_total, subtotal, delivery_fee, total = _combined_totals(request, branch)
    return JsonResponse({
        "ok": True, "qty_total": str(qty_total), "subtotal": str(subtotal),
        "delivery_fee": str(delivery_fee), "total": str(total),
    })


def cx_cart_update(request, branch_id, item_id):
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)
    branch = get_object_or_404(StoreBranch, id=branch_id, is_active=True)
    try:
        qty = int(dec(request.POST.get("qty") or "0"))
    except Exception:
        qty = 0

    cx_cart = get_cx_cart(request, branch_id)
    line_total = Decimal("0")
    if qty <= 0:
        cx_cart = [it for it in cx_cart if it["item_id"] != item_id]
    else:
        for it in cx_cart:
            if it["item_id"] == item_id:
                it["qty"] = qty
                break
        cx_data = constructor_utils.constructors_data(branch.store)
        for it in cx_cart:
            if it["item_id"] == item_id:
                resolved = constructor_utils.resolve_cx_item(cx_data, it)
                if resolved:
                    line_total = resolved["line_total"]
                break
    save_cx_cart(request, branch_id, cx_cart)

    qty_total, subtotal, delivery_fee, total = _combined_totals(request, branch)
    return JsonResponse({
        "ok": True, "row_qty": qty if qty > 0 else 0, "line_total": str(line_total),
        "qty_total": str(qty_total), "subtotal": str(subtotal),
        "delivery_fee": str(delivery_fee), "total": str(total),
    })


def cx_cart_remove(request, branch_id, item_id):
    branch = get_object_or_404(StoreBranch, id=branch_id, is_active=True)
    cx_cart = get_cx_cart(request, branch_id)
    cx_cart = [it for it in cx_cart if it["item_id"] != item_id]
    save_cx_cart(request, branch_id, cx_cart)
    qty_total, subtotal, delivery_fee, total = _combined_totals(request, branch)
    return JsonResponse({"ok": True, "qty_total": str(qty_total), "subtotal": str(subtotal), "total": str(total)})


def _wa_digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")

def _build_shop_order_text(order, items, is_delivery: bool) -> str:
    # items: список (name, qty, price, line_total)
    lines = []
    lines.append(f"🛒 Заказ (магазин)")
    lines.append(f"Филиал: {order.branch.name}")
    lines.append(f"Тип: {'Доставка' if is_delivery else 'В магазине'}")
    lines.append(f"Телефон клиента: {order.phone}")
    if order.name:
        lines.append(f"Имя: {order.name}")
    if is_delivery:
        lines.append(f"Адрес: {order.address}")
    if order.comment:
        lines.append(f"Комментарий: {order.comment}")
    lines.append("")
    lines.append("Состав:")
    for it in items:
        lines.append(f"• {it['name']} × {it['qty']} = {it['line_total']} сом")
    lines.append("")
    lines.append(f"Итого: {order.total} сом")
    return "\n".join(lines)
import re
from urllib.parse import quote
from django.http import HttpResponseNotAllowed
from django.contrib import messages

def _wa_digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")

def _build_shop_order_text(order, items, is_delivery: bool) -> str:
    lines = []
    lines.append("🛒 Заказ (магазин)")
    lines.append(f"Филиал: {order.branch.name_ru}")
    lines.append(f"Тип: {'Доставка' if is_delivery else 'В магазине'}")
    lines.append(f"Телефон клиента: {order.phone}")
    if getattr(order, "name", ""):
        lines.append(f"Имя: {order.name}")
    if is_delivery:
        lines.append(f"Адрес: {order.address}")
    if getattr(order, "comment", ""):
        lines.append(f"Комментарий: {order.comment}")
    lines.append("")
    lines.append("Состав:")
    for it in items:
        lines.append(f"• {it['name']} × {it['qty']} = {it['line_total']} сом")
    lines.append("")
    lines.append(f"Итого: {order.total} сом")
    return "\n".join(lines)

def checkout(request, branch_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    branch = get_object_or_404(StoreBranch, pk=branch_id, is_active=True)

    cart = get_shop_cart(request, branch)
    rows = cart["rows"]

    # «Собери сам» — считаем на сервере от актуальных данных конструктора
    cx_cart = get_cx_cart(request, branch_id)
    cx_data = constructor_utils.constructors_data(branch.store)
    cx_rows = [r for r in (constructor_utils.resolve_cx_item(cx_data, it) for it in cx_cart) if r]

    if not rows and not cx_rows:
        return redirect("shops:cart_detail", branch_id=branch.id)

    cx_subtotal = sum((cr["line_total"] for cr in cx_rows), Decimal("0"))
    combined_subtotal = cart["subtotal"] + cx_subtotal

    # режим берём из session (ты его ставишь кнопками delivery/in_store)
    mode = get_mode(request, branch.id)   # "delivery" | "in_store"
    is_delivery = (mode == "delivery")

    name = (request.POST.get("name") or "").strip()
    phone = (request.POST.get("phone") or "").strip()
    address = (request.POST.get("address") or "").strip()
    comment = (request.POST.get("comment") or "").strip()

    # адрес обязателен только для доставки
    if is_delivery and not address:
        messages.error(request, _("Укажите адрес для доставки"))
        return redirect("shops:cart_detail", branch_id=branch.id)

    delivery_fee = Decimal("0")
    if is_delivery and getattr(branch, "delivery_enabled", False):
        delivery_fee = dec(getattr(branch, "delivery_fee", 0))

    # Минимальная сумма заказа для доставки — не пропускаем оформление, если не набрали
    min_order = dec(getattr(branch, "min_order_amount", 0) or 0)
    if is_delivery and min_order and combined_subtotal < min_order:
        return redirect(f"{reverse('shops:cart_detail', args=[branch.id])}?min_order_error=1")

    product_ids = [r["product_id"] for r in rows]

    # сколько ингредиентов «Собери сам» нужно списать со склада филиала (суммарно)
    cx_ing_needed = {}
    for cr in cx_rows:
        for pid, per_unit in cr["wh_deductions"].items():
            cx_ing_needed[pid] = cx_ing_needed.get(pid, Decimal("0")) + per_unit * cr["qty"]

    with transaction.atomic():
        # блокируем остатки
        stocks = (StoreStock.objects
                  .select_for_update()
                  .filter(branch=branch, product_id__in=product_ids, product__is_active=True)
                  .select_related("product"))
        stock_map = {s.product_id: s for s in stocks}

        # проверка наличия — «продавать без остатка» пропускает только сравнение количества
        for r in rows:
            st = stock_map.get(r["product_id"])
            if not st or st.is_stopped or not st.product.sell_direct:
                messages.error(request, _("Нет в наличии: %(name)s") % {"name": r['product'].name_ru})
                return redirect("shops:cart_detail", branch_id=branch.id)
            if not st.product.sell_out_of_stock and int(st.qty) < int(r["qty"]):
                messages.error(request, _("Нет в наличии: %(name)s") % {"name": r['product'].name_ru})
                return redirect("shops:cart_detail", branch_id=branch.id)

        # проверка наличия ингредиентов для «Собери сам»
        cx_stock_map = {}
        if cx_ing_needed:
            cx_stocks = (StoreStock.objects
                         .select_for_update()
                         .filter(branch=branch, product_id__in=list(cx_ing_needed.keys()))
                         .select_related("product"))
            cx_stock_map = {s.product_id: s for s in cx_stocks}
            for pid, needed in cx_ing_needed.items():
                st = cx_stock_map.get(pid)
                if not st:
                    messages.error(request, _("Нет в наличии: %(name)s") % {"name": pid})
                    return redirect("shops:cart_detail", branch_id=branch.id)
                if not st.product.sell_out_of_stock and st.qty < needed:
                    messages.error(request, _("Нет в наличии: %(name)s") % {"name": st.product.name_ru})
                    return redirect("shops:cart_detail", branch_id=branch.id)

        subtotal = cart["subtotal"] + cx_subtotal
        total = subtotal + delivery_fee

        # создаём заказ
        # создаём заказ (ТОЛЬКО по существующим полям)
        order_data = {
    "branch": branch,
    "phone": phone,
        }

# optional поля
        if name:
            if "name" in {f.name for f in StoreOrder._meta.get_fields()}:
                order_data["name"] = name

        if comment:
            if "comment" in {f.name for f in StoreOrder._meta.get_fields()}:
                order_data["comment"] = comment

# адрес — только для доставки (и только если поле есть)
        if is_delivery and address and ("address" in {f.name for f in StoreOrder._meta.get_fields()}):
            order_data["address"] = address
        elif (not is_delivery) and ("address" in {f.name for f in StoreOrder._meta.get_fields()}):
            order_data["address"] = ""

# если у тебя есть поле mode (рекомендовано) — запишем
        fields = {f.name for f in StoreOrder._meta.get_fields()}
        if "mode" in fields:
            order_data["mode"] = "delivery" if is_delivery else "in_store"
        elif "order_type" in fields:
            order_data["order_type"] = "delivery" if is_delivery else "in_store"
# ⚠️ is_delivery НЕ передаём, потому что поля нет

# суммы — добавляем только если есть такие поля
        if "total" in fields:
            order_data["total"] = total
        if "subtotal" in fields:
            order_data["subtotal"] = subtotal
        if "delivery_fee" in fields:
            order_data["delivery_fee"] = delivery_fee

        order = StoreOrder.objects.create(**order_data)


        items_payload = []

        # позиции + списание (цена — из корзины, уже с учётом акции на сегодня)
        for r in rows:
            st = stock_map[r["product_id"]]
            price = r["price"]
            qty = int(r["qty"])
            line_total = price * qty

            StoreOrderItem.objects.create(
                order=order,
                product=st.product,
                qty=qty,
                price=price,
                line_total=line_total,
            )

            StoreStock.objects.filter(pk=st.pk).update(qty=F("qty") - qty)

            items_payload.append({
                "name": getattr(st.product, "name_ru", str(st.product)),
                "qty": qty,
                "line_total": line_total,
            })

        # «Собери сам» — позиции заказа + списание ингредиентов со склада филиала
        for cr in cx_rows:
            StoreConstructorOrderItem.objects.create(
                order=order, constructor_id=cr["cx_id"], constructor_name_snapshot=cr["cx_name"],
                qty=cr["qty"], unit_price=cr["unit_price"], line_total=cr["line_total"],
                ingredients_snapshot=cr["snapshot"],
            )
            items_payload.append({
                "name": "🧩 " + cr["cx_name"] + (f" ({cr['summary']})" if cr["summary"] else ""),
                "qty": cr["qty"],
                "line_total": cr["line_total"],
            })

        for pid, needed in cx_ing_needed.items():
            StoreStock.objects.filter(pk=cx_stock_map[pid].pk).update(qty=F("qty") - needed)

    # чистим корзину после успешного заказа
    clear_shop_cart(request, branch)

    # текст заказа (для success + копирование + WA)
    order_text = _build_shop_order_text(order, items_payload, is_delivery=is_delivery)
    request.session["shop_last_order_text"] = order_text
    request.session.modified = True

    # Уведомление в Telegram отправляет integrations/signals.py (post_save на StoreOrder) —
    # он срабатывает автоматически для ЛЮБОГО способа создания заказа (сайт, касса и т.д.)
    # и уже включает состав «Собери сам». Раньше здесь ЕЩЁ ОТДЕЛЬНО вызывался
    # shops.tasks.notify_new_shop_order — устаревший дублирующий путь без учёта
    # «Собери сам», из-за которого в группу через раз приходило то полное, то пустое
    # сообщение по одному и тому же заказу. Убрано, чтобы не дублировать.

    return redirect("shops:checkout_success", branch_id=branch.id, order_id=order.id)



def order_success(request, branch_id, order_id):
    branch = get_object_or_404(StoreBranch, id=branch_id, is_active=True)
    order = get_object_or_404(StoreOrder, id=order_id, branch=branch)
    text = request.session.get("shop_last_order_text", "")

    # wa number
    phone_digits = "".join(ch for ch in (branch.phone or "") if ch.isdigit())
    wa_phone = phone_digits
    wa_url = ""
    if wa_phone:
        wa_url = "https://wa.me/{}?text={}".format(wa_phone, urllib.parse.quote(text))
    phone_digits2 = "".join(ch for ch in (branch.phone2 or "") if ch.isdigit())
    wa_url2 = "https://wa.me/{}?text={}".format(phone_digits2, urllib.parse.quote(text)) if phone_digits2 else ""

    # 1–2 строки состава
    items = list(order.items.select_related("product").all()[:2])
    short = []
    for it in items:
        short.append(f"{it.product.name_ru} × {it.qty}")

    return render(request, "shops/order_success.html", {
        "branch": branch,
        "order": order,
        "wa_url": wa_url,
        "wa_url2": wa_url2,
        "order_text": text,
        "short_lines": short,
    })
# shops/views.py


def _wa_digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")

def checkout_success(request, branch_id, order_id):
    order = (StoreOrder.objects
             .select_related("branch")
             .prefetch_related("items__product", "constructor_items")
             .get(pk=order_id, branch_id=branch_id))

    order_text = request.session.get("shop_last_order_text", "")

    wa_phone = _wa_digits(order.branch.phone)
    wa_url = f"https://wa.me/{wa_phone}?text={quote(order_text)}" if wa_phone else ""

    wa_phone2 = _wa_digits(order.branch.phone2)
    wa_url2 = f"https://wa.me/{wa_phone2}?text={quote(order_text)}" if wa_phone2 else ""

    # Собираем краткий состав: обычные товары + «Собери сам» — в один список
    all_lines = [{"name": it.product.name_ru, "qty": it.qty} for it in order.items.all()]
    all_lines += [
        {"name": "🧩 " + (coi.constructor_name_snapshot or "Собери сам"), "qty": coi.qty}
        for coi in order.constructor_items.all()
    ]
    preview_items = all_lines[:2]

    return render(request, "shops/checkout_success.html", {
        "order": order,
        "wa_url": wa_url,
        "wa_url2": wa_url2,
        "order_text": order_text,
        "preview_items": preview_items,
        "preview_more": len(all_lines) > 2,
    })
