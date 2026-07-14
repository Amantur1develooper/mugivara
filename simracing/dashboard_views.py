from datetime import date, timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Machine, Session, SessionType, SimRacingMembership, SimRacingVenue

LOGIN_URL = "dashboard:login"


def _user_venues(user):
    if user.is_staff or user.is_superuser:
        return SimRacingVenue.objects.all()
    ids = SimRacingMembership.objects.filter(user=user).values_list("venue_id", flat=True)
    return SimRacingVenue.objects.filter(id__in=ids)


def _check(user, venue):
    if user.is_staff or user.is_superuser:
        return True
    return SimRacingMembership.objects.filter(user=user, venue=venue).exists()


def _tg_send(venue, text):
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


# ─────────────────────────────────────────────────────────────────────────────
# HOME
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def sr_home(request):
    venues = _user_venues(request.user)
    today = date.today()
    data = []
    for v in venues:
        active_count = Session.objects.filter(venue=v, status=Session.Status.ACTIVE).count()
        today_count  = Session.objects.filter(venue=v, started_at__date=today).exclude(
            status=Session.Status.CANCELED).count()
        today_revenue = Session.objects.filter(venue=v, started_at__date=today,
            status=Session.Status.DONE).aggregate(s=Sum("price"))["s"] or 0
        data.append({
            "venue": v,
            "active_count":  active_count,
            "today_count":   today_count,
            "today_revenue": today_revenue,
        })
    return render(request, "dashboard/simracing/home.html", {"data": data})


# ─────────────────────────────────────────────────────────────────────────────
# VENUE EDIT
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def sr_venue_edit(request, venue_id):
    v = get_object_or_404(SimRacingVenue, id=venue_id)
    if not _check(request.user, v):
        return redirect("dashboard:sr_home")
    if request.method == "POST":
        for f in ["name", "tagline", "description", "address", "phone",
                  "whatsapp", "working_hours", "map_url", "tg_chat_id"]:
            setattr(v, f, request.POST.get(f, "").strip())
        tgt = request.POST.get("tg_thread_id", "").strip()
        v.tg_thread_id = int(tgt) if tgt.isdigit() else None
        if request.FILES.get("logo"):
            v.logo = request.FILES["logo"]
        if request.FILES.get("cover"):
            v.cover = request.FILES["cover"]
        v.save()
        return redirect("dashboard:sr_venue_edit", venue_id=v.id)
    return render(request, "dashboard/simracing/venue_edit.html", {"venue": v})


# ─────────────────────────────────────────────────────────────────────────────
# MACHINES
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def sr_machines(request, venue_id):
    v = get_object_or_404(SimRacingVenue, id=venue_id)
    if not _check(request.user, v):
        return redirect("dashboard:sr_home")
    machines = v.machines.all()
    active_sessions = {
        s.machine_id: s
        for s in Session.objects.filter(venue=v, status=Session.Status.ACTIVE).select_related("machine")
    }
    machines_data = [(m, active_sessions.get(m.id)) for m in machines]
    return render(request, "dashboard/simracing/machines.html", {
        "venue": v,
        "machines_data": machines_data,
        "machine_types": Machine.Type.choices,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def sr_machine_add(request, venue_id):
    v = get_object_or_404(SimRacingVenue, id=venue_id)
    if not _check(request.user, v):
        return redirect("dashboard:sr_home")
    name = request.POST.get("name", "").strip()
    mtype = request.POST.get("type", Machine.Type.KART_STANDARD)
    if not name:
        return redirect("dashboard:sr_machines", venue_id=v.id)
    m = Machine.objects.create(venue=v, name=name, type=mtype)
    if request.FILES.get("photo"):
        m.photo = request.FILES["photo"]
        m.save()
    return redirect("dashboard:sr_machines", venue_id=v.id)


@require_POST
@login_required(login_url=LOGIN_URL)
def sr_machine_toggle(request, machine_id):
    m = get_object_or_404(Machine, id=machine_id)
    if not _check(request.user, m.venue):
        return JsonResponse({"ok": False}, status=403)
    m.is_active = not m.is_active
    m.save(update_fields=["is_active"])
    return JsonResponse({"ok": True, "is_active": m.is_active})


@require_POST
@login_required(login_url=LOGIN_URL)
def sr_machine_delete(request, machine_id):
    m = get_object_or_404(Machine, id=machine_id)
    if not _check(request.user, m.venue):
        return JsonResponse({"ok": False}, status=403)
    if Session.objects.filter(machine=m, status=Session.Status.ACTIVE).exists():
        return JsonResponse({"ok": False, "error": "Машина занята — сначала завершите сессию"})
    venue_id = m.venue_id
    m.delete()
    return JsonResponse({"ok": True})


# ─────────────────────────────────────────────────────────────────────────────
# SESSION TYPES (PRICE LIST)
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def sr_session_types(request, venue_id):
    v = get_object_or_404(SimRacingVenue, id=venue_id)
    if not _check(request.user, v):
        return redirect("dashboard:sr_home")
    types = v.session_types.all()
    return render(request, "dashboard/simracing/session_types.html", {
        "venue": v,
        "types": types,
        "machine_types": Machine.Type.choices,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def sr_session_type_add(request, venue_id):
    v = get_object_or_404(SimRacingVenue, id=venue_id)
    if not _check(request.user, v):
        return redirect("dashboard:sr_home")
    mtype    = request.POST.get("machine_type", "")
    dur_str  = request.POST.get("duration_minutes", "")
    price_str = request.POST.get("price", "")
    if mtype and dur_str.isdigit() and price_str:
        SessionType.objects.get_or_create(
            venue=v, machine_type=mtype, duration_minutes=int(dur_str),
            defaults={"price": Decimal(price_str)},
        )
    return redirect("dashboard:sr_session_types", venue_id=v.id)


@require_POST
@login_required(login_url=LOGIN_URL)
def sr_session_type_delete(request, st_id):
    st = get_object_or_404(SessionType, id=st_id)
    if not _check(request.user, st.venue):
        return JsonResponse({"ok": False}, status=403)
    st.delete()
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url=LOGIN_URL)
def sr_session_type_toggle(request, st_id):
    st = get_object_or_404(SessionType, id=st_id)
    if not _check(request.user, st.venue):
        return JsonResponse({"ok": False}, status=403)
    st.is_active = not st.is_active
    st.save(update_fields=["is_active"])
    return JsonResponse({"ok": True, "is_active": st.is_active})


# ─────────────────────────────────────────────────────────────────────────────
# SESSIONS (LIVE + HISTORY)
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def sr_sessions(request, venue_id):
    v = get_object_or_404(SimRacingVenue, id=venue_id)
    if not _check(request.user, v):
        return redirect("dashboard:sr_home")

    machines = v.machines.filter(is_active=True).order_by("sort_order", "id")
    active_sessions = {
        s.machine_id: s
        for s in Session.objects.filter(venue=v, status=Session.Status.ACTIVE)
                                 .select_related("machine", "session_type")
    }
    live = [(m, active_sessions.get(m.id)) for m in machines]

    # stopped machines with no active session
    stopped = v.machines.filter(is_active=False)

    history = (
        Session.objects
        .filter(venue=v)
        .exclude(status=Session.Status.ACTIVE)
        .select_related("machine", "session_type")
        .order_by("-started_at")[:60]
    )

    # session types for starting from dashboard
    session_types = (
        SessionType.objects.filter(venue=v, is_active=True)
        .order_by("machine_type", "duration_minutes")
    )

    import json
    from django.utils import timezone as tz
    now_ts = int(tz.now().timestamp())

    live_json = {}
    for m, s in live:
        if s:
            live_json[str(m.id)] = {
                "ends_ts": int(s.ends_at.timestamp()),
                "is_overtime": s.is_overtime,
                "session_id": s.id,
                "remaining": s.remaining_seconds,
            }

    return render(request, "dashboard/simracing/sessions.html", {
        "venue": v,
        "live": live,
        "stopped": stopped,
        "history": history,
        "session_types": session_types,
        "live_json": json.dumps(live_json),
        "now_ts": now_ts,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def sr_session_start(request, venue_id):
    """Start a session from dashboard (offline/cashier)."""
    v = get_object_or_404(SimRacingVenue, id=venue_id)
    if not _check(request.user, v):
        return JsonResponse({"ok": False}, status=403)

    machine_id = request.POST.get("machine_id", "")
    st_id      = request.POST.get("session_type_id", "")
    customer_name  = (request.POST.get("customer_name") or "").strip()
    customer_phone = (request.POST.get("customer_phone") or "").strip()

    machine = get_object_or_404(Machine, id=machine_id, venue=v, is_active=True)
    st      = get_object_or_404(SessionType, id=st_id, venue=v, is_active=True)

    if Session.objects.filter(machine=machine, status=Session.Status.ACTIVE).exists():
        return JsonResponse({"ok": False, "error": "Машина уже занята"})

    session = Session.objects.create(
        venue=v, machine=machine, session_type=st,
        customer_name=customer_name, customer_phone=customer_phone,
        duration_minutes=st.duration_minutes, price=st.price,
        source="offline",
    )

    _tg_send(
        v,
        f"🏁 <b>Сессия запущена</b> #{session.id} (касса)\n"
        f"Машина: {machine.name}\n"
        f"Длительность: {st.duration_minutes} мин — {int(st.price)} сом"
    )

    from django.utils import timezone as tz
    return JsonResponse({
        "ok": True,
        "session_id": session.id,
        "ends_ts": int(session.ends_at.timestamp()),
        "ends_at": tz.localtime(session.ends_at).strftime("%H:%M"),
        "remaining": session.remaining_seconds,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def sr_session_close(request, session_id):
    s = get_object_or_404(Session, id=session_id)
    if not _check(request.user, s.venue):
        return JsonResponse({"ok": False}, status=403)
    if s.status != Session.Status.ACTIVE:
        return JsonResponse({"ok": False, "error": "Сессия не активна"})
    s.status   = Session.Status.DONE
    s.ended_at = timezone.now()
    s.save(update_fields=["status", "ended_at"])
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url=LOGIN_URL)
def sr_session_cancel(request, session_id):
    s = get_object_or_404(Session, id=session_id)
    if not _check(request.user, s.venue):
        return JsonResponse({"ok": False}, status=403)
    s.status   = Session.Status.CANCELED
    s.ended_at = timezone.now()
    s.save(update_fields=["status", "ended_at"])
    return JsonResponse({"ok": True})


# ─────────────────────────────────────────────────────────────────────────────
# REPORT
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def sr_report(request, venue_id):
    v = get_object_or_404(SimRacingVenue, id=venue_id)
    if not _check(request.user, v):
        return redirect("dashboard:sr_home")

    today = date.today()
    period = request.GET.get("period", "today")

    if period == "week":
        date_from = today - timedelta(days=6)
        label = "Неделя"
    elif period == "month":
        date_from = today.replace(day=1)
        label = "Месяц"
    else:
        date_from = today
        label = "Сегодня"

    qs = Session.objects.filter(
        venue=v,
        started_at__date__gte=date_from,
        started_at__date__lte=today,
        status=Session.Status.DONE,
    )

    total_revenue = qs.aggregate(s=Sum("price"))["s"] or 0
    total_sessions = qs.count()

    by_type = {}
    for mtype, mname in Machine.Type.choices:
        type_qs = qs.filter(machine_type_snapshot=mtype)
        by_type[mtype] = {
            "name": mname,
            "count": type_qs.count(),
            "revenue": type_qs.aggregate(s=Sum("price"))["s"] or 0,
        }

    by_machine = []
    for m in v.machines.all():
        mqs = qs.filter(machine=m)
        by_machine.append({
            "machine": m,
            "count": mqs.count(),
            "revenue": mqs.aggregate(s=Sum("price"))["s"] or 0,
        })

    return render(request, "dashboard/simracing/report.html", {
        "venue": v,
        "period": period,
        "label": label,
        "date_from": date_from,
        "today": today,
        "total_revenue": total_revenue,
        "total_sessions": total_sessions,
        "by_type": by_type,
        "by_machine": by_machine,
    })
