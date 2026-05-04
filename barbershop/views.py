import json
from datetime import date, datetime, timedelta
from urllib.parse import quote
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import (Barbershop, ServiceCategory, Service, Barber,
                     BarberSchedule, Appointment)


def _get_bot_token():
    return (getattr(settings, "TG_BOT_TOKEN", "") or
            getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()


def _tg_notify(shop, text):
    token = _get_bot_token()
    if not token or not shop.tg_chat_id:
        return
    try:
        import requests as req
        payload = {"chat_id": shop.tg_chat_id, "text": text,
                   "parse_mode": "HTML", "disable_web_page_preview": True}
        if shop.tg_thread_id:
            payload["message_thread_id"] = shop.tg_thread_id
        req.post(f"https://api.telegram.org/bot{token}/sendMessage",
                 json=payload, timeout=8)
    except Exception:
        pass


def _available_slots(barber, appt_date, duration_min):
    """Return list of 'HH:MM' strings for available slots."""
    weekday = appt_date.weekday()
    try:
        schedule = barber.schedules.get(weekday=weekday, is_working=True)
    except BarberSchedule.DoesNotExist:
        return []

    # existing appointments for this barber on this date (active statuses)
    existing = list(
        Appointment.objects.filter(
            barber=barber,
            appt_date=appt_date,
            status__in=["new", "confirmed"],
        ).values_list("appt_time", "duration_min")
    )

    slots = []
    slot_step = timedelta(minutes=30)
    current = datetime.combine(appt_date, schedule.start_time)
    end_dt  = datetime.combine(appt_date, schedule.end_time)
    dur     = timedelta(minutes=duration_min)

    while current + dur <= end_dt:
        slot_end = current + dur
        # Check overlap
        overlap = False
        for (existing_time, existing_dur) in existing:
            ex_start = datetime.combine(appt_date, existing_time)
            ex_end   = ex_start + timedelta(minutes=existing_dur or 30)
            if current < ex_end and slot_end > ex_start:
                overlap = True
                break
        if not overlap:
            slots.append(current.strftime("%H:%M"))
        current += slot_step

    return slots


def index(request):
    shops = Barbershop.objects.filter(is_active=True).order_by("sort_order", "name")
    return render(request, "barbershop/index.html", {"shops": shops})


def venue(request, slug):
    shop = get_object_or_404(Barbershop, slug=slug, is_active=True)
    categories = (ServiceCategory.objects
                  .filter(barbershop=shop, is_active=True)
                  .prefetch_related("services")
                  .order_by("sort_order", "id"))
    barbers = (Barber.objects
               .filter(barbershop=shop, is_active=True)
               .prefetch_related("barber_services__service")
               .order_by("sort_order", "id"))
    return render(request, "barbershop/venue.html", {
        "shop": shop, "categories": categories, "barbers": barbers,
    })


def book(request, slug):
    shop = get_object_or_404(Barbershop, slug=slug, is_active=True)
    categories = (ServiceCategory.objects
                  .filter(barbershop=shop, is_active=True)
                  .prefetch_related("services")
                  .order_by("sort_order", "id"))
    services_json = json.dumps([
        {
            "id": svc.id, "name": svc.name,
            "price": int(svc.price), "duration": svc.duration_min,
            "category": svc.category_id,
        }
        for cat in categories for svc in cat.services.filter(is_active=True)
    ], ensure_ascii=False)
    categories_json = json.dumps([
        {"id": c.id, "name": c.name} for c in categories
    ], ensure_ascii=False)
    return render(request, "barbershop/book.html", {
        "shop": shop,
        "services_json": services_json,
        "categories_json": categories_json,
    })


def barbers_json(request, slug):
    shop = get_object_or_404(Barbershop, slug=slug, is_active=True)
    service_id = request.GET.get("service")
    qs = Barber.objects.filter(barbershop=shop, is_active=True).order_by("sort_order")
    if service_id:
        qs = qs.filter(barber_services__service_id=service_id)
    data = []
    for b in qs:
        data.append({
            "id": b.id,
            "name": b.name,
            "experience": b.experience,
            "photo": b.photo.url if b.photo else "",
        })
    return JsonResponse({"barbers": data})


def slots_json(request, slug):
    shop = get_object_or_404(Barbershop, slug=slug, is_active=True)
    barber_id   = request.GET.get("barber")
    service_id  = request.GET.get("service")
    date_str    = request.GET.get("date")
    if not (barber_id and service_id and date_str):
        return JsonResponse({"slots": []})
    try:
        barber      = Barber.objects.get(id=barber_id, barbershop=shop, is_active=True)
        service     = Service.objects.get(id=service_id, barbershop=shop, is_active=True)
        appt_date   = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return JsonResponse({"slots": []})
    if appt_date < date.today():
        return JsonResponse({"slots": []})
    slots = _available_slots(barber, appt_date, service.duration_min)
    return JsonResponse({"slots": slots})


@require_POST
def book_confirm(request, slug):
    shop = get_object_or_404(Barbershop, slug=slug, is_active=True)
    service_id  = request.POST.get("service_id")
    barber_id   = request.POST.get("barber_id")
    date_str    = request.POST.get("appt_date")
    time_str    = request.POST.get("appt_time")
    name        = (request.POST.get("name") or "").strip() or "Клиент"
    phone       = (request.POST.get("phone") or "").strip()

    try:
        service   = Service.objects.get(id=service_id, barbershop=shop, is_active=True)
        barber    = Barber.objects.get(id=barber_id, barbershop=shop, is_active=True)
        appt_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        appt_time = datetime.strptime(time_str, "%H:%M").time()
    except Exception:
        return redirect("barbershop:book", slug=slug)

    appt = Appointment.objects.create(
        barbershop=shop,
        barber=barber,
        service=service,
        service_name=service.name,
        barber_name=barber.name,
        price_snapshot=service.price,
        duration_min=service.duration_min,
        customer_name=name,
        customer_phone=phone,
        appt_date=appt_date,
        appt_time=appt_time,
        status="new",
        source="online",
    )

    # Telegram notification
    weekday_ru = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    date_fmt = appt_date.strftime("%d.%m.%Y") + f" ({weekday_ru[appt_date.weekday()]})"
    tg_text = (
        f"✂️ <b>Новая запись #{appt.id}</b>\n"
        f"📋 Услуга: {service.name} — {int(service.price)} сом ({service.duration_min} мин)\n"
        f"👤 Мастер: {barber.name}\n"
        f"📅 Дата: {date_fmt} в {time_str}\n"
        f"👤 Клиент: {name}\n"
        f"📞 Телефон: {phone or '—'}"
    )
    _tg_notify(shop, tg_text)

    # WhatsApp notification to admin
    wa_msg = (
        f"Новая запись #{appt.id}\n"
        f"Услуга: {service.name} ({int(service.price)} сом)\n"
        f"Мастер: {barber.name}\n"
        f"Дата: {date_fmt} в {time_str}\n"
        f"Клиент: {name} {phone}"
    )
    wa_number = "".join(c for c in (shop.whatsapp or "") if c.isdigit())
    request.session[f"bs_appt_{slug}"] = appt.id
    return redirect("barbershop:book_success", slug=slug)


def book_success(request, slug):
    shop = get_object_or_404(Barbershop, slug=slug, is_active=True)
    appt_id = request.session.pop(f"bs_appt_{slug}", None)
    appt = None
    if appt_id:
        try:
            appt = Appointment.objects.get(id=appt_id)
        except Appointment.DoesNotExist:
            pass
    return render(request, "barbershop/success.html", {"shop": shop, "appt": appt})
