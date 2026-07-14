import json
from datetime import datetime, date, time, timedelta
from urllib.parse import quote

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import Machine, Session, SessionType, SimRacingVenue, SimRacingAppointment


def _tg_notify(venue, text):
    try:
        token = (getattr(settings, "TG_BOT_TOKEN", "") or
                 getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
        if not token or not venue.tg_chat_id:
            return
        import requests as req
        payload = {"chat_id": venue.tg_chat_id, "text": text,
                   "parse_mode": "HTML", "disable_web_page_preview": True}
        if venue.tg_thread_id:
            payload["message_thread_id"] = venue.tg_thread_id
        req.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=8)
    except Exception:
        pass


def _parse_working_hours(working_hours_str):
    """Parse '10:00 - 22:00' → (time(10,0), time(22,0)) or None."""
    if not working_hours_str:
        return None, None
    import re
    m = re.search(r'(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})', working_hours_str)
    if not m:
        return None, None
    return time(int(m.group(1)), int(m.group(2))), time(int(m.group(3)), int(m.group(4)))


def _generate_slots(open_t, close_t, duration_total, appt_date, booked_intervals):
    """Generate 30-min interval slots between open/close, filtering booked + past."""
    slots = []
    if not open_t or not close_t:
        # fallback: 10:00–22:00
        open_t, close_t = time(10, 0), time(22, 0)

    cursor = datetime.combine(appt_date, open_t)
    end_boundary = datetime.combine(appt_date, close_t)
    now_dt = datetime.now()

    while cursor + timedelta(minutes=duration_total) <= end_boundary:
        slot_end = cursor + timedelta(minutes=duration_total)
        # skip past slots (with 15-min buffer for today)
        if appt_date == date.today() and cursor <= now_dt + timedelta(minutes=15):
            cursor += timedelta(minutes=30)
            continue
        # check conflicts with existing appointments
        conflict = False
        for (b_start, b_end) in booked_intervals:
            if cursor < b_end and slot_end > b_start:
                conflict = True
                break
        if not conflict:
            slots.append(cursor.strftime("%H:%M"))
        cursor += timedelta(minutes=30)

    return slots


def venue(request, slug):
    v = get_object_or_404(SimRacingVenue, slug=slug, is_active=True)

    machines = (
        Machine.objects
        .filter(venue=v)
        .prefetch_related("sessions")
        .order_by("sort_order", "id")
    )

    active_sessions = {
        s.machine_id: s
        for s in Session.objects.filter(venue=v, status=Session.Status.ACTIVE).select_related("machine")
    }

    session_types = (
        SessionType.objects
        .filter(venue=v, is_active=True)
        .order_by("machine_type", "sort_order", "duration_minutes")
    )

    st_by_type = {}
    for st in session_types:
        st_by_type.setdefault(st.machine_type, []).append({
            "id": st.id,
            "duration": st.duration_minutes,
            "price": int(st.price),
            "label": f"{st.duration_minutes} мин — {int(st.price)} сом",
        })

    # Types that have active machines
    active_types = set(
        machines.filter(is_active=True).values_list("type", flat=True)
    )

    machine_types_available = [
        {"value": v_type, "label": label, "has_price": v_type in st_by_type}
        for v_type, label in Machine.Type.choices
        if v_type in active_types
    ]

    machines_data = []
    for m in machines:
        active = active_sessions.get(m.id)
        machines_data.append({
            "machine": m,
            "active_session": active,
            "session_types_json": json.dumps(st_by_type.get(m.type, [])),
        })

    return render(request, "simracing/venue.html", {
        "venue": v,
        "machines_data": machines_data,
        "st_by_type_json": json.dumps(st_by_type, ensure_ascii=False),
        "machine_types_json": json.dumps(machine_types_available, ensure_ascii=False),
        "slots_url": f"/simracing/{slug}/slots.json",
    })


def slots_json(request, slug):
    """Return available time slots for a given date and machine_type."""
    v = get_object_or_404(SimRacingVenue, slug=slug, is_active=True)
    machine_type = request.GET.get("machine_type", "")
    date_str = request.GET.get("date", "")
    st_id = request.GET.get("session_type_id", "")
    qty_raw = request.GET.get("quantity", "1")

    try:
        appt_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        quantity = max(1, int(qty_raw))
    except Exception:
        return JsonResponse({"slots": []})

    if appt_date < date.today():
        return JsonResponse({"slots": []})

    # Get duration for this session type
    duration_per_session = 0
    if st_id:
        try:
            st = SessionType.objects.get(id=st_id, venue=v, is_active=True)
            duration_per_session = st.duration_minutes
        except SessionType.DoesNotExist:
            pass

    if not duration_per_session:
        # fallback: 30 min
        duration_per_session = 30

    duration_total = duration_per_session * quantity

    # Booked intervals for that date + machine_type
    existing = SimRacingAppointment.objects.filter(
        venue=v,
        machine_type=machine_type,
        appt_date=appt_date,
        status__in=["new", "confirmed"],
    )
    booked_intervals = []
    for appt in existing:
        b_start = datetime.combine(appt_date, appt.appt_time)
        b_end = b_start + timedelta(minutes=appt.duration_minutes)
        booked_intervals.append((b_start, b_end))

    open_t, close_t = _parse_working_hours(v.working_hours)
    slots = _generate_slots(open_t, close_t, duration_total, appt_date, booked_intervals)
    return JsonResponse({"slots": slots})


@require_POST
def book_appt(request, slug):
    """Create a pre-booking appointment (online reservation)."""
    v = get_object_or_404(SimRacingVenue, slug=slug, is_active=True)

    machine_type = request.POST.get("machine_type", "")
    st_id = request.POST.get("session_type_id", "")
    date_str = request.POST.get("appt_date", "")
    time_str = request.POST.get("appt_time", "")
    qty_raw = request.POST.get("quantity", "1")
    customer_name = (request.POST.get("name") or "").strip()
    customer_phone = (request.POST.get("phone") or "").strip()

    try:
        st = SessionType.objects.get(id=st_id, venue=v, is_active=True)
        appt_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        appt_time = datetime.strptime(time_str, "%H:%M").time()
        quantity = max(1, int(qty_raw))
    except Exception:
        return redirect("simracing:venue", slug=slug)

    total_price = st.price * quantity
    duration_total = st.duration_minutes * quantity

    appt = SimRacingAppointment.objects.create(
        venue=v,
        machine_type=machine_type,
        session_type=st,
        quantity=quantity,
        appt_date=appt_date,
        appt_time=appt_time,
        customer_name=customer_name or "Гость",
        customer_phone=customer_phone,
        total_price=total_price,
        duration_minutes=duration_total,
        status=SimRacingAppointment.Status.NEW,
    )

    weekday_ru = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    date_fmt = appt_date.strftime("%d.%m.%Y") + f" ({weekday_ru[appt_date.weekday()]})"
    type_label = dict(Machine.Type.choices).get(machine_type, machine_type)
    _tg_notify(
        v,
        f"🏎 <b>Новая запись #{appt.id}</b>\n"
        f"Тип: {type_label}\n"
        f"Сессия: {st.duration_minutes} мин × {quantity} заезд(а) = {duration_total} мин\n"
        f"Итого: {int(total_price)} сом\n"
        f"Дата: {date_fmt} в {time_str}\n"
        f"Клиент: {customer_name or 'Гость'}\n"
        f"Телефон: {customer_phone or '—'}"
    )

    # Redirect to WhatsApp with pre-filled text
    wa_number = "".join(ch for ch in (v.whatsapp or v.phone or "") if ch.isdigit())
    if wa_number:
        wa_text = (
            f"🏎️ Бронирование симрейсинг\n\n"
            f"Тип: {type_label}\n"
            f"Сессия: {st.duration_minutes} мин × {quantity} заезд(а) = {duration_total} мин\n"
            f"Итого: {int(total_price)} сом\n"
            f"Дата: {date_fmt} в {time_str}\n"
            f"Клиент: {customer_name or 'Гость'}\n"
            f"Телефон: {customer_phone or '—'}\n\n"
            f"📋 Запись #{appt.id}"
        )
        return redirect(f"https://wa.me/{wa_number}?text={quote(wa_text)}")

    return redirect("simracing:appt_success", slug=slug, appt_id=appt.id)


def appt_success(request, slug, appt_id):
    v = get_object_or_404(SimRacingVenue, slug=slug)
    appt = get_object_or_404(SimRacingAppointment, id=appt_id, venue=v)
    weekday_ru = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    date_fmt = appt.appt_date.strftime("%d.%m.%Y") + f" ({weekday_ru[appt.appt_date.weekday()]})"
    return render(request, "simracing/appt_success.html", {
        "venue": v,
        "appt": appt,
        "date_fmt": date_fmt,
        "type_label": dict(Machine.Type.choices).get(appt.machine_type, appt.machine_type),
    })


# ── Legacy live-session views (cashier / walk-in) ──────────────────────────

@require_POST
def book(request, slug):
    v = get_object_or_404(SimRacingVenue, slug=slug, is_active=True)

    machine_id = request.POST.get("machine_id", "")
    session_type_id = request.POST.get("session_type_id", "")
    customer_name = (request.POST.get("customer_name") or "").strip()
    customer_phone = (request.POST.get("customer_phone") or "").strip()

    machine = get_object_or_404(Machine, id=machine_id, venue=v, is_active=True)

    if Session.objects.filter(machine=machine, status=Session.Status.ACTIVE).exists():
        return JsonResponse({"ok": False, "error": "Машина уже занята"})

    st = get_object_or_404(SessionType, id=session_type_id, venue=v, is_active=True)

    session = Session.objects.create(
        venue=v,
        machine=machine,
        session_type=st,
        customer_name=customer_name,
        customer_phone=customer_phone,
        duration_minutes=st.duration_minutes,
        price=st.price,
        source="online",
        status=Session.Status.ACTIVE,
    )

    name_str = customer_name or "Гость"
    phone_str = f" ({customer_phone})" if customer_phone else ""
    _tg_notify(
        v,
        f"🏎 <b>Новая сессия</b> #{session.id}\n"
        f"Машина: {machine.name}\n"
        f"Длительность: {st.duration_minutes} мин — {int(st.price)} сом\n"
        f"Клиент: {name_str}{phone_str}\n"
        f"Начало: {timezone.localtime(session.started_at).strftime('%H:%M')}"
    )

    return redirect("simracing:success", slug=slug, session_id=session.id)


def success(request, slug, session_id):
    v = get_object_or_404(SimRacingVenue, slug=slug)
    session = get_object_or_404(Session, id=session_id, venue=v)
    return render(request, "simracing/success.html", {"venue": v, "session": session})


def machines_status(request, slug):
    """JSON endpoint: real-time status of all machines."""
    v = get_object_or_404(SimRacingVenue, slug=slug, is_active=True)
    active = {
        s.machine_id: {
            "ends_at": timezone.localtime(s.ends_at).strftime("%H:%M"),
            "remaining": s.remaining_seconds,
            "is_overtime": s.is_overtime,
        }
        for s in Session.objects.filter(venue=v, status=Session.Status.ACTIVE)
    }
    machines = Machine.objects.filter(venue=v).values("id", "is_active")
    result = []
    for m in machines:
        a = active.get(m["id"])
        result.append({
            "id": m["id"],
            "is_stopped": not m["is_active"],
            "busy": a is not None,
            "active": a,
        })
    return JsonResponse({"machines": result})
