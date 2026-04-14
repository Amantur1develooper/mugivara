from django.shortcuts import render
# shops/views.py
from django.db import transaction
from django.db.models import F
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
from .models import Store, StoreBranch, StoreCategory, StoreProduct, StoreStock, StoreOrder, StoreOrderItem
from .cart import get_cart, save_cart, set_mode, get_mode, dec, get_shop_cart, clear_shop_cart

# from .cart import get_cart, save_cart, set_mode, get_mode, dec

def _add_if_field(model, data: dict, field_name: str, value):
    """Добавляет поле в data только если оно реально есть в модели."""
    return field_name in {f.name for f in model._meta.get_fields() if hasattr(f, "name")} and data.setdefault(field_name, value) is None

def store_list(request):
    q = (request.GET.get("q") or "").strip()
    stores = Store.objects.filter(is_active=True)
    if q:
        stores = stores.filter(name_ru__icontains=q)
    return render(request, "shops/store_list.html", {"stores": stores, "q": q})


def store_detail(request, slug):
    store = get_object_or_404(Store, slug=slug, is_active=True)
    branches = store.branches.filter(is_active=True)
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
    q = (request.GET.get("q") or "").strip()
    stores = Store.objects.filter(is_active=True)
    if q:
        stores = stores.filter(name_ru__icontains=q)
    return render(request, "shops/store_list.html", {"stores": stores, "q": q})


def store_detail(request, slug):
    store = get_object_or_404(Store, slug=slug, is_active=True)
    branches = store.branches.filter(is_active=True)
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

    categories = store.categories.filter(is_active=True).order_by("sort_order", "id")

    stocks = (
        StoreStock.objects
        .filter(branch=branch, product__is_active=True)
        .select_related("product", "product__category")
        .order_by("product__category__sort_order", "product__id")
    )

    # cart badge
    cart = get_cart(request, branch.id)
    qty_total = sum(dec(v) for v in cart.values())
    total = Decimal("0")
    # быстро посчитаем total по текущим ценам
    price_map = {s.product_id: s.product.price for s in stocks}
    for pid, q in cart.items():
        total += price_map.get(int(pid), Decimal("0")) * dec(q)

    return render(request, "shops/branch_catalog.html", {
        "store": store,
        "branch": branch,
        "mode": mode,
        "categories": categories,
        "stocks": stocks,
        "cart_qty": qty_total,
        "cart_total": total,
    })


def cart_detail(request, branch_id):
    branch = get_object_or_404(StoreBranch, id=branch_id, is_active=True)
    mode = get_mode(request, branch_id)
    cart = get_cart(request, branch_id)

    product_ids = [int(pid) for pid in cart.keys()]
    stocks = (
        StoreStock.objects
        .filter(branch=branch, product_id__in=product_ids)
        .select_related("product")
    )
    stock_map = {s.product_id: s for s in stocks}

    rows = []
    subtotal = Decimal("0")
    qty_total = Decimal("0")

    for pid_str, qty_str in cart.items():
        pid = int(pid_str)
        s = stock_map.get(pid)
        if not s:
            continue
        qty = dec(qty_str)
        line_total = s.product.price * qty
        subtotal += line_total
        qty_total += qty
        rows.append({
            "product": s.product,
            "stock": s,
            "qty": qty,
            "line_total": line_total,
        })

    delivery_fee = Decimal("0")
    if mode == "delivery" and branch.delivery_enabled:
        delivery_fee = branch.delivery_fee

    total = subtotal + delivery_fee

    return render(request, "shops/cart_detail.html", {
        "branch": branch,
        "mode": mode,
        "rows": rows,
        "qty_total": qty_total,
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "total": total,
    })


def cart_add(request, branch_id, product_id):
    branch = get_object_or_404(StoreBranch, id=branch_id, is_active=True)
    stock = get_object_or_404(StoreStock, branch=branch, product_id=product_id, product__is_active=True)

    qty = dec(request.POST.get("qty") or "1")
    if qty <= 0:
        return JsonResponse({"ok": False, "error": "qty"})

    cart = get_cart(request, branch_id)
    current = dec(cart.get(str(product_id), "0"))
    new_qty = current + qty

    # проверка остатков
    if new_qty > stock.qty:
        return JsonResponse({"ok": False, "error": "not_enough", "available": str(stock.qty)})

    cart[str(product_id)] = str(new_qty)
    save_cart(request, branch_id, cart)

    # totals
    qty_total = sum(dec(v) for v in cart.values())
    # total считаем по товарам этой корзины
    pids = [int(pid) for pid in cart.keys()]
    products = StoreProduct.objects.filter(id__in=pids).only("id", "price")
    price_map = {p.id: p.price for p in products}
    total = sum(price_map.get(int(pid), Decimal("0")) * dec(q) for pid, q in cart.items())

    return JsonResponse({"ok": True, "qty_total": str(qty_total), "total": str(total)})


def cart_update(request, branch_id, product_id):
    branch = get_object_or_404(StoreBranch, id=branch_id, is_active=True)
    stock = get_object_or_404(StoreStock, branch=branch, product_id=product_id, product__is_active=True)

    qty = dec(request.POST.get("qty") or "0")
    cart = get_cart(request, branch_id)

    if qty <= 0:
        cart.pop(str(product_id), None)
    else:
        if qty > stock.qty:
            return JsonResponse({"ok": False, "error": "not_enough", "available": str(stock.qty)})
        cart[str(product_id)] = str(qty)

    save_cart(request, branch_id, cart)

    qty_total = sum(dec(v) for v in cart.values())
    pids = [int(pid) for pid in cart.keys()]
    products = StoreProduct.objects.filter(id__in=pids).only("id", "price")
    price_map = {p.id: p.price for p in products}
    subtotal = sum(price_map.get(int(pid), Decimal("0")) * dec(q) for pid, q in cart.items())

    mode = get_mode(request, branch_id)
    delivery_fee = Decimal("0")
    if mode == "delivery" and branch.delivery_enabled:
        delivery_fee = branch.delivery_fee

    total = subtotal + delivery_fee

    line_total = stock.product.price * qty if qty > 0 else Decimal("0")
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
    if not rows:
        return redirect("shops:cart_detail", branch_id=branch.id)

    # режим берём из session (ты его ставишь кнопками delivery/in_store)
    mode = get_mode(request, branch.id)   # "delivery" | "in_store"
    is_delivery = (mode == "delivery")

    name = (request.POST.get("name") or "").strip()
    phone = (request.POST.get("phone") or "").strip()
    address = (request.POST.get("address") or "").strip()
    comment = (request.POST.get("comment") or "").strip()

    # адрес обязателен только для доставки
    if is_delivery and not address:
        messages.error(request, "Укажите адрес для доставки")
        return redirect("shops:cart_detail", branch_id=branch.id)

    delivery_fee = Decimal("0")
    if is_delivery and getattr(branch, "delivery_enabled", False):
        delivery_fee = dec(getattr(branch, "delivery_fee", 0))

    product_ids = [r["product_id"] for r in rows]

    with transaction.atomic():
        # блокируем остатки
        stocks = (StoreStock.objects
                  .select_for_update()
                  .filter(branch=branch, product_id__in=product_ids, product__is_active=True)
                  .select_related("product"))
        stock_map = {s.product_id: s for s in stocks}

        # проверка наличия
        for r in rows:
            st = stock_map.get(r["product_id"])
            if (not st) or (int(st.qty) < int(r["qty"])):
                messages.error(request, f"Нет в наличии: {r['product'].name_ru}")
                return redirect("shops:cart_detail", branch_id=branch.id)

        subtotal = cart["subtotal"]
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

        # позиции + списание
        for r in rows:
            st = stock_map[r["product_id"]]
            price = dec(st.product.price)
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

    # чистим корзину после успешного заказа
    clear_shop_cart(request, branch)

    # текст заказа (для success + копирование + WA)
    order_text = _build_shop_order_text(order, items_payload, is_delivery=is_delivery)
    request.session["shop_last_order_text"] = order_text
    request.session.modified = True

    # TG
    # from shops.tasks import notify_new_shop_order
    # notify_new_shop_order.delay(order.id)
    from shops.tasks import notify_new_shop_order
    notify_new_shop_order.delay(order.id)


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
             .prefetch_related("items__product")
             .get(pk=order_id, branch_id=branch_id))

    order_text = request.session.get("shop_last_order_text", "")

    wa_phone = _wa_digits(order.branch.phone)
    wa_url = f"https://wa.me/{wa_phone}?text={quote(order_text)}" if wa_phone else ""

    wa_phone2 = _wa_digits(order.branch.phone2)
    wa_url2 = f"https://wa.me/{wa_phone2}?text={quote(order_text)}" if wa_phone2 else ""

    preview_items = list(order.items.all()[:2])

    return render(request, "shops/checkout_success.html", {
        "order": order,
        "wa_url": wa_url,
        "wa_url2": wa_url2,
        "order_text": order_text,
        "preview_items": preview_items,
    })
