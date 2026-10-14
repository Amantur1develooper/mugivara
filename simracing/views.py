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
    """Разбор текстовой подписи часов работы — только для старых записей,
    у которых ещё не заполнены open_time/close_time.
    Понимает «10:00-22:00», «10:00 — 22:00», «с 10:00 до 22:00», «10-22»."""
    if not working_hours_str:
        return None, None
    import re
    t = working_hours_str.lower().replace('—', '-').replace('–', '-')
    m = re.search(r'(\d{1,2})[:.](\d{2})\s*(?:-|до)\s*(\d{1,2})[:.](\d{2})', t)
    if m:
        h1, m1, h2, m2 = (int(x) for x in m.groups())
    else:
        m = re.search(r'(?:с\s*)?(\d{1,2})\s*(?:-|до)\s*(\d{1,2})(?!\d|[:.])', t)
        if not m:
            return None, None
        h1, m1, h2, m2 = int(m.group(1)), 0, int(m.group(2)), 0
    if not (0 <= h1 <= 23 and 0 <= h2 <= 23 and 0 <= m1 <= 59 and 0 <= m2 <= 59):
        return None, None
    return time(h1, m1), time(h2, m2)


def _venue_hours(v):
    """Часы работы площадки. Приоритет — у структурированных полей open_time/close_time;
    текстовая подпись разбирается только как подстраховка для старых записей."""
    if v.open_time and v.close_time:
        return v.open_time, v.close_time
    return _parse_working_hours(v.working_hours)


def _max_concurrent(window_start, window_end, intervals):
    """Максимум одновременно занятых машин внутри окна [start, end).
    Считаем именно пик одновременности, а не число пересечений: семь коротких
    заездов, идущих друг за другом, занимают одну машину, а не семь."""
    events = []
    for b_start, b_end in intervals:
        if b_start < window_end and b_end > window_start:
            events.append((max(b_start, window_start), 1))
            events.append((min(b_end, window_end), -1))
    if not events:
        return 0
    # при совпадении времени сначала освобождение (-1), потом занятие (+1):
    # бронь, которая кончается в 14:30, освобождает машину для той, что с 14:30
    events.sort()
    current = peak = 0
    for _, delta in events:
        current += delta
        peak = max(peak, current)
    return peak


def _generate_slots(open_t, close_t, duration_total, appt_date, booked_intervals,
                    step_minutes=30, capacity=1):
    """Слоты строго внутри часов работы, без прошедших и занятых.
    step_minutes — шаг сетки времени, по умолчанию 30 минут: время предлагается
    на :00 и :30. Длина самой брони берётся из duration_total, поэтому заезд
    может быть и короче шага.
    Если часы работы не заданы — слотов нет (бронировать на закрытое время нельзя)."""
    slots = []
    if not open_t or not close_t:
        return slots
    step = timedelta(minutes=max(5, int(step_minutes or 15)))

    cursor = datetime.combine(appt_date, open_t)
    end_boundary = datetime.combine(appt_date, close_t)
    # Работа после полуночи (например 14:00–02:00): ограничиваемся выбранными сутками.
    # Запись хранится как «дата + время», поэтому слот в 01:00 было бы непонятно,
    # к какой ночи относить. Лучше предложить меньше, чем записать на закрытое время.
    if end_boundary <= cursor:
        end_boundary = datetime.combine(appt_date, time(0, 0)) + timedelta(days=1)
    # «сейчас» по часовому поясу заведения, а не по часам сервера
    now_dt = timezone.localtime(timezone.now()).replace(tzinfo=None)

    while cursor + timedelta(minutes=duration_total) <= end_boundary:
        slot_end = cursor + timedelta(minutes=duration_total)
        # прошедшие слоты не показываем (с запасом 15 минут на сегодня)
        if appt_date == now_dt.date() and cursor <= now_dt + timedelta(minutes=15):
            cursor += step
            continue
        # слот доступен, пока в категории есть свободная машина
        if _max_concurrent(cursor, slot_end, booked_intervals) < max(1, capacity):
            slots.append(cursor.strftime("%H:%M"))
        cursor += step

    return slots


def venues_list(request):
    venues = SimRacingVenue.objects.filter(is_active=True).order_by("sort_order", "id")
    return render(request, "simracing/list.html", {"venues": venues})


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
        {"value": v_type, "label": str(label), "has_price": v_type in st_by_type}
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

    # Кнопки в шапке: WhatsApp и карта.
    # Если у площадки не заполнен whatsapp — берём телефон (как в book_appt),
    # если не заполнена ссылка на карту — ищем по адресу.
    wa_number = "".join(ch for ch in (v.whatsapp or v.phone or "") if ch.isdigit())
    map_url = v.map_url
    if not map_url and v.address:
        map_url = "https://www.google.com/maps/search/?api=1&query=" + quote(v.address)

    return render(request, "simracing/venue.html", {
        "venue": v,
        "machines_data": machines_data,
        "st_by_type_json": json.dumps(st_by_type, ensure_ascii=False),
        "machine_types_json": json.dumps(machine_types_available, ensure_ascii=False),
        "slots_url": f"/simracing/{slug}/slots.json",
        "wa_number": wa_number,
        "map_url": map_url,
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

    # Больше, чем разрешено настройкой площадки, за одну запись брать нельзя
    quantity = min(quantity, max(1, v.max_parallel_bookings))

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

    # Booked intervals for that date + machine_type.
    # Время занимают ТОЛЬКО подтверждённые записи: пока владелец не подтвердил
    # заявку в кабинете, это ещё не бронь — время остаётся свободным в публичной
    # форме и не показывается занятым другим клиентам.
    existing = SimRacingAppointment.objects.filter(
        venue=v,
        machine_type=machine_type,
        appt_date=appt_date,
        status=SimRacingAppointment.Status.CONFIRMED,
    )
    booked_intervals = []
    for appt in existing:
        b_start = datetime.combine(appt_date, appt.appt_time)
        b_end = b_start + timedelta(minutes=appt.duration_minutes)
        booked_intervals.append((b_start, b_end))

    open_t, close_t = _venue_hours(v)
    if not open_t or not close_t:
        # часы работы не настроены — бронировать «вслепую» нельзя
        return JsonResponse({"slots": [], "reason": "no_hours"})
    slots = _generate_slots(open_t, close_t, duration_total, appt_date, booked_intervals,
                            capacity=v.max_parallel_bookings)

    # Какие из слотов попадают под скидку — считаем здесь, чтобы правило
    # жило в одном месте и не разъезжалось с серверным расчётом цены.
    discounted = [
        s for s in slots
        if v.discount_for(appt_date, datetime.strptime(s, "%H:%M").time())
    ]
    return JsonResponse({
        "slots": slots,
        "discounted": discounted,
        "discount_percent": v.discount_percent,
    })


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

    # Лимит заездов за одну запись — из настроек площадки
    if quantity > max(1, v.max_parallel_bookings):
        return redirect("simracing:venue", slug=slug)

    base_price = st.price * quantity
    duration_total = st.duration_minutes * quantity

    # Скидку считаем на сервере по времени заезда — то, что прислал браузер,
    # на цену не влияет.
    discount_percent = v.discount_for(appt_date, appt_time)
    total_price = base_price - (base_price * discount_percent // 100)

    # ── Проверка на сервере: записаться можно только на рабочее время ──
    # JS показывает лишь допустимые слоты, но форму можно отправить и напрямую
    # (или со страницы, открытой час назад), поэтому проверяем здесь ещё раз.
    open_t, close_t = _venue_hours(v)
    if not open_t or not close_t:
        return redirect("simracing:venue", slug=slug)

    start_dt = datetime.combine(appt_date, appt_time)
    end_dt = start_dt + timedelta(minutes=duration_total)
    open_dt = datetime.combine(appt_date, open_t)
    close_dt = datetime.combine(appt_date, close_t)
    if close_dt <= open_dt:                       # работа после полуночи
        close_dt = datetime.combine(appt_date, time(0, 0)) + timedelta(days=1)
    now_local = timezone.localtime(timezone.now()).replace(tzinfo=None)

    if start_dt < open_dt or end_dt > close_dt or start_dt < now_local:
        return redirect("simracing:venue", slug=slug)

    # Вместимость категории: принимаем заявку, пока на это время есть свободная
    # машина. Считается по подтверждённым броням — заявки слот не занимают.
    busy = SimRacingAppointment.objects.filter(
        venue=v, machine_type=machine_type, appt_date=appt_date,
        status=SimRacingAppointment.Status.CONFIRMED,
    )
    busy_intervals = [
        (datetime.combine(appt_date, b.appt_time),
         datetime.combine(appt_date, b.appt_time) + timedelta(minutes=b.duration_minutes))
        for b in busy
    ]
    if _max_concurrent(start_dt, end_dt, busy_intervals) >= max(1, v.max_parallel_bookings):
        return redirect("simracing:venue", slug=slug)

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
        discount_percent=discount_percent,
        duration_minutes=duration_total,
        status=SimRacingAppointment.Status.NEW,
    )

    weekday_ru = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    date_fmt = appt_date.strftime("%d.%m.%Y") + f" ({weekday_ru[appt_date.weekday()]})"
    type_label = dict(Machine.Type.choices).get(machine_type, machine_type)
    disc_line = (
        f"Скидка: −{discount_percent}% (без скидки {int(base_price)} сом)\n"
        if discount_percent else ""
    )
    _tg_notify(
        v,
        f"🏎 <b>Новая запись #{appt.id}</b>\n"
        f"Тип: {type_label}\n"
        f"Сессия: {st.duration_minutes} мин × {quantity} заезд(а) = {duration_total} мин\n"
        f"{disc_line}"
        f"Итого: {int(total_price)} сом\n"
        f"Дата: {date_fmt} в {time_str}\n"
        f"Клиент: {customer_name or 'Гость'}\n"
        f"Телефон: {customer_phone or '—'}"
    )

    # Redirect to WhatsApp with pre-filled text
    wa_number = "".join(ch for ch in (v.whatsapp or v.phone or "") if ch.isdigit())
    if wa_number:
        # Текст уходит от клиента владельцу площадки, поэтому написан от первого
        # лица и сразу просит реквизиты: бронь закрепляется только после предоплаты.
        wa_text = (
            f"🏎️ Картинг — заявка на бронь №{appt.id}\n\n"
            f"Тип: {type_label}\n"
            f"Сессия: {st.duration_minutes} мин × {quantity} заезд(а) = {duration_total} мин\n"
            f"Дата: {date_fmt}\n"
            f"Время: {time_str}\n"
            f"{disc_line}"
            f"К оплате: {int(total_price)} сом\n\n"
            f"Клиент: {customer_name or 'Гость'}\n"
            f"Телефон: {customer_phone or '—'}\n\n"
            f"Подскажите, пожалуйста, куда внести предоплату — "
            f"бронь подтверждается после неё, и это время закрепляется за мной. "
            f"Жду реквизиты 🙏"
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
