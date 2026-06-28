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


def _today_free_slots(shop):
    """Return sorted list of unique 'HH:MM' free slots across all barbers today (30-min probe)."""
    today = date.today()
    barbers = Barber.objects.filter(barbershop=shop, is_active=True)
    all_slots = set()
    for barber in barbers:
        slots = _available_slots(barber, today, 30)
        all_slots.update(slots)
    return sorted(all_slots)


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
    free_slots = _today_free_slots(shop)
    return render(request, "barbershop/venue.html", {
        "shop": shop, "categories": categories, "barbers": barbers,
        "free_slots": free_slots,
        "free_first": free_slots[0] if free_slots else None,
        "free_last":  free_slots[-1] if free_slots else None,
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
    # Accept comma-separated service IDs: ?services=1,2,3
    raw = request.GET.get("services", request.GET.get("service", ""))
    service_ids = [int(x) for x in raw.split(",") if x.strip().isdigit()]
    qs = Barber.objects.filter(barbershop=shop, is_active=True).order_by("sort_order")
    if service_ids:
        qs = qs.filter(barber_services__service_id__in=service_ids).distinct()
    data = [
        {
            "id": b.id,
            "name": b.name,
            "experience": b.experience,
            "photo": b.photo.url if b.photo else "",
        }
        for b in qs
    ]
    return JsonResponse({"barbers": data})


def slots_json(request, slug):
    shop = get_object_or_404(Barbershop, slug=slug, is_active=True)
    barber_id = request.GET.get("barber")
    date_str  = request.GET.get("date")
    raw       = request.GET.get("services", request.GET.get("service", ""))
    service_ids = [int(x) for x in raw.split(",") if x.strip().isdigit()]
    if not (barber_id and service_ids and date_str):
        return JsonResponse({"slots": []})
    try:
        barber    = Barber.objects.get(id=barber_id, barbershop=shop, is_active=True)
        services  = list(Service.objects.filter(id__in=service_ids, barbershop=shop, is_active=True))
        appt_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return JsonResponse({"slots": []})
    if appt_date < date.today():
        return JsonResponse({"slots": []})
    total_duration = sum(s.duration_min for s in services)
    slots = _available_slots(barber, appt_date, total_duration)
    return JsonResponse({"slots": slots})


@require_POST
def book_confirm(request, slug):
    shop      = get_object_or_404(Barbershop, slug=slug, is_active=True)
    barber_id = request.POST.get("barber_id")
    date_str  = request.POST.get("appt_date")
    time_str  = request.POST.get("appt_time")
    name      = (request.POST.get("name") or "").strip() or "Клиент"
    phone     = (request.POST.get("phone") or "").strip()
    # Multiple services: comma-separated IDs
    raw_ids   = request.POST.get("service_ids", request.POST.get("service_id", ""))
    service_ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]

    try:
        services  = list(Service.objects.filter(id__in=service_ids, barbershop=shop, is_active=True))
        barber    = Barber.objects.get(id=barber_id, barbershop=shop, is_active=True)
        appt_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        appt_time = datetime.strptime(time_str, "%H:%M").time()
    except Exception:
        return redirect("barbershop:book", slug=slug)

    if not services:
        return redirect("barbershop:book", slug=slug)

    total_price    = sum(s.price for s in services)
    total_duration = sum(s.duration_min for s in services)
    service_names  = " + ".join(s.name for s in services)
    primary_service = services[0]

    appt = Appointment.objects.create(
        barbershop=shop,
        barber=barber,
        service=primary_service,
        service_name=service_names,
        barber_name=barber.name,
        price_snapshot=total_price,
        duration_min=total_duration,
        customer_name=name,
        customer_phone=phone,
        appt_date=appt_date,
        appt_time=appt_time,
        status="new",
        source="online",
    )

    weekday_ru = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    date_fmt = appt_date.strftime("%d.%m.%Y") + f" ({weekday_ru[appt_date.weekday()]})"
    svc_lines = "\n".join(
        f"  • {s.name} — {int(s.price)} сом ({s.duration_min} мин)" for s in services
    )
    tg_text = (
        f"✂️ <b>Новая запись #{appt.id}</b>\n"
        f"📋 Услуги:\n{svc_lines}\n"
        f"💰 Итого: {int(total_price)} сом ({total_duration} мин)\n"
        f"👤 Мастер: {barber.name}\n"
        f"📅 Дата: {date_fmt} в {time_str}\n"
        f"👤 Клиент: {name}\n"
        f"📞 Телефон: {phone or '—'}"
    )
    _tg_notify(shop, tg_text)

    wa_number = "".join(ch for ch in (shop.whatsapp or shop.phone or "") if ch.isdigit())
    if wa_number:
        wa_text = (
            f"✂️ Новая запись\n\n"
            f"Услуги: {service_names}\n"
            f"Мастер: {barber.name}\n"
            f"Дата: {date_fmt} в {time_str}\n"
            f"Итого: {int(total_price)} сом ({total_duration} мин)\n\n"
            f"Клиент: {name}\n"
            f"Телефон: {phone or '—'}"
        )
        request.session[f"bs_appt_{slug}"] = appt.id
        return redirect(f"https://wa.me/{wa_number}?text={quote(wa_text)}")

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
