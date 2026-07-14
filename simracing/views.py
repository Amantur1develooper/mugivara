import json
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import Machine, Session, SessionType, SimRacingVenue


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
            "price": str(st.price),
            "label": f"{st.duration_minutes} мин — {int(st.price)} сом",
        })

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
        "st_by_type_json": json.dumps(st_by_type),
    })


@require_POST
def book(request, slug):
    v = get_object_or_404(SimRacingVenue, slug=slug, is_active=True)

    machine_id = request.POST.get("machine_id", "")
    session_type_id = request.POST.get("session_type_id", "")
    customer_name = (request.POST.get("customer_name") or "").strip()
    customer_phone = (request.POST.get("customer_phone") or "").strip()

    machine = get_object_or_404(Machine, id=machine_id, venue=v, is_active=True)

    # check not already busy
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

    # Telegram notify
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
    """JSON endpoint: real-time status of all machines (for auto-refresh)."""
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
