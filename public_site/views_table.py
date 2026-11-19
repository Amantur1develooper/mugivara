
# public_site/views_table.py
from integrations.dispatch import send_now
import json
from collections import Counter
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import JsonResponse, Http404
from django.contrib import messages
from django.utils.translation import gettext as _
from decimal import Decimal
from django.db import transaction
from django.db.models import F

from reservations.models import Place
from core.models import Branch, Restaurant
from catalog.models import BranchCategory, BranchCategoryItem, BranchItem, ItemCategory, DishConstructor
from orders.models import Order, OrderItem, ConstructorOrderItem
from .cart import get_cart, cart_details, clear_cart
from public_site.cart import get_table_cart, set_table_cart, clear_table_cart, table_cart_totals


def _get_active_place_and_branch(token: str):
    """
    Находит место (стол) по QR-токену и филиал, которому оно принадлежит.

    Если место, его филиал ИЛИ ресторан филиала не активны (is_active=False) —
    QR-меню/заказ/корзина/вызов официанта для этого стола не должны работать:
    бросаем 404, как будто такого стола вообще нет. Это единая точка проверки
    для всех table_*-вьюх ниже — раньше каждая проверяла только Place.is_active,
    и выключенный ресторан/филиал никак не блокировал уже открытые QR-коды.
    """
    place = get_object_or_404(
        Place.objects.select_related("floor__branch__restaurant"),
        token=token, is_active=True,
    )
    branch = place.floor.branch
    if not branch.is_active or not branch.restaurant.is_active:
        raise Http404("Branch or restaurant is not active")
    return place, branch


def _table_cart_key(token: str) -> str:
    return f"table_cart_{token}"


def _get_cart(request, token: str) -> dict:
    return request.session.get(_table_cart_key(token), {})  # {"12": 2, "15": 1}


def _save_cart(request, token: str, cart: dict):
    request.session[_table_cart_key(token)] = cart
    request.session.modified = True


def _cart_calc(branch, cart: dict):
    """cart: {"branch_item_id" или "id:размер": qty}

    Разбор ключей и цену за размер считает общий модуль корзины: столик и
    онлайн-заказ должны считать одинаково, иначе одно и то же блюдо в зале
    и на доставке стоило бы по-разному.
    """
    from public_site.cart import table_cart_totals

    rows, subtotal, qty_total = table_cart_totals(branch, cart or {})
    return rows, qty_total, subtotal


# ── КОНСТРУКТОР КОРЗИНА (table QR flow) ──────────────────────────────────────

def _table_cx_key(token: str) -> str:
    return f"table_cx_{token}"


def _get_cx_cart(request, token: str) -> list:
    return request.session.get(_table_cx_key(token), [])


def _save_cx_cart(request, token: str, cart: list):
    request.session[_table_cx_key(token)] = cart
    request.session.modified = True


def _cx_cart_totals(cx_cart: list):
    """Returns (total_qty, total_sum) for constructor cart."""
    total_qty = 0
    total_sum = Decimal("0")
    for item in cx_cart:
        q = int(item.get("qty", 0))
        if q <= 0:
            continue
        total_qty += q
        total_sum += Decimal(str(item["unit_price"])) * q
    return total_qty, total_sum


def _build_branch_menu(branch):
    """
    menu как в твоём шаблоне: [{branch_category, items:[{branch_item}...]}]
    ВАЖНО: для QR-стола НЕ фильтруем delivery_available.
    """
    menu = []
    cats = (BranchCategory.objects
            .filter(branch=branch, is_active=True)
            .select_related("category")
            .order_by("sort_order", "id"))

    for bc in cats:
        item_ids = ItemCategory.objects.filter(category=bc.category).values_list("item_id", flat=True)
        bis = (BranchItem.objects
               .filter(branch=branch, is_available=True, item_id__in=item_ids)
               .select_related("item")
               .order_by("sort_order", "id"))

        menu.append({
            "branch_category": bc,
            "items": [{"branch_item": bi} for bi in bis],
        })
    return menu







def _size_for(bi, raw):
    """id размера из запроса, проверенный по блюду. None — размеров нет."""
    sizes = bi.size_list()
    if not sizes:
        return None
    try:
        chosen = int(raw)
    except (TypeError, ValueError):
        chosen = None
    if chosen and any(z.id == chosen for z in sizes):
        return chosen
    default = bi.default_size()
    return default.id if default else None

@require_POST
def table_add_to_cart(request, token, branch_item_id: int):
    place, branch = _get_active_place_and_branch(token)

    bi = get_object_or_404(BranchItem, id=branch_item_id, branch=branch, is_available=True)

    qty = int(request.POST.get("qty") or 1)
    if qty < 1:
        qty = 1

    # Размер: не прислали — берём по умолчанию, иначе цена уехала бы
    from public_site.cart import make_key
    size_id = _size_for(bi, request.POST.get("size_id"))

    cart = _get_cart(request, token)
    k = make_key(bi.id, size_id)
    cart[k] = int(cart.get(k, 0)) + qty
    _save_cart(request, token, cart)

    _, reg_qty, reg_total = _cart_calc(branch, cart)
    cx_qty, cx_total = _cx_cart_totals(_get_cx_cart(request, token))
    return JsonResponse({"ok": True, "qty": reg_qty + cx_qty, "total": float(reg_total + cx_total)})


@require_POST
def table_add_constructor(request, token: str, cx_id: int):
    """Add a constructor dish to the table cart."""
    place, branch = _get_active_place_and_branch(token)
    cx = get_object_or_404(DishConstructor, id=cx_id, branch=branch, is_active=True)

    try:
        selections_raw = json.loads(request.POST.get("selections", "{}"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Неверные данные"}, status=400)

    groups = cx.groups.prefetch_related("ingredients").order_by("sort_order", "id")
    selections = []
    total_price = Decimal("0")

    for g in groups:
        chosen_ids = selections_raw.get(str(g.id), [])
        if not isinstance(chosen_ids, list):
            chosen_ids = [chosen_ids]
        chosen_ids = [int(i) for i in chosen_ids if i]

        if g.min_select and len(chosen_ids) < g.min_select:
            return JsonResponse({"ok": False, "error": f"Выберите минимум {g.min_select} в «{g.name}»"}, status=400)
        if g.max_select > 0 and len(chosen_ids) > g.max_select:
            return JsonResponse({"ok": False, "error": f"Максимум {g.max_select} в «{g.name}»"}, status=400)

        id_counts = Counter(chosen_ids)
        ings_data = []
        for ing in g.ingredients.select_related("branch_item__item").filter(is_active=True, id__in=list(id_counts)):
            for _ in range(id_counts[ing.id]):
                ings_data.append({"id": ing.id, "name": ing.display_name, "price": str(ing.display_price)})
                total_price += ing.display_price

        if ings_data:
            selections.append({"gid": g.id, "gname": g.name, "ings": ings_data})

    unit_price = total_price

    cx_cart = _get_cx_cart(request, token)
    idx = max((item["idx"] for item in cx_cart), default=-1) + 1
    cx_cart.append({
        "idx": idx,
        "cx_id": cx.id,
        "cx_name": cx.name,
        "base_price": str(cx.base_price),
        "selections": selections,
        "unit_price": str(unit_price),
        "qty": 1,
        "line_total": str(unit_price),
    })
    _save_cx_cart(request, token, cx_cart)

    cart = _get_cart(request, token)
    _, reg_qty, reg_total = _cart_calc(branch, cart)
    cx_qty, cx_total = _cx_cart_totals(cx_cart)
    return JsonResponse({"ok": True, "qty": reg_qty + cx_qty, "total": float(reg_total + cx_total)})


@require_POST
def table_cx_update(request, token: str):
    """Update qty or remove a constructor cart item."""
    place, branch = _get_active_place_and_branch(token)

    idx = int(request.POST.get("idx") or -1)
    action = (request.POST.get("action") or "").strip()

    cx_cart = _get_cx_cart(request, token)
    item = next((x for x in cx_cart if x["idx"] == idx), None)
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
        cx_cart = [x for x in cx_cart if x["idx"] != idx]
        new_line = Decimal("0")
        new_qty = 0
    else:
        new_line = unit_price * new_qty
        item["line_total"] = str(new_line)

    _save_cx_cart(request, token, cx_cart)

    cart = _get_cart(request, token)
    _, reg_qty, reg_total = _cart_calc(branch, cart)
    cx_qty, cx_total = _cx_cart_totals(cx_cart)

    return JsonResponse({
        "ok": True,
        "item_qty": new_qty,
        "line_total": str(new_line),
        "qty": reg_qty + cx_qty,
        "total": str(reg_total + cx_total),
    })


def _activate_qr_lang(request):
    """QR-страницы вне i18n_patterns: язык берём из cookie переключателя,
    по умолчанию — русский (не подхватываем язык браузера туриста)."""
    from django.conf import settings as _s
    from django.utils import translation
    lang = request.COOKIES.get(_s.LANGUAGE_COOKIE_NAME) or ""
    if lang not in dict(_s.LANGUAGES):
        lang = "ru"
    translation.activate(lang)
    request.LANGUAGE_CODE = lang


def table_cart(request, token):
    _activate_qr_lang(request)

    place, branch = _get_active_place_and_branch(token)

    cart = _get_cart(request, token)
    rows, reg_qty, reg_total = _cart_calc(branch, cart)

    cx_cart = _get_cx_cart(request, token)
    cx_qty, cx_total = _cx_cart_totals(cx_cart)

    return render(request, "public_site/table_cart.html", {
        "token": token,
        "place": place,
        "branch": branch,
        "rows": rows,
        "cx_rows": cx_cart,
        "cart_qty": reg_qty + cx_qty,
        "cart_total": reg_total + cx_total,
        "table": True,
    })


@transaction.atomic
def table_checkout(request, token):
    _activate_qr_lang(request)

    place, branch = _get_active_place_and_branch(token)

    cart = _get_cart(request, token)
    rows, cart_qty, cart_total = _cart_calc(branch, cart)
    # «Собери сам» живёт в отдельной корзине. Раньше эта страница её не знала:
    # гость, собравший только бургер, видел «корзина пуста», а если в заказе
    # были и обычные блюда — собранное молча пропадало.
    cx_rows = _get_cx_cart(request, token)
    cx_qty, cx_total = _cx_cart_totals(cx_rows)
    cart_qty += cx_qty
    cart_total += cx_total
    if cart_qty == 0:
        return redirect("table_menu", token=token)

    if request.method == "POST":
        name = (request.POST.get("customer_name") or "").strip()
        phone = (request.POST.get("customer_phone") or "").strip()
        comment = (request.POST.get("comment") or "").strip()
        promo_code_str = (request.POST.get("promo_code") or "").strip()

        if not name:
            from django.contrib import messages
            messages.error(request, "Укажите ваше имя.")
            return render(request, "public_site/table_checkout.html", {
                "token": token, "place": place, "branch": branch,
                "rows": rows, "cx_rows": cx_rows,
                "cart_qty": cart_qty, "cart_total": cart_total,
            })

        from core.promo import resolve_promo, bump_promo_use
        promo, promo_discount, _fee, _lbl = resolve_promo(
            branch, promo_code_str, cart_total, allow_free_delivery=False,
        )

        order = Order.objects.create(
            type=Order.Type.DINE_IN,              # ✅ В заведении
            branch=branch,
            table_place=place,                    # ✅ привязка к столу
            status=Order.Status.NEW,
            customer_name=name,
            customer_phone=phone,
            comment=comment,
            total_amount=cart_total - promo_discount,
            promo_code=(promo.code if promo else ""),
            promo_discount=promo_discount,
            payment_method=Order.PaymentMethod.CASH,
            payment_status=Order.PaymentStatus.UNPAID,
        )
        if promo:
            bump_promo_use(promo)

        for r in rows:
            bi = r["branch_item"]
            qty = r["qty"]
            line_total = r["line_total"]
            size = r.get("size")
            OrderItem.objects.create(
                order=order,
                item=bi.item,
                size_name=(size.name if size else ""),
                size_factor=(size.tc_factor if size else 1),
                qty=qty,
                price_snapshot=r.get("unit_price", bi.price),
                old_price_snapshot=bi.old_price if bi.is_on_promo and not size else None,
                line_total=line_total,
            )

        for cx_item in cx_rows:
            qty = int(cx_item.get("qty", 1))
            unit_price = Decimal(str(cx_item["unit_price"]))
            cx = DishConstructor.objects.filter(id=cx_item["cx_id"], branch=branch).first()
            ConstructorOrderItem.objects.create(
                order=order,
                constructor=cx,
                constructor_name_snapshot=cx_item["cx_name"],
                qty=qty,
                unit_price=unit_price,
                line_total=unit_price * qty,
                ingredients_snapshot=cx_item.get("selections", []),
            )

        # ✅ очищаем обе корзины — обычную и «Собери сам»
        _save_cart(request, token, {})
        _save_cx_cart(request, token, [])

        # Автоинкремент Restaurant.rating убран: был БЕЗ ограничения, а поле
        # DecimalField(max_digits=3, decimal_places=1) хранит максимум 99.9 —
        # набрав ~100, F("rating")+0.1 ронял UPDATE ошибкой БД "numeric field
        # overflow" прямо внутри этой атомарной транзакции, и весь заказ
        # откатывался (пользователь не мог заказать).

        # Кухонный чек — после коммита транзакции
        # Если print_on_accept включён — печать только по нажатию «Принять заказ» кассиром
        _order_id = order.id
        _print_on_accept = branch.print_on_accept
        def _do_print():
            if _print_on_accept:
                return
            try:
                from printing.jobs import create_print_jobs
                from orders.models import Order as _Ord
                create_print_jobs(
                    _Ord.objects
                    .select_related("table_place__floor", "branch__restaurant")
                    .get(id=_order_id)
                )
            except Exception as e:
                import traceback
                print("PRINT create_print_jobs ERROR (checkout):", e)
                traceback.print_exc()
        transaction.on_commit(_do_print)

        return redirect("table_success", token=token, order_id=order.id)

    return render(request, "public_site/table_checkout.html", {
        "token": token,
        "place": place,
        "branch": branch,
        "rows": rows,
        "cx_rows": cx_rows,
        "cart_qty": cart_qty,
        "cart_total": cart_total,
    })


def table_success(request, token, order_id: int):
    _activate_qr_lang(request)
    place, branch = _get_active_place_and_branch(token)
    order = get_object_or_404(Order, id=order_id, branch=branch)

    return render(request, "public_site/table_success.html", {
        "token": token,
        "place": place,
        "branch": branch,
        "order": order,
    })
def table_menu(request, token: str):
    _activate_qr_lang(request)

    place, branch = _get_active_place_and_branch(token)

    categories = BranchCategory.objects.filter(branch=branch, is_active=True).order_by("sort_order", "id")

    menu = []
    for bc in categories:
        rows = BranchCategoryItem.objects.select_related("branch_item__item").filter(
            branch_category=bc,
            branch_item__is_available=True,
        ).order_by("sort_order", "id")

        menu.append({"branch_category": bc, "items": rows})

    # Конструкторы — показываем только если есть хотя бы один активный
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

    cart = _get_cart(request, token)
    _, reg_qty, reg_total = _cart_calc(branch, cart)
    cx_cart = _get_cx_cart(request, token)
    cx_qty, cx_total = _cx_cart_totals(cx_cart)

    # Все открытые заказы стола (накопительный режим)
    _OPEN = [Order.Status.NEW, Order.Status.ACCEPTED, Order.Status.COOKING, Order.Status.READY]
    open_orders_qs = list(
        Order.objects
        .filter(branch=branch, table_place=place, status__in=_OPEN)
        .prefetch_related("items__item", "constructor_items")
        .order_by("created_at")
    )
    open_order = None
    open_order_items = []   # list of (name, qty, line_total) tuples
    open_order_total = Decimal("0")
    if open_orders_qs:
        open_order = open_orders_qs[0]  # primary (earliest) — for order_id / time ref
        for o in open_orders_qs:
            for oi in o.items.select_related("item").all():
                open_order_items.append({
                    "name": oi.item.name_ru,
                    "qty": oi.qty,
                    "line_total": oi.line_total,
                })
            for coi in o.constructor_items.all():
                open_order_items.append({
                    "name": coi.constructor_name_snapshot or "Конструктор",
                    "qty": coi.qty,
                    "line_total": coi.line_total,
                })
            open_order_total += o.total_amount

    return render(request, "public_site/table_menu.html", {
        "branch": branch,
        "place": place,
        "menu": menu,
        "constructors": constructors,
        "token": token,
        "cart_qty": reg_qty + cx_qty,
        "cart_total": reg_total + cx_total,
        "table": True,
        "open_order": open_order,
        "open_order_items": open_order_items,
        "open_order_total": open_order_total,
    })
    
    
from django.views.decorators.http import require_POST

@require_POST
def table_cart_update(request, token):
    place, branch = _get_active_place_and_branch(token)

    action = (request.POST.get("action") or "").strip()
    bi_id = int(request.POST.get("branch_item_id") or 0)

    bi = get_object_or_404(BranchItem, id=bi_id, branch=branch)

    from public_site.cart import make_key
    raw_size = request.POST.get("size_id")
    size_id = int(raw_size) if (raw_size or "").isdigit() else None

    cart = _get_cart(request, token)  # твоя функция/сессионная корзина
    k = make_key(bi_id, size_id)
    cur = int(cart.get(k, 0))

    if action == "inc":
        new_qty = cur + 1
    elif action == "dec":
        new_qty = cur - 1
    elif action == "remove":
        new_qty = 0
    else:
        return JsonResponse({"ok": False}, status=400)

    if new_qty <= 0:
        cart.pop(k, None)
        new_qty = 0
    else:
        cart[k] = new_qty

    _save_cart(request, token, cart)
    rows, reg_qty, reg_total = _cart_calc(branch, cart)
    cx_qty, cx_total = _cx_cart_totals(_get_cx_cart(request, token))

    # Сумма именно той строки, которую правили: у блюда с размерами строк
    # несколько, и без сверки размера вернулась бы чужая сумма.
    line_total = "0"
    for r in rows:
        if r["branch_item"].id != bi_id:
            continue
        row_size = r.get("size").id if r.get("size") else None
        if row_size == size_id or size_id is None:
            line_total = str(r["line_total"])
            break

    return JsonResponse({
        "ok": True,
        "item_qty": new_qty,
        "line_total": line_total,
        "qty": reg_qty + cx_qty,
        "total": str(reg_total + cx_total),
    })


from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from reservations.models import Place
from integrations.tasks import notify_call_waiter  # сделаем ниже
from django.http import HttpResponse

@require_POST
def table_call_waiter(request, token):
    place, branch = _get_active_place_and_branch(token)

    # можно добавить короткий текст
    note = (request.POST.get("note") or "").strip()[:200]

    send_now(notify_call_waiter, place.id, note)
    return JsonResponse({"ok": True})
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from reservations.models import Place
from orders.models import Order, OrderItem
from catalog.models import BranchItem

@require_POST
def table_create_order(request, token):
    place, branch = _get_active_place_and_branch(token)

    customer_name = (request.POST.get("customer_name") or "").strip()[:120]
    comment = (request.POST.get("comment") or "").strip()
    promo_code_str = (request.POST.get("promo_code") or "").strip()

    if not customer_name:
        return redirect("table_cart", token=token)

    cart = _get_cart(request, token)
    cx_cart = _get_cx_cart(request, token)

    if not cart and not cx_cart:
        return redirect("table_cart", token=token)

    # Считаем заранее, чтобы сигнал при создании получил верную сумму.
    # Разбор ключей корзины и цену за размер отдаём общему модулю: ключ
    # вида «12:5» означает блюдо с выбранным размером.
    rows_calc, _qty_calc, total = _cart_calc(branch, cart)
    cart_rows = [{"bi": r["branch_item"], "qty": r["qty"],
                  "line_total": r["line_total"], "size": r.get("size")}
                 for r in rows_calc]

    for cx_item in cx_cart:
        qty = int(cx_item.get("qty", 1))
        unit_price = Decimal(str(cx_item["unit_price"]))
        total += unit_price * qty

    _OPEN = [Order.Status.NEW, Order.Status.ACCEPTED, Order.Status.COOKING, Order.Status.READY]

    with transaction.atomic():
        existing_order = (
            Order.objects
            .filter(branch=branch, table_place=place, status__in=_OPEN)
            .select_for_update()
            .order_by("-created_at")
            .first()
        )

        if existing_order:
            order = existing_order
            new_oi_ids = []
            new_cx_ids = []
            # Append new items to the existing order
            for row in cart_rows:
                oi = OrderItem.objects.create(
                    order=order,
                    item=row["bi"].item,
                    size_name=(row["size"].name if row.get("size") else ""),
                    size_factor=(row["size"].tc_factor if row.get("size") else 1),
                    qty=row["qty"],
                    price_snapshot=(row["size"].price if row.get("size")
                                    else row["bi"].price),
                    old_price_snapshot=(row["bi"].old_price
                                        if row["bi"].is_on_promo and not row.get("size")
                                        else None),
                    line_total=row["line_total"],
                )
                new_oi_ids.append(oi.id)
            for cx_item in cx_cart:
                qty = int(cx_item.get("qty", 1))
                unit_price = Decimal(str(cx_item["unit_price"]))
                line_total = unit_price * qty
                cx = get_object_or_404(DishConstructor, id=cx_item["cx_id"])
                coi = ConstructorOrderItem.objects.create(
                    order=order,
                    constructor=cx,
                    constructor_name_snapshot=cx_item["cx_name"],
                    qty=qty,
                    unit_price=unit_price,
                    line_total=line_total,
                    ingredients_snapshot=cx_item.get("selections", []),
                )
                new_cx_ids.append(coi.id)
            order.total_amount = order.total_amount + total
            if comment and not order.comment:
                order.comment = comment
            order.save(update_fields=["total_amount", "comment"])
        else:
            from core.promo import resolve_promo, bump_promo_use
            promo, promo_discount, _fee, _lbl = resolve_promo(
                branch, promo_code_str, total, allow_free_delivery=False,
            )
            order = Order.objects.create(
                branch=branch,
                type=Order.Type.DINE_IN,
                table_place=place,
                status=Order.Status.NEW,
                customer_name=customer_name,
                comment=comment,
                total_amount=total - promo_discount,
                promo_code=(promo.code if promo else ""),
                promo_discount=promo_discount,
                payment_method=Order.PaymentMethod.CASH,
                payment_status=Order.PaymentStatus.UNPAID,
            )
            if promo:
                bump_promo_use(promo)

            for row in cart_rows:
                OrderItem.objects.create(
                    order=order,
                    item=row["bi"].item,
                    size_name=(row["size"].name if row.get("size") else ""),
                    size_factor=(row["size"].tc_factor if row.get("size") else 1),
                    qty=row["qty"],
                    price_snapshot=(row["size"].price if row.get("size")
                                    else row["bi"].price),
                    old_price_snapshot=(row["bi"].old_price
                                        if row["bi"].is_on_promo and not row.get("size")
                                        else None),
                    line_total=row["line_total"],
                )

            for cx_item in cx_cart:
                qty = int(cx_item.get("qty", 1))
                unit_price = Decimal(str(cx_item["unit_price"]))
                line_total = unit_price * qty
                cx = get_object_or_404(DishConstructor, id=cx_item["cx_id"])
                ConstructorOrderItem.objects.create(
                    order=order,
                    constructor=cx,
                    constructor_name_snapshot=cx_item["cx_name"],
                    qty=qty,
                    unit_price=unit_price,
                    line_total=line_total,
                    ingredients_snapshot=cx_item.get("selections", []),
                )

            # Автоинкремент Restaurant.rating убран — см. пояснение у первого
            # такого же вызова выше в этом файле (table_create_order).

    _save_cart(request, token, {})
    _save_cx_cart(request, token, [])

    # Кухонный чек → облачная печать (только НОВЫЕ позиции, чтобы не дублировать)
    # Если print_on_accept — ждём подтверждения кассира, печать не нужна
    if not branch.print_on_accept:
        try:
            from printing.jobs import create_print_jobs
            if existing_order:
                create_print_jobs(order, new_item_ids=new_oi_ids, new_cx_ids=new_cx_ids)
            else:
                create_print_jobs(order)
        except Exception as e:
            import traceback
            print("PRINT create_print_jobs ERROR (table):", e)
            traceback.print_exc()

    # Telegram уведомление
    # Для нового заказа — сигнал integrations/signals.py отправляет уведомление автоматически.
    # Здесь отправляем только дозаказ (signal не срабатывает, т.к. Order не создаётся).
    if existing_order:
        try:
            from integrations.tasks import notify_extra_order
            new_items_tg = []
            for row in cart_rows:
                new_items_tg.append({"name": row["bi"].item.name_ru, "qty": row["qty"]})
            for cx_item in cx_cart:
                new_items_tg.append({"name": cx_item.get("cx_name", "Конструктор"), "qty": int(cx_item.get("qty", 1))})
            send_now(notify_extra_order, order.id, new_items_tg)
        except Exception as e:
            print("TG notify_extra_order ERROR:", e)

    return redirect("table_success", token=token, order_id=order.id)


# ── Branch tables — waiter dashboard ─────────────────────────────────────────

def branch_tables_page(request, branch_id):
    from core.models import Branch
    from reservations.models import Floor
    branch = get_object_or_404(
        Branch.objects.select_related("restaurant"), id=branch_id, is_active=True,
    )
    if not branch.restaurant.is_active:
        raise Http404("Restaurant is not active")

    # Open orders for this branch
    _OPEN = [Order.Status.NEW, Order.Status.ACCEPTED, Order.Status.COOKING, Order.Status.READY]
    open_orders = (
        Order.objects
        .filter(
            branch=branch,
            table_place__isnull=False,
            status__in=_OPEN,
        )
        .select_related("table_place")
        .order_by("created_at")
    )
    # Combine all open orders per table: use the earliest order as the primary,
    # sum total_amount across all orders for the table
    order_by_place = {}   # place_id → primary Order (earliest), with summed total
    totals_by_place = {}  # place_id → Decimal sum
    for o in open_orders:
        pid = o.table_place_id
        if pid not in order_by_place:
            order_by_place[pid] = o
            totals_by_place[pid] = Decimal("0")
        totals_by_place[pid] += o.total_amount
    # Patch the primary order's total_amount with the combined total (in memory only)
    for pid, o in order_by_place.items():
        o.total_amount = totals_by_place[pid]

    floors = (Floor.objects
              .filter(branch=branch, is_active=True)
              .prefetch_related("places")
              .order_by("sort_order", "id"))

    import secrets as _secrets
    floors_with_tables = []
    for f in floors:
        places = [p for p in f.places.all() if p.is_active]
        if not places:
            continue
        for p in places:
            # Auto-fix missing tokens (created before save() override was added)
            if not p.token:
                p.token = _secrets.token_urlsafe(10)[:20]
                p.save(update_fields=["token"])
            p.open_order = order_by_place.get(p.id)
        floors_with_tables.append({"floor": f, "places": places})

    return render(request, "public_site/branch_tables.html", {
        "branch": branch,
        "floors": floors_with_tables,
    })


def table_order_json(request, order_id):
    """AJAX: детали открытого заказа для официанта. Возвращает все позиции со стола."""
    order = get_object_or_404(Order, id=order_id)

    _OPEN = [Order.Status.NEW, Order.Status.ACCEPTED, Order.Status.COOKING, Order.Status.READY]

    # Collect all open orders for this table
    if order.table_place_id:
        all_orders = list(
            Order.objects
            .filter(branch=order.branch, table_place_id=order.table_place_id, status__in=_OPEN)
            .prefetch_related("items__item", "constructor_items")
            .order_by("created_at")
        )
        if not all_orders:
            # Order may already be closed — return it alone
            all_orders = [order]
            order.prefetch_related("items__item", "constructor_items")
    else:
        all_orders = [order]

    items = []
    combined_total = Decimal("0")
    for o in all_orders:
        for oi in o.items.select_related("item").all():
            items.append({
                "oi_id": oi.id,
                "type": "item",
                "name": oi.item.name_ru,
                "qty": oi.qty,
                "price": float(oi.price_snapshot),
                "line_total": float(oi.line_total),
            })
        for coi in o.constructor_items.all():
            items.append({
                "oi_id": coi.id,
                "type": "cx",
                "name": coi.constructor_name_snapshot or "Конструктор",
                "qty": coi.qty,
                "price": float(coi.unit_price),
                "line_total": float(coi.line_total),
            })
        combined_total += o.total_amount

    # Статус: NEW если хотя бы один заказ на столе ещё не принят
    earliest_status = all_orders[0].status if all_orders else order.status

    return JsonResponse({
        "ok": True,
        "order": {
            "id": order.id,
            "status": earliest_status,
            "total": float(combined_total),
            "comment": order.comment,
            "customer": order.customer_name,
            "created_at": order.created_at.strftime("%H:%M"),
            "items": items,
        },
    })


@require_POST
def table_waiter_accept(request, order_id):
    """Кассир/официант принимает заказ: статус NEW → ACCEPTED, кухонный чек идёт в печать."""
    order = get_object_or_404(Order, id=order_id)

    _NEW = Order.Status.NEW
    if order.table_place_id:
        new_orders = list(
            Order.objects
            .select_related("table_place__floor", "branch__restaurant")
            .filter(branch=order.branch, table_place_id=order.table_place_id, status=_NEW)
        )
    else:
        new_orders = (
            [Order.objects.select_related("table_place__floor", "branch__restaurant").get(id=order.id)]
            if order.status == _NEW else []
        )

    if not new_orders:
        return JsonResponse({"ok": False, "error": "Нет новых заказов для принятия"})

    for o in new_orders:
        o.status = Order.Status.ACCEPTED
        o.save(update_fields=["status"])
        # печатаем кухонный чек только если так настроено (иначе он уже
        # напечатался при создании заказа — не дублируем)
        if o.branch.print_on_accept:
            try:
                from printing.jobs import create_print_jobs
                create_print_jobs(o)
            except Exception as e:
                import traceback
                print("PRINT create_print_jobs ERROR (accept):", e)
                traceback.print_exc()

    return JsonResponse({"ok": True})


@require_POST
def table_waiter_close(request, order_id):
    """Официант закрывает стол. Закрывает ВСЕ открытые заказы на этом столе. Печатает чек."""
    import json as _json
    order = get_object_or_404(Order, id=order_id)

    if order.status == Order.Status.CLOSED:
        return JsonResponse({"ok": False, "error": "Уже закрыт"})

    try:
        data = _json.loads(request.body)
    except Exception:
        data = {}

    payment = data.get("payment", "cash")

    _OPEN = [Order.Status.NEW, Order.Status.ACCEPTED, Order.Status.COOKING, Order.Status.READY]

    # Close all open orders for this table
    if order.table_place_id:
        all_open = list(
            Order.objects.filter(
                branch=order.branch,
                table_place_id=order.table_place_id,
                status__in=_OPEN,
            )
        )
    else:
        all_open = [order]

    # Статус меняем через общий путь: он же переписывает карточку заказа в
    # группе. Раньше счёт закрывали на сайте, а в Telegram заказ так и
    # оставался открытым, и в группе не понимали, что со столом.
    from orders.flow import apply_status

    combined_total = Decimal("0")
    for o in all_open:
        o.payment_method = payment
        o.save(update_fields=["payment_method"])
        # Чек печатаем один на весь стол ниже, поэтому здесь печать выключена.
        apply_status(o, Order.Status.CLOSED, actor="Официант",
                     payment_status=Order.PaymentStatus.PAID, print_docs=False)
        combined_total += o.total_amount

    # Print receipt for the primary order (which now reflects the full total)
    order.total_amount = combined_total
    order.save(update_fields=["total_amount"])

    try:
        from printing.jobs import create_receipt_job
        create_receipt_job(order)
    except Exception:
        pass

    return JsonResponse({
        "ok": True,
        "order_id": order.id,
        "total": float(combined_total),
    })


@require_POST
def table_waiter_cancel_item(request, order_id):
    """Официант отменяет одну позицию из заказа. Печатает ОТМЕНУ на кухню."""
    import json as _json
    from orders.models import OrderItem, ConstructorOrderItem

    order = get_object_or_404(Order, id=order_id)

    _OPEN = [Order.Status.NEW, Order.Status.ACCEPTED, Order.Status.COOKING, Order.Status.READY]
    if order.status not in _OPEN:
        return JsonResponse({"ok": False, "error": "Заказ уже закрыт"})

    try:
        data = _json.loads(request.body)
    except Exception:
        data = {}

    oi_id = data.get("oi_id")
    item_type = data.get("type", "item")  # "item" | "cx"

    if not oi_id:
        return JsonResponse({"ok": False, "error": "Не указана позиция"}, status=400)

    item_name = ""
    item_qty = 0
    item_line = Decimal("0")
    item_id = None  # для поиска принтера

    with transaction.atomic():
        if item_type == "cx":
            obj = get_object_or_404(ConstructorOrderItem, id=oi_id, order__table_place=order.table_place)
            item_name = obj.constructor_name_snapshot or "Конструктор"
            item_qty = obj.qty
            item_line = obj.line_total
            parent_order = obj.order
            obj.delete()
        else:
            obj = get_object_or_404(OrderItem.objects.select_related("item"), id=oi_id, order__table_place=order.table_place)
            item_name = obj.item.name_ru
            item_qty = obj.qty
            item_line = obj.line_total
            item_id = obj.item_id
            parent_order = obj.order
            obj.delete()

        # Уменьшаем сумму заказа
        parent_order.total_amount = max(Decimal("0"), parent_order.total_amount - item_line)
        parent_order.save(update_fields=["total_amount"])

    # Пересчитываем суммарный итог по всем открытым заказам стола
    from django.db.models import Sum as _Sum
    _OPEN2 = [Order.Status.NEW, Order.Status.ACCEPTED, Order.Status.COOKING, Order.Status.READY]
    new_total = float(
        Order.objects
        .filter(branch=order.branch, table_place_id=order.table_place_id, status__in=_OPEN2)
        .aggregate(s=_Sum('total_amount'))['s']
        or 0
    )

    # Кухонный тикет ОТМЕНА — на принтер этого блюда
    try:
        from printing.jobs import create_cancel_job
        create_cancel_job(order, item_name, item_qty, item_id=item_id)
    except Exception:
        pass

    return JsonResponse({
        "ok": True,
        "cancelled_name": item_name,
        "new_total": new_total,
    })
