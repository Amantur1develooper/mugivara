# pharmacy/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.translation import get_language
from .models import Pharmacy, PharmacyBranch, DrugCategory, DrugInCategory, BranchDrug, Drug
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils.translation import gettext as _
from decimal import Decimal
from urllib.parse import quote
from django.http import HttpResponseRedirect
from pharmacy.tasks import notify_new_pharmacy_order
from .cart import get_cart, add_to_cart, set_qty, clear_cart, cart_details
from .models import PharmacyOrder, PharmacyOrderItem, BranchDrug

def build_whatsapp_url(phone: str, text: str) -> str:
    phone = (phone or "").strip()
    phone = phone.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    encoded = quote(text)

    # если у филиала есть номер — откроется чат аптеки
    if phone:
        return f"https://wa.me/{phone}?text={encoded}"

    # если номера нет — откроется WhatsApp и предложит выбрать чат
    return f"https://wa.me/?text={encoded}"

def tr(obj, base: str, lang: str):
    field = f"{base}_{lang}"
    if hasattr(obj, field):
        v = getattr(obj, field) or ""
        return v or getattr(obj, f"{base}_ru", "") or ""
    return getattr(obj, base, "")

def pharmacy_list(request):
    q = (request.GET.get("q") or "").strip()
    pharmacies = Pharmacy.objects.filter(is_active=True).order_by("name_ru")
    if q:
        pharmacies = pharmacies.filter(name_ru__icontains=q)
    return render(request, "pharmacy/pharmacy_list.html", {"pharmacies": pharmacies, "q": q})

def pharmacy_detail(request, slug):
    pharmacy = get_object_or_404(Pharmacy, slug=slug, is_active=True)
    branches = pharmacy.branches.filter(is_active=True).order_by("name_ru")
    return render(request, "pharmacy/pharmacy_detail.html", {"pharmacy": pharmacy, "branches": branches})

def branch_catalog(request, branch_id: int):
    branch = get_object_or_404(PharmacyBranch, id=branch_id, is_active=True)
    pharmacy = branch.pharmacy
    lang = (get_language() or "ru")[:2]

    cats = DrugCategory.objects.filter(pharmacy=pharmacy, is_active=True).order_by("sort_order", "id")

    # соберём лекарства по категориям, но показываем только те, что есть в филиале и available
    menu = []
    for cat in cats:
        links = (DrugInCategory.objects
                 .select_related("drug")
                 .filter(category=cat, drug__is_active=True)
                 .order_by("sort_order", "id"))

        drug_ids = [x.drug_id for x in links]
        branch_map = {bd.drug_id: bd for bd in BranchDrug.objects.filter(branch=branch, drug_id__in=drug_ids, is_available=True)}

        items = []
        for ln in links:
            bd = branch_map.get(ln.drug_id)
            if not bd:
                continue
            items.append({"drug": ln.drug, "bd": bd})

        if items:
            menu.append({"category": cat, "items": items})
    cart = get_cart(request, branch.id)
    _, subtotal, qty_total = cart_details(branch, cart)

    return render(request, "pharmacy/branch_catalog.html", {
    "branch": branch,
    "pharmacy": pharmacy,
    "menu": menu,
    "lang": lang,

    # для base.html (FAB корзины)
    "is_pharmacy": True,
    "cart_qty": qty_total,
    "cart_total": subtotal,
        })
    # return render(request, "pharmacy/branch_catalog.html", {
    #     "branch": branch,
    #     "pharmacy": pharmacy,
    #     "menu": menu,
    #     "lang": lang,
    # })

def drug_detail(request, branch_id: int, drug_id: int):
    branch = get_object_or_404(PharmacyBranch, id=branch_id, is_active=True)
    drug = get_object_or_404(Drug, id=drug_id, pharmacy=branch.pharmacy, is_active=True)
    bd = BranchDrug.objects.filter(branch=branch, drug=drug).first()
    lang = (get_language() or "ru")[:2]
    cart = get_cart(request, branch.id)
    _, subtotal, qty_total = cart_details(branch, cart)

    return render(request, "pharmacy/drug_detail.html", {
    "branch": branch,
     "drug": drug,
        "bd": bd,
  
    "lang": lang,

    # для base.html (FAB корзины)
    "is_pharmacy": True,
    "cart_qty": qty_total,
    "cart_total": subtotal,
        })
    

@require_POST
def cart_add(request, branch_id: int, branch_drug_id: int):
    branch = get_object_or_404(PharmacyBranch, id=branch_id, is_active=True)
    bd = get_object_or_404(BranchDrug, id=branch_drug_id, branch=branch, is_available=True)

    qty = int(request.POST.get("qty") or 1)
    qty = max(1, min(qty, 99))

    add_to_cart(request, branch.id, bd.id, qty)

    cart = get_cart(request, branch.id)
    _, subtotal, qty_total = cart_details(branch, cart)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "qty": qty_total, "total": str(subtotal)})

    return redirect("pharmacy:cart_detail", branch_id=branch.id)


def cart_detail(request, branch_id: int):
    branch = get_object_or_404(PharmacyBranch, id=branch_id, is_active=True)
    cart = get_cart(request, branch.id)
    rows, subtotal, qty_total = cart_details(branch, cart)

    return render(request, "pharmacy/cart_detail.html", {
        "branch": branch,
        "rows": rows,
        "qty_total": qty_total,
        "subtotal": subtotal,
        "total": subtotal,

        "is_pharmacy": True,
        "cart_qty": qty_total,
        "cart_total": subtotal,
    })


@require_POST
def cart_update(request, branch_id: int, branch_drug_id: int):
    branch = get_object_or_404(PharmacyBranch, id=branch_id, is_active=True)
    qty = int(request.POST.get("qty") or 1)
    set_qty(request, branch.id, branch_drug_id, qty)
    return redirect("pharmacy:cart_detail", branch_id=branch.id)


@require_POST
def cart_remove(request, branch_id: int, branch_drug_id: int):
    branch = get_object_or_404(PharmacyBranch, id=branch_id, is_active=True)
    set_qty(request, branch.id, branch_drug_id, 0)
    return redirect("pharmacy:cart_detail", branch_id=branch.id)

@require_POST
def checkout(request, branch_id: int):
    branch = get_object_or_404(PharmacyBranch, id=branch_id, is_active=True)

    cart = get_cart(request, branch.id)
    rows, subtotal, qty_total = cart_details(branch, cart)

    if qty_total == 0:
        messages.error(request, _("Корзина пуста."))
        return redirect("pharmacy:cart_detail", branch_id=branch.id)

    name = (request.POST.get("name") or "").strip()
    phone = (request.POST.get("phone") or "").strip()
    address = (request.POST.get("address") or "").strip()
    comment = (request.POST.get("comment") or "").strip()

    payment_method = request.POST.get("payment_method") or PharmacyOrder.PaymentMethod.CASH
    if payment_method not in [PharmacyOrder.PaymentMethod.CASH, PharmacyOrder.PaymentMethod.ONLINE]:
        payment_method = PharmacyOrder.PaymentMethod.CASH

    # 1) создаём заказ
    order = PharmacyOrder.objects.create(
        branch=branch,
        status=PharmacyOrder.Status.NEW,
        customer_name=name,
        customer_phone=phone,
        delivery_address=address,
        comment=comment,
        total_amount=subtotal,
        payment_method=payment_method,
        payment_status=PharmacyOrder.PaymentStatus.UNPAID,
    )

    # 2) позиции
    lines = []
    for i, r in enumerate(rows, start=1):
        bd = r["bd"]
        qty = r["qty"]
        PharmacyOrderItem.objects.create(
            order=order,
            drug=bd.drug,
            qty=qty,
            price_snapshot=bd.price,
            line_total=bd.price * qty,
        )
        lines.append(f"{i}) {bd.drug.name_ru} × {qty} = {r['line_total']} сом")

    # 3) чистим корзину
    clear_cart(request, branch.id)

    # 4) TG уведомление (если есть)
    # notify_new_pharmacy_order.delay(order.id)

    # 5) формируем текст WhatsApp
    pay_text = _("Наличные") if payment_method == PharmacyOrder.PaymentMethod.CASH else _("Онлайн")

    text = (
        f"🧾 Заказ #{order.id}\n"
        f"🏥 Аптека: {branch.pharmacy.name_ru}\n"
        f"📍 Филиал: {branch.name_ru}\n"
        f"📌 Адрес филиала: {branch.address}\n\n"
        f"👤 Клиент: {name or '—'}\n"
        f"📞 Тел: {phone or '—'}\n"
        f"🏠 Адрес (если доставка): {address or '—'}\n"
        f"💳 Оплата: {pay_text}\n"
        f"💬 Комментарий: {comment or '—'}\n\n"
        + "\n".join(lines)
        + f"\n\n💰 Итого: {order.total_amount} сом"
    )

    whatsapp_url = build_whatsapp_url(branch.phone, text)
    # ✅ TG уведомление всегда
    notify_new_pharmacy_order.delay(order.id)

# ✅ WhatsApp только если поставили галочку
    # send_whatsapp = request.POST.get("send_whatsapp") == "1"
    # if send_whatsapp:
    #     # whatsapp_url = build_whatsapp_url(branch.phone, text)
    return HttpResponseRedirect(whatsapp_url)

    # иначе обычный success
    return redirect("pharmacy:checkout_success", branch_id=branch.id, order_id=order.id)
    # 6) сразу уводим в WhatsApp
    # return HttpResponseRedirect(whatsapp_url)


def checkout_success(request, branch_id: int, order_id: int):
    branch = get_object_or_404(PharmacyBranch, id=branch_id, is_active=True)
    order = get_object_or_404(PharmacyOrder, id=order_id, branch=branch)
    return render(request, "pharmacy/checkout_success.html", {
        "branch": branch,
        "order": order,
        "is_pharmacy": True,
        "cart_qty": 0,
        "cart_total": 0,
    })