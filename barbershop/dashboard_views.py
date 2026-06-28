from datetime import date, datetime, timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import (Appointment, Barber, BarberSchedule, BarberService,
                     Barbershop, BarbershopMembership, Service, ServiceCategory,
                     WEEKDAY_CHOICES)

LOGIN_URL = "dashboard:login"


def _user_shops(user):
    if user.is_staff or user.is_superuser:
        return Barbershop.objects.all()
    ids = BarbershopMembership.objects.filter(user=user).values_list("barbershop_id", flat=True)
    return Barbershop.objects.filter(id__in=ids)


def _check(user, shop):
    if user.is_staff or user.is_superuser:
        return True
    return BarbershopMembership.objects.filter(user=user, barbershop=shop).exists()


def _tg_send(shop, text):
    try:
        token = (getattr(settings, "TG_BOT_TOKEN", "") or
                 getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
        if not token or not shop.tg_chat_id:
            return
        import requests as req
        payload = {"chat_id": shop.tg_chat_id, "text": text,
                   "parse_mode": "HTML", "disable_web_page_preview": True}
        if shop.tg_thread_id:
            payload["message_thread_id"] = shop.tg_thread_id
        req.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=8)
    except Exception:
        pass


# ── HOME ─────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def bs_home(request):
    shops = _user_shops(request.user).prefetch_related("barbers")
    data = []
    for s in shops:
        new_count = Appointment.objects.filter(barbershop=s, status="new").count()
        today_count = Appointment.objects.filter(barbershop=s, appt_date=date.today()).exclude(status="cancelled").count()
        data.append({"shop": s, "new_count": new_count, "today_count": today_count})
    return render(request, "dashboard/barbershop/home.html", {"data": data})


# ── VENUE EDIT ────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def bs_venue_edit(request, shop_id):
    shop = get_object_or_404(Barbershop, id=shop_id)
    if not _check(request.user, shop):
        return redirect("dashboard:bs_home")
    if request.method == "POST":
        for f in ["name", "tagline", "description", "address", "phone",
                  "whatsapp", "working_hours", "map_url", "tg_chat_id"]:
            setattr(shop, f, request.POST.get(f, "").strip())
        tgt = request.POST.get("tg_thread_id", "").strip()
        shop.tg_thread_id = int(tgt) if tgt.isdigit() else None
        shop.is_active = request.POST.get("is_active") == "on"
        if "logo" in request.FILES:
            shop.logo = request.FILES["logo"]
        if "cover" in request.FILES:
            shop.cover = request.FILES["cover"]
        shop.save()
        messages.success(request, "Настройки сохранены")
        return redirect("dashboard:bs_venue_edit", shop_id=shop.id)
    return render(request, "dashboard/barbershop/venue_edit.html", {"shop": shop})


# ── SERVICES ──────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def bs_services(request, shop_id):
    shop = get_object_or_404(Barbershop, id=shop_id)
    if not _check(request.user, shop):
        return redirect("dashboard:bs_home")
    categories = (ServiceCategory.objects.filter(barbershop=shop)
                  .prefetch_related("services").order_by("sort_order", "id"))
    return render(request, "dashboard/barbershop/services.html",
                  {"shop": shop, "categories": categories})


@require_POST
@login_required(login_url=LOGIN_URL)
def bs_category_add(request, shop_id):
    shop = get_object_or_404(Barbershop, id=shop_id)
    if not _check(request.user, shop):
        return redirect("dashboard:bs_home")
    name = request.POST.get("name", "").strip()
    if name:
        ServiceCategory.objects.create(barbershop=shop, name=name)
        messages.success(request, f"Категория «{name}» добавлена")
    return redirect("dashboard:bs_services", shop_id=shop.id)


@require_POST
@login_required(login_url=LOGIN_URL)
def bs_category_delete(request, cat_id):
    cat = get_object_or_404(ServiceCategory, id=cat_id)
    if not _check(request.user, cat.barbershop):
        return redirect("dashboard:bs_home")
    shop_id = cat.barbershop_id
    cat.delete()
    messages.success(request, "Категория удалена")
    return redirect("dashboard:bs_services", shop_id=shop_id)


@require_POST
@login_required(login_url=LOGIN_URL)
def bs_service_add(request, cat_id):
    cat = get_object_or_404(ServiceCategory, id=cat_id)
    if not _check(request.user, cat.barbershop):
        return redirect("dashboard:bs_home")
    name = request.POST.get("name", "").strip()
    if not name:
        return redirect("dashboard:bs_services", shop_id=cat.barbershop_id)
    try:
        price = Decimal(request.POST.get("price") or "0")
    except Exception:
        price = Decimal("0")
    try:
        dur = int(request.POST.get("duration_min") or 30)
    except Exception:
        dur = 30
    Service.objects.create(
        barbershop=cat.barbershop, category=cat, name=name,
        description=request.POST.get("description", "").strip(),
        price=price, duration_min=dur,
    )
    messages.success(request, f"Услуга «{name}» добавлена")
    return redirect("dashboard:bs_services", shop_id=cat.barbershop_id)


@require_POST
@login_required(login_url=LOGIN_URL)
def bs_service_edit(request, svc_id):
    svc = get_object_or_404(Service, id=svc_id)
    if not _check(request.user, svc.barbershop):
        return JsonResponse({"ok": False}, status=403)
    svc.name = request.POST.get("name", svc.name).strip()
    svc.description = request.POST.get("description", "").strip()
    try:
        svc.price = Decimal(request.POST.get("price") or svc.price)
    except Exception:
        pass
    try:
        svc.duration_min = int(request.POST.get("duration_min") or svc.duration_min)
    except Exception:
        pass
    svc.is_active = request.POST.get("is_active") == "on"
    svc.save()
    messages.success(request, "Услуга обновлена")
    return redirect("dashboard:bs_services", shop_id=svc.barbershop_id)


@require_POST
@login_required(login_url=LOGIN_URL)
def bs_service_delete(request, svc_id):
    svc = get_object_or_404(Service, id=svc_id)
    if not _check(request.user, svc.barbershop):
        return redirect("dashboard:bs_home")
    shop_id = svc.barbershop_id
    svc.delete()
    messages.success(request, "Услуга удалена")
    return redirect("dashboard:bs_services", shop_id=shop_id)


@require_POST
@login_required(login_url=LOGIN_URL)
def bs_service_toggle(request, svc_id):
    svc = get_object_or_404(Service, id=svc_id)
    if not _check(request.user, svc.barbershop):
        return JsonResponse({"ok": False}, status=403)
    svc.is_active = not svc.is_active
    svc.save(update_fields=["is_active", "updated_at"])
    return JsonResponse({"ok": True, "is_active": svc.is_active})


# ── BARBERS ───────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def bs_barbers(request, shop_id):
    shop = get_object_or_404(Barbershop, id=shop_id)
    if not _check(request.user, shop):
        return redirect("dashboard:bs_home")
    barbers = shop.barbers.prefetch_related("barber_services__service", "schedules").order_by("sort_order", "id")
    all_services = Service.objects.filter(barbershop=shop, is_active=True).order_by("sort_order")
    return render(request, "dashboard/barbershop/barbers.html",
                  {"shop": shop, "barbers": barbers, "all_services": all_services})


@require_POST
@login_required(login_url=LOGIN_URL)
def bs_barber_add(request, shop_id):
    shop = get_object_or_404(Barbershop, id=shop_id)
    if not _check(request.user, shop):
        return redirect("dashboard:bs_home")
    name = request.POST.get("name", "").strip()
    if not name:
        return redirect("dashboard:bs_barbers", shop_id=shop.id)
    barber = Barber(
        barbershop=shop, name=name,
        experience=request.POST.get("experience", "").strip(),
        bio=request.POST.get("bio", "").strip(),
    )
    if "photo" in request.FILES:
        barber.photo = request.FILES["photo"]
    barber.save()

    # Set services
    svc_ids = request.POST.getlist("services")
    for sid in svc_ids:
        try:
            svc = Service.objects.get(id=sid, barbershop=shop)
            BarberService.objects.get_or_create(barber=barber, service=svc)
        except Service.DoesNotExist:
            pass

    # Create default schedule (all days, 09:00-20:00)
    for wd in range(7):
        BarberSchedule.objects.create(
            barber=barber, weekday=wd,
            start_time="09:00", end_time="20:00",
            is_working=(wd < 6),  # Mon-Sat working, Sun off
        )

    messages.success(request, f"Мастер «{name}» добавлен")
    return redirect("dashboard:bs_barbers", shop_id=shop.id)


@require_POST
@login_required(login_url=LOGIN_URL)
def bs_barber_edit(request, barber_id):
    barber = get_object_or_404(Barber, id=barber_id)
    if not _check(request.user, barber.barbershop):
        return redirect("dashboard:bs_home")
    barber.name = request.POST.get("name", barber.name).strip()
    barber.experience = request.POST.get("experience", "").strip()
    barber.bio = request.POST.get("bio", "").strip()
    if "photo" in request.FILES:
        barber.photo = request.FILES["photo"]
    barber.save()

    # Update services
    barber.barber_services.all().delete()
    for sid in request.POST.getlist("services"):
        try:
            svc = Service.objects.get(id=sid, barbershop=barber.barbershop)
            BarberService.objects.create(barber=barber, service=svc)
        except Service.DoesNotExist:
            pass

    messages.success(request, "Данные мастера обновлены")
    return redirect("dashboard:bs_barbers", shop_id=barber.barbershop_id)


@require_POST
@login_required(login_url=LOGIN_URL)
def bs_barber_toggle(request, barber_id):
    barber = get_object_or_404(Barber, id=barber_id)
    if not _check(request.user, barber.barbershop):
        return JsonResponse({"ok": False}, status=403)
    barber.is_active = not barber.is_active
    barber.save(update_fields=["is_active", "updated_at"])
    return JsonResponse({"ok": True, "is_active": barber.is_active})


@require_POST
@login_required(login_url=LOGIN_URL)
def bs_barber_delete(request, barber_id):
    barber = get_object_or_404(Barber, id=barber_id)
    if not _check(request.user, barber.barbershop):
        return redirect("dashboard:bs_home")
    shop_id = barber.barbershop_id
    barber.delete()
    messages.success(request, "Мастер удалён")
    return redirect("dashboard:bs_barbers", shop_id=shop_id)


@login_required(login_url=LOGIN_URL)
def bs_barber_schedule(request, barber_id):
    barber = get_object_or_404(Barber, id=barber_id)
    if not _check(request.user, barber.barbershop):
        return redirect("dashboard:bs_home")
    schedules = {s.weekday: s for s in barber.schedules.all()}
    if request.method == "POST":
        for wd in range(7):
            is_working = request.POST.get(f"working_{wd}") == "on"
            start = request.POST.get(f"start_{wd}", "09:00")
            end   = request.POST.get(f"end_{wd}", "20:00")
            try:
                sched = schedules.get(wd)
                if sched:
                    sched.is_working = is_working
                    sched.start_time = start
                    sched.end_time = end
                    sched.save()
                else:
                    BarberSchedule.objects.create(
                        barber=barber, weekday=wd,
                        start_time=start, end_time=end, is_working=is_working,
                    )
            except Exception:
                pass
        messages.success(request, "График сохранён")
        return redirect("dashboard:bs_barber_schedule", barber_id=barber.id)
    # Ensure all 7 days exist in context
    days = []
    for wd, wd_name in WEEKDAY_CHOICES:
        sched = schedules.get(wd)
        days.append({
            "wd": wd, "name": wd_name,
            "is_working": sched.is_working if sched else (wd < 6),
            "start": sched.start_time.strftime("%H:%M") if sched else "09:00",
            "end": sched.end_time.strftime("%H:%M") if sched else "20:00",
        })
    return render(request, "dashboard/barbershop/schedule.html",
                  {"shop": barber.barbershop, "barber": barber, "days": days})


# ── APPOINTMENTS ──────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def bs_appointments(request, shop_id):
    shop = get_object_or_404(Barbershop, id=shop_id)
    if not _check(request.user, shop):
        return redirect("dashboard:bs_home")

    qs = Appointment.objects.filter(barbershop=shop).select_related("barber", "service")
    status_f = request.GET.get("status", "")
    barber_f = request.GET.get("barber", "")
    # По умолчанию показываем только сегодня; "all" сбрасывает фильтр
    default_date = date.today().strftime("%Y-%m-%d")
    date_f = request.GET.get("date", default_date)
    if request.GET.get("all"):
        date_f = ""
    if status_f:
        qs = qs.filter(status=status_f)
    if barber_f:
        qs = qs.filter(barber_id=barber_f)
    if date_f:
        try:
            qs = qs.filter(appt_date=datetime.strptime(date_f, "%Y-%m-%d").date())
        except Exception:
            pass

    barbers = shop.barbers.filter(is_active=True).prefetch_related("barber_services__service").order_by("sort_order")
    today = date.today()
    tomorrow = today + timedelta(days=1)
    base_qs = Appointment.objects.filter(barbershop=shop)
    if barber_f:
        base_qs = base_qs.filter(barber_id=barber_f)
    from .models import APPOINTMENT_STATUS
    return render(request, "dashboard/barbershop/appointments.html", {
        "shop": shop, "appointments": qs,
        "barbers": barbers,
        "statuses": APPOINTMENT_STATUS,
        "status_f": status_f, "barber_f": barber_f, "date_f": date_f,
        "today_str":    today.strftime("%Y-%m-%d"),
        "tomorrow_str": tomorrow.strftime("%Y-%m-%d"),
        "count_today":    base_qs.filter(appt_date=today).exclude(status="cancelled").count(),
        "count_tomorrow": base_qs.filter(appt_date=tomorrow).exclude(status="cancelled").count(),
        "count_new":      base_qs.filter(status="new").count(),
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def bs_appointment_add(request, shop_id):
    shop = get_object_or_404(Barbershop, id=shop_id)
    if not _check(request.user, shop):
        return redirect("dashboard:bs_home")

    try:
        barber    = Barber.objects.get(id=request.POST.get("barber_id"), barbershop=shop)
        appt_date = datetime.strptime(request.POST.get("appt_date"), "%Y-%m-%d").date()
        appt_time = datetime.strptime(request.POST.get("appt_time"), "%H:%M").time()
    except Exception:
        messages.error(request, "Некорректные данные")
        return redirect("dashboard:bs_appointments", shop_id=shop.id)

    # Support multiple services: comma-separated or multiple values
    raw_ids = request.POST.get("service_ids", request.POST.get("service_id", ""))
    svc_ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]
    services = list(Service.objects.filter(id__in=svc_ids, barbershop=shop))
    if not services:
        messages.error(request, "Выберите хотя бы одну услугу")
        return redirect("dashboard:bs_appointments", shop_id=shop.id)

    total_price    = sum(s.price for s in services)
    total_duration = sum(s.duration_min for s in services)
    service_name   = " + ".join(s.name for s in services)
    primary        = services[0]

    name    = (request.POST.get("customer_name") or "").strip() or "Клиент"
    phone   = (request.POST.get("customer_phone") or "").strip()
    pay_m   = request.POST.get("payment_method", "")
    is_paid = request.POST.get("is_paid") == "on"
    status  = request.POST.get("status", "confirmed")
    notes   = request.POST.get("notes", "").strip()

    appt = Appointment.objects.create(
        barbershop=shop, barber=barber, service=primary,
        service_name=service_name, barber_name=barber.name,
        price_snapshot=total_price, duration_min=total_duration,
        customer_name=name, customer_phone=phone,
        appt_date=appt_date, appt_time=appt_time,
        status=status, source="offline",
        is_paid=is_paid, payment_method=pay_m, notes=notes,
    )

    weekday_ru = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    date_fmt = appt_date.strftime("%d.%m.%Y") + f" ({weekday_ru[appt_date.weekday()]})"
    svc_lines = "\n".join(f"  • {s.name} — {int(s.price)} сом" for s in services)
    _tg_send(shop,
        f"✂️ <b>Запись офлайн #{appt.id}</b>\n"
        f"📋 Услуги:\n{svc_lines}\n"
        f"💰 Итого: {int(total_price)} сом ({total_duration} мин)\n"
        f"👤 Мастер: {barber.name}\n"
        f"📅 {date_fmt} в {appt_time.strftime('%H:%M')}\n"
        f"👤 {name}{' ' + phone if phone else ''}"
    )
    messages.success(request, f"Запись #{appt.id} создана")
    return redirect("dashboard:bs_appointments", shop_id=shop.id)


@require_POST
@login_required(login_url=LOGIN_URL)
def bs_appointment_status(request, appt_id):
    appt = get_object_or_404(Appointment, id=appt_id)
    if not _check(request.user, appt.barbershop):
        return JsonResponse({"ok": False}, status=403)
    from .models import APPOINTMENT_STATUS
    new_status = request.POST.get("status", "")
    if new_status in dict(APPOINTMENT_STATUS):
        appt.status = new_status
        appt.save(update_fields=["status", "updated_at"])
    return JsonResponse({"ok": True, "status": appt.status})


@require_POST
@login_required(login_url=LOGIN_URL)
def bs_appointment_payment(request, appt_id):
    appt = get_object_or_404(Appointment, id=appt_id)
    if not _check(request.user, appt.barbershop):
        return JsonResponse({"ok": False}, status=403)
    appt.is_paid = not appt.is_paid
    if appt.is_paid and not appt.payment_method:
        appt.payment_method = request.POST.get("payment_method", "cash")
    appt.save(update_fields=["is_paid", "payment_method", "updated_at"])
    return JsonResponse({"ok": True, "is_paid": appt.is_paid})


@require_POST
@login_required(login_url=LOGIN_URL)
def bs_appointment_delete(request, appt_id):
    appt = get_object_or_404(Appointment, id=appt_id)
    if not _check(request.user, appt.barbershop):
        return redirect("dashboard:bs_home")
    shop_id = appt.barbershop_id
    appt.delete()
    messages.success(request, "Запись удалена")
    return redirect("dashboard:bs_appointments", shop_id=shop_id)


# ── REPORT ────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def bs_report(request, shop_id):
    shop = get_object_or_404(Barbershop, id=shop_id)
    if not _check(request.user, shop):
        return redirect("dashboard:bs_home")

    period = request.GET.get("period", "month")
    today = date.today()
    if period == "today":
        date_from = today
        date_to   = today
    elif period == "week":
        date_from = today - timedelta(days=today.weekday())
        date_to   = today
    else:  # month
        date_from = today.replace(day=1)
        date_to   = today

    qs = Appointment.objects.filter(
        barbershop=shop, appt_date__gte=date_from, appt_date__lte=date_to,
        status__in=["done", "confirmed"],
    )

    total_revenue = qs.aggregate(t=Sum("price_snapshot"))["t"] or 0
    total_count   = qs.count()
    paid_revenue  = qs.filter(is_paid=True).aggregate(t=Sum("price_snapshot"))["t"] or 0
    online_rev    = qs.filter(source="online").aggregate(t=Sum("price_snapshot"))["t"] or 0
    offline_rev   = qs.filter(source="offline").aggregate(t=Sum("price_snapshot"))["t"] or 0

    barber_stats = (qs.values("barber_name")
                    .annotate(cnt=Count("id"), rev=Sum("price_snapshot"))
                    .order_by("-rev"))
    service_stats = (qs.values("service_name")
                     .annotate(cnt=Count("id"), rev=Sum("price_snapshot"))
                     .order_by("-cnt"))

    # Daily shift: today's appointments grouped by barber
    shift_qs = (Appointment.objects
                .filter(barbershop=shop, appt_date=today)
                .exclude(status="cancelled")
                .select_related("barber")
                .order_by("barber__sort_order", "appt_time"))
    shift_by_barber = {}
    for appt in shift_qs:
        bname = appt.barber_name or "—"
        if bname not in shift_by_barber:
            shift_by_barber[bname] = {"appointments": [], "total": 0, "paid": 0, "count": 0}
        shift_by_barber[bname]["appointments"].append(appt)
        shift_by_barber[bname]["total"] += int(appt.price_snapshot)
        shift_by_barber[bname]["count"] += 1
        if appt.is_paid:
            shift_by_barber[bname]["paid"] += int(appt.price_snapshot)
    shift_total = sum(v["total"] for v in shift_by_barber.values())
    shift_paid  = sum(v["paid"]  for v in shift_by_barber.values())
    shift_count = sum(v["count"] for v in shift_by_barber.values())

    return render(request, "dashboard/barbershop/report.html", {
        "shop": shop, "period": period,
        "date_from": date_from, "date_to": date_to,
        "total_revenue": total_revenue, "total_count": total_count,
        "paid_revenue": paid_revenue,
        "online_rev": online_rev, "offline_rev": offline_rev,
        "barber_stats": barber_stats, "service_stats": service_stats,
        "shift_by_barber": shift_by_barber,
        "shift_total": shift_total, "shift_paid": shift_paid, "shift_count": shift_count,
        "today": today,
    })
