# -*- coding: utf-8 -*-
"""Кабинет фитнес-клуба.

Страницы разведены по ролям: администратору всё, кассиру продажи и
проход, тренеру — только его записи и его клиенты. Проверка прав висит
декоратором @require, чтобы её нельзя было забыть.
"""
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from integrations import tgbot

from . import services, tg
from .access import (ADMIN, CASHIER, TRAINER, can_see_money, can_see_profit,
                     my_clubs, my_trainer, require, staff_of)
from .models import (SECTION_PRESETS, ClassBooking, ClubStaff, Expense,
                     FitnessClub, GroupClass, Lead, LeadNote, Member, Membership,
                     MembershipPlan, Payment, Section, Trainer, TrainerBooking,
                     TrainerSchedule, Visit)

LOGIN_URL = "dashboard:login"


def _money(raw, default="0"):
    try:
        return Decimal(str(raw or default).replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return Decimal(default)


def _date(raw, default=None):
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return default or timezone.localdate()


def _ctx(club, staff, **extra):
    """Общий контекст: в шаблонах нужны права и клуб."""
    base = {
        "club": club,
        "staff": staff,
        "role": staff.role,
        "is_admin": staff.role == ADMIN,
        "is_cashier": staff.role == CASHIER,
        "is_trainer": staff.role == TRAINER,
        "can_money": can_see_money(staff),
        "can_profit": can_see_profit(staff),
    }
    base.update(extra)
    return base


# ── Список клубов и сводка ──────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def clubs(request):
    items = my_clubs(request.user)
    if items.count() == 1:
        return redirect("fitness_dash:home", club_id=items.first().id)
    return render(request, "fitness/dash/clubs.html", {"clubs": items})


@login_required(login_url=LOGIN_URL)
@require()
def home(request, club, staff):
    today = timezone.localdate()
    month_start = today.replace(day=1)

    visits_today = Visit.objects.filter(club=club, visit_time__date=today, success=True)
    trainer = my_trainer(request.user, club)

    data = _ctx(club, staff,
                today=today,
                visits_today=visits_today.count(),
                members_total=Member.objects.filter(club=club, is_active=True).count(),
                new_leads=Lead.objects.filter(club=club, status=Lead.Status.NEW).count(),
                my_trainer=trainer)

    # Абонементы, которые скоро кончатся — повод позвонить
    soon = (Membership.objects
            .filter(member__club=club, is_active=True, end_date__isnull=False,
                    end_date__gte=today, end_date__lte=today + timedelta(days=7))
            .select_related("member", "plan").order_by("end_date")[:10])
    data["expiring"] = soon

    if can_see_money(staff):
        income_today = Payment.objects.filter(club=club, created_at__date=today) \
            .aggregate(s=Sum("amount"))["s"] or 0
        income_month = Payment.objects.filter(club=club, created_at__date__gte=month_start) \
            .aggregate(s=Sum("amount"))["s"] or 0
        data.update(income_today=income_today, income_month=income_month)

    if can_see_profit(staff):
        exp_month = Expense.objects.filter(club=club, spent_on__gte=month_start) \
            .aggregate(s=Sum("amount"))["s"] or 0
        data.update(expenses_month=exp_month,
                    profit_month=(data.get("income_month") or 0) - exp_month)

    if trainer:
        data["my_today"] = (TrainerBooking.objects
                            .filter(trainer=trainer, date=today)
                            .exclude(status=TrainerBooking.Status.CANCELLED)
                            .select_related("member").order_by("time_from"))

    if can_see_money(staff):
        data.update(_reminders(club, today))
    return render(request, "fitness/dash/home.html", data)


def _reminders(club, today):
    """Три повода позвонить: день рождения, пропал, просрочен звонок.

    Это то, из-за чего клиенты уходят молча. Клуб узнаёт об уходе через
    месяц, когда абонемент давно кончился, и возвращать уже поздно.
    """
    week = [(today + timedelta(days=i)) for i in range(7)]
    md = {(d.month, d.day): d for d in week}
    birthdays = []
    for m in (Member.objects.filter(club=club, is_active=True, birth_date__isnull=False)
              .only("id", "full_name", "phone", "birth_date")):
        when = md.get((m.birth_date.month, m.birth_date.day))
        if when:
            birthdays.append({"member": m, "when": when})
    birthdays.sort(key=lambda x: x["when"])

    # Пропал: есть действующий абонемент, но две недели не приходил
    gone_edge = timezone.now() - timedelta(days=14)
    lost = []
    for ms in (Membership.objects
               .filter(member__club=club, is_active=True, start_date__isnull=False,
                       end_date__gte=today)
               .select_related("member")
               .order_by("end_date")[:200]):
        last = ms.member.visits.filter(success=True).order_by("-visit_time").first()
        if last and last.visit_time < gone_edge:
            lost.append({"member": ms.member, "last": last.visit_time,
                         "days": (timezone.now() - last.visit_time).days})
        elif not last and ms.created_at < gone_edge:
            lost.append({"member": ms.member, "last": None, "days": None})
    lost = lost[:10]

    overdue = (Lead.objects.filter(club=club, next_contact_at__lt=timezone.now())
               .exclude(status__in=[Lead.Status.SOLD, Lead.Status.LOST])
               .order_by("next_contact_at")[:10])

    return {"birthdays": birthdays[:10], "lost_members": lost, "overdue_leads": overdue}


# ── Касса: проход в зал ─────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
def checkin(request, club, staff):
    q = (request.GET.get("q") or "").strip()
    found = []
    if q:
        found = list(Member.objects
                     .filter(club=club, is_active=True)
                     .filter(Q(full_name__icontains=q) | Q(phone__icontains=q)
                             | Q(card_id__iexact=q))
                     .prefetch_related("memberships__plan")[:20])

    recent = (Visit.objects.filter(club=club)
              .select_related("member", "membership__plan", "trainer")
              .order_by("-visit_time")[:15])
    return render(request, "fitness/dash/checkin.html",
                  _ctx(club, staff, q=q, found=found, recent=recent,
                       trainers=club.trainers.filter(is_active=True)))


@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
@require_POST
def checkin_pass(request, club, staff, member_id):
    member = get_object_or_404(Member, id=member_id, club=club)
    trainer = None
    raw = request.POST.get("trainer_id")
    if raw and raw.isdigit():
        trainer = Trainer.objects.filter(id=int(raw), club=club).first()

    ok, msg, visit = services.check_in(club, member, trainer=trainer,
                                       actor=request.user)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        ms = member.active_membership()
        return JsonResponse({
            "ok": ok, "message": msg,
            "name": member.full_name,
            "left": (ms.remaining_visits if ms and ms.plan.visits_number else None),
            "until": (ms.end_date.strftime("%d.%m.%Y") if ms and ms.end_date else ""),
        })
    (messages.success if ok else messages.error)(request, f"{member.full_name}: {msg}")
    return redirect("fitness_dash:checkin", club_id=club.id)


# ── Клиенты ─────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
@require()
def members(request, club, staff):
    q = (request.GET.get("q") or "").strip()
    rows = Member.objects.filter(club=club).prefetch_related("memberships__plan")
    if q:
        rows = rows.filter(Q(full_name__icontains=q) | Q(phone__icontains=q)
                           | Q(card_id__icontains=q))

    # Тренер видит только своих: тех, у кого он указан в абонементе или
    # к кому ходит на записи. Остальных ему знать незачем.
    trainer = my_trainer(request.user, club)
    if staff.role == TRAINER and trainer:
        rows = rows.filter(Q(memberships__trainer=trainer) |
                           Q(bookings__trainer=trainer)).distinct()

    only = (request.GET.get("filter") or "").strip()
    today = timezone.localdate()
    if only == "debt":
        rows = rows.filter(memberships__debt_amount__gt=0).distinct()
    elif only == "expiring":
        rows = rows.filter(memberships__is_active=True,
                           memberships__end_date__gte=today,
                           memberships__end_date__lte=today + timedelta(days=7)).distinct()
    elif only == "no_membership":
        rows = rows.exclude(memberships__is_active=True)

    return render(request, "fitness/dash/members.html",
                  _ctx(club, staff, q=q, only=only, members=rows.order_by("full_name")[:300]))


@login_required(login_url=LOGIN_URL)
@require()
def member_detail(request, club, staff, member_id):
    member = get_object_or_404(Member.objects.prefetch_related(
        "memberships__plan", "memberships__trainer"), id=member_id, club=club)
    data = _ctx(club, staff,
                member=member,
                memberships=member.memberships.select_related("plan", "trainer"),
                visits=member.visits.select_related("membership__plan", "trainer")[:30],
                plans=club.plans.filter(is_active=True),
                trainers=club.trainers.filter(is_active=True),
                active=member.active_membership())
    if can_see_money(staff):
        data["payments"] = member.payments.order_by("-id")[:30]
    return render(request, "fitness/dash/member_detail.html", data)


@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
@require_POST
def member_save(request, club, staff, member_id=0):
    """Создание и правка клиента одной вьюхой: поля те же."""
    if member_id:
        member = get_object_or_404(Member, id=member_id, club=club)
    else:
        member = Member(club=club, created_by=request.user)

    member.full_name = (request.POST.get("full_name") or "").strip()[:200]
    member.phone = (request.POST.get("phone") or "").strip()[:30]
    member.card_id = (request.POST.get("card_id") or "").strip()[:50]
    member.notes = (request.POST.get("notes") or "").strip()
    member.gender = (request.POST.get("gender") or "")[:1]
    bd = request.POST.get("birth_date")
    member.birth_date = _date(bd, None) if bd else None
    if request.FILES.get("photo"):
        member.photo = request.FILES["photo"]
    if not member.full_name:
        messages.error(request, "Без имени клиента не сохранить")
        return redirect("fitness_dash:members", club_id=club.id)
    member.save()
    messages.success(request, f"{member.full_name} сохранён")
    return redirect("fitness_dash:member_detail", club_id=club.id, member_id=member.id)


@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
@require_POST
def membership_sell(request, club, staff, member_id):
    member = get_object_or_404(Member, id=member_id, club=club)
    plan = get_object_or_404(MembershipPlan, id=request.POST.get("plan_id"), club=club)
    trainer = None
    raw = request.POST.get("trainer_id")
    if raw and raw.isdigit():
        trainer = Trainer.objects.filter(id=int(raw), club=club).first()

    ms = services.sell_membership(
        club, member, plan,
        price=_money(request.POST.get("price"), str(plan.price)),
        discount=_money(request.POST.get("discount"), "0"),
        paid=_money(request.POST.get("paid"), str(plan.price)),
        trainer=trainer,
        start_today=request.POST.get("start_today") == "on",
        method=request.POST.get("method") or "cash",
        actor=request.user,
    )
    note = "начнётся с первого посещения" if not ms.activated else f"с {ms.start_date:%d.%m.%Y}"
    messages.success(request, f"Абонемент продан, {note}")
    return redirect("fitness_dash:member_detail", club_id=club.id, member_id=member.id)


@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
@require_POST
def membership_action(request, club, staff, membership_id):
    ms = get_object_or_404(Membership.objects.select_related("member", "plan"),
                           id=membership_id, member__club=club)
    action = request.POST.get("action")

    if action == "pay":
        services.pay_debt(club, ms, _money(request.POST.get("amount"), "0"),
                          method=request.POST.get("method") or "cash", actor=request.user)
        messages.success(request, "Долг принят")
    elif action == "freeze":
        services.freeze(ms, request.POST.get("days") or 7, actor=request.user)
        messages.success(request, "Абонемент заморожен")
    elif action == "unfreeze":
        services.unfreeze(ms, actor=request.user)
        messages.success(request, "Заморозка снята")
    elif action == "activate":
        if ms.activate():
            messages.success(request, f"Активирован до {ms.end_date:%d.%m.%Y}")
        else:
            messages.info(request, "Уже активирован")
    elif action == "close" and staff.role == ADMIN:
        ms.is_active = False
        ms.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "Абонемент закрыт")
    return redirect("fitness_dash:member_detail", club_id=club.id, member_id=ms.member_id)


# ── Шахматка записей ────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
@require()
def board(request, club, staff):
    """Кто к какому тренеру записан — по часам, как на доске у ресепшена."""
    day = _date(request.GET.get("date"))
    trainer = my_trainer(request.user, club)

    trainers = club.trainers.filter(is_active=True).order_by("sort_order", "id")
    if staff.role == TRAINER and trainer:
        trainers = trainers.filter(id=trainer.id)

    rows = (TrainerBooking.objects
            .filter(club=club, date=day)
            .exclude(status=TrainerBooking.Status.CANCELLED)
            .select_related("trainer", "member", "lead"))

    # Сетка часов: от самого раннего начала до самого позднего конца, но не
    # уже 8:00–22:00 — иначе пустая таблица выглядит сломанной.
    start_hour, end_hour = 8, 22
    for b in rows:
        start_hour = min(start_hour, b.time_from.hour)
        end_hour = max(end_hour, (b.time_to.hour + 1) if b.time_to.minute else b.time_to.hour)
    hours = list(range(start_hour, max(end_hour, start_hour + 1)))

    cells = {}
    for b in rows:
        cells.setdefault(b.trainer_id, {}).setdefault(b.time_from.hour, []).append(b)

    return render(request, "fitness/dash/board.html",
                  _ctx(club, staff, day=day, hours=hours, trainers=list(trainers),
                       cells=cells, total=rows.count(),
                       prev_day=day - timedelta(days=1), next_day=day + timedelta(days=1),
                       today=timezone.localdate()))


@login_required(login_url=LOGIN_URL)
@require()
@require_POST
def booking_save(request, club, staff):
    """Запись к тренеру из кабинета."""
    trainer = get_object_or_404(Trainer, id=request.POST.get("trainer_id"), club=club)
    mine = my_trainer(request.user, club)
    if staff.role == TRAINER and (not mine or mine.id != trainer.id):
        messages.error(request, "Записывать можно только к себе")
        return redirect("fitness_dash:board", club_id=club.id)

    member = None
    raw = request.POST.get("member_id")
    if raw and raw.isdigit():
        member = Member.objects.filter(id=int(raw), club=club).first()

    hhmm = (request.POST.get("time_from") or "").strip()
    try:
        t = datetime.strptime(hhmm, "%H:%M").time()
    except ValueError:
        messages.error(request, "Время в формате 14:30")
        return redirect("fitness_dash:board", club_id=club.id)

    booking = TrainerBooking.objects.create(
        club=club, trainer=trainer, member=member,
        client_name=(request.POST.get("client_name") or "").strip()[:150],
        phone=(request.POST.get("phone") or "").strip()[:30],
        date=_date(request.POST.get("date")),
        time_from=t,
        duration_min=int(request.POST.get("duration_min") or 60),
        comment=(request.POST.get("comment") or "").strip()[:300],
        price=_money(request.POST.get("price"), str(trainer.price_per_session)),
        status=TrainerBooking.Status.CONFIRMED,
        created_by=request.user,
    )
    tgbot.in_background(tg.send_booking, booking)
    messages.success(request, f"Записан: {booking.who} на {booking.date:%d.%m} {t:%H:%M}")
    return redirect(f"/ru/cabinet/fitness/{club.id}/board/?date={booking.date:%Y-%m-%d}")


@login_required(login_url=LOGIN_URL)
@require()
@require_POST
def booking_status(request, club, staff, booking_id):
    booking = get_object_or_404(TrainerBooking.objects.select_related("trainer", "club"),
                                id=booking_id, club=club)
    mine = my_trainer(request.user, club)
    if staff.role == TRAINER and (not mine or mine.id != booking.trainer_id):
        return JsonResponse({"ok": False}, status=403)

    action = request.POST.get("action") or ""
    name = (request.user.get_full_name() or request.user.username)
    toast = tg.apply_booking_action(booking, action, actor=name)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": bool(toast), "status": booking.status,
                             "label": booking.get_status_display()})
    messages.success(request, toast or "Не понял действие")
    return redirect(f"/ru/cabinet/fitness/{club.id}/board/?date={booking.date:%Y-%m-%d}")


# ── Заявки (CRM) ────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
def leads(request, club, staff):
    status = (request.GET.get("status") or "").strip()
    rows = Lead.objects.filter(club=club).select_related("section", "trainer", "assigned_to")
    if status:
        rows = rows.filter(status=status)

    counts = {r["status"]: r["n"] for r in
              Lead.objects.filter(club=club).values("status").annotate(n=Count("id"))}
    # Просроченные звонки — то, из-за чего заявки и теряются
    overdue = Lead.objects.filter(club=club, next_contact_at__lt=timezone.now()) \
        .exclude(status__in=[Lead.Status.SOLD, Lead.Status.LOST]).count()

    return render(request, "fitness/dash/leads.html",
                  _ctx(club, staff, leads=rows.order_by("-id")[:200], status=status,
                       counts=counts, overdue=overdue,
                       statuses=Lead.Status.choices))


@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
def lead_detail(request, club, staff, lead_id):
    lead = get_object_or_404(Lead.objects.select_related("section", "trainer", "member"),
                             id=lead_id, club=club)
    return render(request, "fitness/dash/lead_detail.html",
                  _ctx(club, staff, lead=lead, notes=lead.notes.select_related("author"),
                       statuses=Lead.Status.choices,
                       plans=club.plans.filter(is_active=True),
                       trainers=club.trainers.filter(is_active=True)))


@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
@require_POST
def lead_save(request, club, staff, lead_id=0):
    if lead_id:
        lead = get_object_or_404(Lead, id=lead_id, club=club)
    else:
        lead = Lead(club=club, source=Lead.Source.PHONE)

    lead.name = (request.POST.get("name") or "").strip()[:150]
    lead.phone = (request.POST.get("phone") or "").strip()[:30]
    if not lead.phone:
        messages.error(request, "Телефон обязателен — иначе перезвонить некому")
        return redirect("fitness_dash:leads", club_id=club.id)

    lead.comment = (request.POST.get("comment") or "").strip()
    if request.POST.get("status") in dict(Lead.Status.choices):
        lead.status = request.POST["status"]
    if request.POST.get("source") in dict(Lead.Source.choices):
        lead.source = request.POST["source"]
    sec = request.POST.get("section_id")
    lead.section = Section.objects.filter(id=sec, club=club).first() if (sec or "").isdigit() else None
    tr = request.POST.get("trainer_id")
    lead.trainer = Trainer.objects.filter(id=tr, club=club).first() if (tr or "").isdigit() else None

    when = (request.POST.get("next_contact") or "").strip()
    if when:
        try:
            naive = datetime.strptime(when, "%Y-%m-%dT%H:%M")
            lead.next_contact_at = timezone.make_aware(naive)
        except ValueError:
            lead.next_contact_at = None
    elif request.POST.get("clear_next") == "on":
        lead.next_contact_at = None

    if not lead.assigned_to_id:
        lead.assigned_to = request.user
    is_new = lead.pk is None
    lead.save()

    text = (request.POST.get("note") or "").strip()
    if text:
        LeadNote.objects.create(lead=lead, text=text, author=request.user)

    if is_new:
        tgbot.in_background(tg.send_lead, lead)
    else:
        name = request.user.get_full_name() or request.user.username
        stamp = timezone.localtime().strftime("%d.%m %H:%M")
        tgbot.in_background(tg.refresh_lead, lead,
                            f"{lead.get_status_display()} — {name}, {stamp}")
    messages.success(request, "Заявка сохранена")
    return redirect("fitness_dash:lead_detail", club_id=club.id, lead_id=lead.id)


@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
@require_POST
def lead_to_member(request, club, staff, lead_id):
    """Заявка стала клиентом: создаём карточку и связываем."""
    lead = get_object_or_404(Lead, id=lead_id, club=club)
    if lead.member_id:
        return redirect("fitness_dash:member_detail", club_id=club.id, member_id=lead.member_id)

    member = Member.objects.create(club=club, full_name=lead.name or lead.phone,
                                   phone=lead.phone, notes=lead.comment,
                                   created_by=request.user)
    lead.member = member
    lead.status = Lead.Status.CAME
    lead.save(update_fields=["member", "status", "updated_at"])
    LeadNote.objects.create(lead=lead, text="Создана карточка клиента", author=request.user)
    messages.success(request, "Клиент создан из заявки")
    return redirect("fitness_dash:member_detail", club_id=club.id, member_id=member.id)


# ── Расходы и деньги ────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
@require(ADMIN)
def expenses(request, club, staff):
    month = _date(request.GET.get("from"), timezone.localdate().replace(day=1))
    rows = Expense.objects.filter(club=club, spent_on__gte=month).select_related("created_by")
    by_cat = (rows.values("category").annotate(s=Sum("amount")).order_by("-s"))
    labels = dict(Expense.Category.choices)
    return render(request, "fitness/dash/expenses.html",
                  _ctx(club, staff, expenses=rows.order_by("-spent_on", "-id")[:200],
                       month=month, total=rows.aggregate(s=Sum("amount"))["s"] or 0,
                       by_cat=[(labels.get(r["category"], r["category"]), r["s"]) for r in by_cat],
                       categories=Expense.Category.choices))


@login_required(login_url=LOGIN_URL)
@require(ADMIN)
@require_POST
def expense_add(request, club, staff):
    amount = _money(request.POST.get("amount"), "0")
    if amount <= 0:
        messages.error(request, "Сумма расхода не указана")
        return redirect("fitness_dash:expenses", club_id=club.id)
    services.add_expense(club, request.POST.get("category") or "other", amount,
                         note=(request.POST.get("note") or "").strip()[:300],
                         spent_on=_date(request.POST.get("spent_on")),
                         actor=request.user)
    messages.success(request, "Расход записан")
    return redirect("fitness_dash:expenses", club_id=club.id)


@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
def reports(request, club, staff):
    start = _date(request.GET.get("from"), timezone.localdate().replace(day=1))
    end = _date(request.GET.get("to"))
    pays = Payment.objects.filter(club=club, created_at__date__gte=start,
                                  created_at__date__lte=end)
    kinds = dict(Payment.Kind.choices)
    methods = dict(Payment.Method.choices)

    data = _ctx(club, staff, start=start, end=end,
                income=pays.aggregate(s=Sum("amount"))["s"] or 0,
                by_kind=[(kinds.get(r["kind"], r["kind"]), r["s"]) for r in
                         pays.values("kind").annotate(s=Sum("amount")).order_by("-s")],
                by_method=[(methods.get(r["method"], r["method"]), r["s"]) for r in
                           pays.values("method").annotate(s=Sum("amount")).order_by("-s")],
                visits=Visit.objects.filter(club=club, success=True,
                                            visit_time__date__gte=start,
                                            visit_time__date__lte=end).count(),
                sold=Membership.objects.filter(member__club=club,
                                               created_at__date__gte=start,
                                               created_at__date__lte=end).count(),
                debts=Membership.objects.filter(member__club=club, debt_amount__gt=0)
                      .aggregate(s=Sum("debt_amount"))["s"] or 0)

    # Загрузка тренеров: сколько провели, сколько не пришло. Без этого
    # нельзя понять, кто из тренеров держит клиентов, а кто теряет.
    load = []
    for t in club.trainers.filter(is_active=True):
        personal = TrainerBooking.objects.filter(trainer=t, date__gte=start, date__lte=end)
        groups = ClassBooking.objects.filter(group_class__trainer=t,
                                             date__gte=start, date__lte=end)
        came = (personal.filter(status=TrainerBooking.Status.CAME).count()
                + groups.filter(status=ClassBooking.Status.CAME).count())
        noshow = (personal.filter(status=TrainerBooking.Status.NO_SHOW).count()
                  + groups.filter(status=ClassBooking.Status.NO_SHOW).count())
        booked = personal.exclude(status=TrainerBooking.Status.CANCELLED).count() + \
            groups.exclude(status=ClassBooking.Status.CANCELLED).count()
        if booked or came:
            load.append({"trainer": t, "booked": booked, "came": came,
                         "noshow": noshow,
                         "share": round(came / booked * 100) if booked else 0})
    load.sort(key=lambda x: -x["came"])
    data["trainer_load"] = load

    # Откуда приходят заявки — чтобы знать, какая реклама работает
    sources = dict(Lead.Source.choices)
    data["lead_sources"] = [
        (sources.get(r["source"], r["source"]), r["n"], r["sold"])
        for r in (Lead.objects.filter(club=club, created_at__date__gte=start,
                                      created_at__date__lte=end)
                  .values("source")
                  .annotate(n=Count("id"),
                            sold=Count("id", filter=Q(status=Lead.Status.SOLD)))
                  .order_by("-n"))
    ]

    if can_see_profit(staff):
        exp = Expense.objects.filter(club=club, spent_on__gte=start, spent_on__lte=end)
        data["expenses"] = exp.aggregate(s=Sum("amount"))["s"] or 0
        data["profit"] = data["income"] - data["expenses"]
    return render(request, "fitness/dash/reports.html", data)


# ── Настройки клуба: секции, тренеры, абонементы, чаты ──────────────────────

@login_required(login_url=LOGIN_URL)
@require(ADMIN)
def setup(request, club, staff):
    if request.method == "POST":
        what = request.POST.get("what")
        if what == "club":
            club.name = (request.POST.get("name") or club.name).strip()[:200]
            club.address = (request.POST.get("address") or "").strip()[:300]
            club.phone = (request.POST.get("phone") or "").strip()[:50]
            club.whatsapp = (request.POST.get("whatsapp") or "").strip()[:30]
            club.working_hours = (request.POST.get("working_hours") or "").strip()[:200]
            club.description = (request.POST.get("description") or "").strip()
            club.tg_leads_chat_id = (request.POST.get("tg_leads_chat_id") or "").strip()[:50]
            club.tg_gym_chat_id = (request.POST.get("tg_gym_chat_id") or "").strip()[:50]
            for field, raw in (("tg_leads_thread_id", request.POST.get("tg_leads_thread_id")),
                               ("tg_gym_thread_id", request.POST.get("tg_gym_thread_id"))):
                setattr(club, field, int(raw) if (raw or "").isdigit() else None)
            if request.FILES.get("logo"):
                club.logo = request.FILES["logo"]
            if request.FILES.get("cover"):
                club.cover = request.FILES["cover"]
            club.save()
            messages.success(request, "Клуб сохранён")
        elif what == "section":
            name = (request.POST.get("s_name") or "").strip()[:150]
            if not name:
                messages.error(request, "Без названия направление не добавить")
            elif Section.objects.filter(club=club, name__iexact=name).exists():
                messages.error(request, f"«{name}» уже есть")
            else:
                Section.objects.create(
                    club=club, name=name,
                    icon=(request.POST.get("s_icon") or "").strip()[:8],
                    price_from=_money(request.POST.get("s_price"), "0"),
                    description=(request.POST.get("s_desc") or "").strip(),
                    photo=request.FILES.get("s_photo"),
                    sort_order=Section.objects.filter(club=club).count())
                messages.success(request, f"«{name}» добавлено")
        elif what == "section_presets":
            # Добавляем только те, которых ещё нет: кнопку нажимают повторно,
            # и дублировать «Бокс» вторым разом незачем.
            have = {s.name.strip().lower() for s in Section.objects.filter(club=club)}
            made = 0
            order = Section.objects.filter(club=club).count()
            for title, icon in SECTION_PRESETS:
                if title.strip().lower() in have:
                    continue
                Section.objects.create(club=club, name=title, icon=icon,
                                       sort_order=order)
                order += 1
                made += 1
            if made:
                messages.success(request, f"Добавлено направлений: {made}. "
                                          f"Цены и описания допишите ниже.")
            else:
                messages.info(request, "Все типовые направления уже есть")
        elif what == "section_edit":
            sec = Section.objects.filter(id=request.POST.get("section_id"), club=club).first()
            if sec:
                sec.name = (request.POST.get("s_name") or sec.name).strip()[:150]
                sec.icon = (request.POST.get("s_icon") or "").strip()[:8]
                sec.price_from = _money(request.POST.get("s_price"), "0")
                sec.description = (request.POST.get("s_desc") or "").strip()
                sec.is_active = request.POST.get("s_active") == "on"
                if request.FILES.get("s_photo"):
                    sec.photo = request.FILES["s_photo"]
                sec.save()
                messages.success(request, f"«{sec.name}» сохранено")
        elif what == "section_delete":
            sec = Section.objects.filter(id=request.POST.get("section_id"), club=club).first()
            if sec:
                # Удаляем только пустое направление: к нему могут быть
                # привязаны абонементы, занятия и заявки, и терять их нельзя.
                busy = (sec.plans.exists() or sec.classes.exists()
                        or sec.trainers.exists() or sec.leads.exists())
                if busy:
                    sec.is_active = False
                    sec.save(update_fields=["is_active", "updated_at"])
                    messages.info(request, f"«{sec.name}» скрыто с сайта: "
                                           f"к нему привязаны занятия или абонементы, "
                                           f"поэтому запись сохранена")
                else:
                    name = sec.name
                    sec.delete()
                    messages.success(request, f"«{name}» удалено")
        elif what == "plan":
            MembershipPlan.objects.create(
                club=club, name=(request.POST.get("p_name") or "").strip()[:150],
                visits_number=int(request.POST.get("p_visits") or 0),
                validity_days=int(request.POST.get("p_days") or 30),
                price=_money(request.POST.get("p_price"), "0"))
            messages.success(request, "Абонемент добавлен")
        elif what == "trainer":
            Trainer.objects.create(
                club=club, name=(request.POST.get("t_name") or "").strip()[:150],
                phone=(request.POST.get("t_phone") or "").strip()[:50],
                price_per_session=_money(request.POST.get("t_price"), "0"),
                bio=(request.POST.get("t_bio") or "").strip(),
                photo=request.FILES.get("t_photo"))
            messages.success(request, "Тренер добавлен")
        return redirect("fitness_dash:setup", club_id=club.id)

    return render(request, "fitness/dash/setup.html",
                  _ctx(club, staff,
                       sections=club.sections.all(),
                       plans=club.plans.all(),
                       trainers=club.trainers.all().prefetch_related("sections"),
                       staff_list=club.staff.select_related("user"),
                       roles=ClubStaff.Role.choices))

# ── Расписание групповых занятий ────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
@require()
def classes(request, club, staff):
    """Расписание на неделю: занятие, тренер, сколько мест осталось."""
    day = _date(request.GET.get("date"))
    week_start = day - timedelta(days=day.weekday())
    days = [week_start + timedelta(days=i) for i in range(7)]

    trainer = my_trainer(request.user, club)
    rows = (GroupClass.objects.filter(club=club, is_active=True)
            .select_related("trainer", "section").order_by("time_from", "id"))
    if staff.role == TRAINER and trainer:
        rows = rows.filter(trainer=trainer)
    rows = list(rows)

    # Считаем занятость одним запросом на неделю, а не по занятию на день:
    # иначе страница расписания делает сотню запросов.
    taken = {}
    booked = (ClassBooking.objects
              .filter(group_class__in=rows, date__in=days)
              .exclude(status=ClassBooking.Status.CANCELLED)
              .values("group_class_id", "date").annotate(n=Count("id")))
    for b in booked:
        taken[(b["group_class_id"], b["date"])] = b["n"]

    grid = []
    for d in days:
        items = []
        for c in rows:
            if c.weekday != d.weekday():
                continue
            used = taken.get((c.id, d), 0)
            items.append({"cls": c, "used": used,
                          "free": max(0, c.capacity - used)})
        grid.append({"day": d, "items": items, "is_today": d == timezone.localdate()})

    return render(request, "fitness/dash/classes.html",
                  _ctx(club, staff, grid=grid, day=day, week_start=week_start,
                       prev_week=week_start - timedelta(days=7),
                       next_week=week_start + timedelta(days=7),
                       all_classes=rows,
                       sections=club.sections.filter(is_active=True),
                       trainers=club.trainers.filter(is_active=True)))


@login_required(login_url=LOGIN_URL)
@require(ADMIN)
@require_POST
def class_save(request, club, staff):
    hhmm = (request.POST.get("time_from") or "").strip()
    try:
        t = datetime.strptime(hhmm, "%H:%M").time()
    except ValueError:
        messages.error(request, "Время в формате 19:00")
        return redirect("fitness_dash:classes", club_id=club.id)

    sec = request.POST.get("section_id")
    tr = request.POST.get("trainer_id")
    GroupClass.objects.create(
        club=club,
        name=(request.POST.get("name") or "").strip()[:150] or "Занятие",
        section=Section.objects.filter(id=sec, club=club).first() if (sec or "").isdigit() else None,
        trainer=Trainer.objects.filter(id=tr, club=club).first() if (tr or "").isdigit() else None,
        weekday=int(request.POST.get("weekday") or 0),
        time_from=t,
        duration_min=int(request.POST.get("duration_min") or 60),
        capacity=int(request.POST.get("capacity") or 12),
        price=_money(request.POST.get("price"), "0"),
        room=(request.POST.get("room") or "").strip()[:100],
    )
    messages.success(request, "Занятие добавлено в расписание")
    return redirect("fitness_dash:classes", club_id=club.id)


@login_required(login_url=LOGIN_URL)
@require()
def class_day(request, club, staff, class_id):
    """Кто записан на занятие в этот день — и отметки о приходе."""
    cls = get_object_or_404(GroupClass.objects.select_related("trainer", "section"),
                            id=class_id, club=club)
    day = _date(request.GET.get("date"))
    rows = (cls.bookings.filter(date=day).select_related("member")
            .order_by("id"))
    return render(request, "fitness/dash/class_day.html",
                  _ctx(club, staff, cls=cls, day=day, rows=rows,
                       free=cls.free_on(day),
                       members=Member.objects.filter(club=club, is_active=True)
                               .order_by("full_name")[:500]))


@login_required(login_url=LOGIN_URL)
@require()
@require_POST
def class_book(request, club, staff, class_id):
    cls = get_object_or_404(GroupClass, id=class_id, club=club)
    day = _date(request.POST.get("date"))

    # Мест может не остаться, пока админ открывал форму
    if cls.free_on(day) <= 0:
        messages.error(request, f"Мест нет: {cls.capacity} из {cls.capacity} заняты")
        return redirect(f"/ru/cabinet/fitness/{club.id}/classes/{cls.id}/?date={day:%Y-%m-%d}")

    member = None
    raw = request.POST.get("member_id")
    if raw and raw.isdigit():
        member = Member.objects.filter(id=int(raw), club=club).first()

    ClassBooking.objects.create(
        group_class=cls, date=day, member=member,
        client_name=(request.POST.get("client_name") or "").strip()[:150],
        phone=(request.POST.get("phone") or "").strip()[:30],
        comment=(request.POST.get("comment") or "").strip()[:300],
        created_by=request.user,
    )
    messages.success(request, "Записали")
    return redirect(f"/ru/cabinet/fitness/{club.id}/classes/{cls.id}/?date={day:%Y-%m-%d}")


@login_required(login_url=LOGIN_URL)
@require()
@require_POST
def class_booking_status(request, club, staff, booking_id):
    b = get_object_or_404(ClassBooking.objects.select_related("group_class", "member"),
                          id=booking_id, group_class__club=club)
    action = request.POST.get("action")
    labels = {"came": ClassBooking.Status.CAME,
              "no_show": ClassBooking.Status.NO_SHOW,
              "cancel": ClassBooking.Status.CANCELLED,
              "back": ClassBooking.Status.BOOKED}
    if action in labels:
        b.status = labels[action]
        b.save(update_fields=["status", "updated_at"])
        # Пришёл на групповое — это посещение зала: списываем, как на входе
        if b.status == ClassBooking.Status.CAME and b.member_id:
            services.check_in(club, b.member, trainer=b.group_class.trainer,
                              actor=request.user)
    return redirect(f"/ru/cabinet/fitness/{club.id}/classes/{b.group_class_id}/"
                    f"?date={b.date:%Y-%m-%d}")

# ── Сотрудники клуба ────────────────────────────────────────────────────────

def _club_admins(club):
    """Действующие администраторы клуба."""
    return ClubStaff.objects.filter(club=club, role=ADMIN, is_active=True)


@login_required(login_url=LOGIN_URL)
@require(ADMIN)
@require_POST
def staff_add(request, club, staff):
    """Добавляет сотрудника: по существующему логину или создаёт новый.

    Логины сотрудников заводит сам администратор клуба — ждать поддержки
    ради кассира на смену неудобно.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    login = (request.POST.get("login") or "").strip()
    role = request.POST.get("role")
    if role not in dict(ClubStaff.Role.choices):
        role = ClubStaff.Role.CASHIER
    if not login:
        messages.error(request, "Укажите логин сотрудника")
        return redirect("fitness_dash:setup", club_id=club.id)

    user = User.objects.filter(username__iexact=login).first()
    created = False
    if not user:
        password = (request.POST.get("password") or "").strip()
        if len(password) < 6:
            messages.error(request, f"Пользователя «{login}» нет. "
                                    f"Чтобы создать нового, задайте пароль "
                                    f"не короче 6 символов.")
            return redirect("fitness_dash:setup", club_id=club.id)
        user = User.objects.create_user(
            username=login, password=password,
            first_name=(request.POST.get("full_name") or "").strip()[:150])
        created = True

    if ClubStaff.objects.filter(user=user, club=club).exists():
        link = ClubStaff.objects.get(user=user, club=club)
        link.role = role
        link.is_active = True
        link.save(update_fields=["role", "is_active", "updated_at"])
        messages.success(request, f"{login}: доступ обновлён — {link.get_role_display()}")
    else:
        ClubStaff.objects.create(user=user, club=club, role=role)
        messages.success(
            request,
            f"{login} добавлен как «{dict(ClubStaff.Role.choices)[role]}»"
            + (" · логин создан" if created else ""))

    # Тренеру нужна его карточка, иначе он войдёт и не увидит своих записей
    if role == TRAINER:
        raw = request.POST.get("trainer_id")
        if (raw or "").isdigit():
            Trainer.objects.filter(id=int(raw), club=club).update(user=user)
        elif request.POST.get("make_trainer") == "on":
            name = ((request.POST.get("full_name") or "").strip()
                    or user.get_full_name() or login)
            Trainer.objects.create(club=club, user=user, name=name[:150],
                                   phone=(request.POST.get("phone") or "").strip()[:50])
            messages.info(request, f"Создана карточка тренера «{name}»")
    return redirect("fitness_dash:setup", club_id=club.id)


@login_required(login_url=LOGIN_URL)
@require(ADMIN)
@require_POST
def staff_edit(request, club, staff, staff_id):
    """Меняет уровень доступа или выключает сотрудника."""
    link = get_object_or_404(ClubStaff.objects.select_related("user"),
                             id=staff_id, club=club)
    action = request.POST.get("action")
    role = request.POST.get("role")

    # Последнего администратора не отбираем: клуб останется без хозяина и
    # никто уже не сможет ни добавить сотрудника, ни поправить настройки.
    last_admin = (link.role == ADMIN and link.is_active
                  and _club_admins(club).count() <= 1)
    if last_admin and (action in ("off", "remove") or (role and role != ADMIN)):
        messages.error(request, "Это единственный администратор клуба. "
                                "Сначала назначьте другого.")
        return redirect("fitness_dash:setup", club_id=club.id)

    if action == "off":
        link.is_active = False
        link.save(update_fields=["is_active", "updated_at"])
        messages.success(request, f"{link.user.username}: доступ выключен")
    elif action == "on":
        link.is_active = True
        link.save(update_fields=["is_active", "updated_at"])
        messages.success(request, f"{link.user.username}: доступ включён")
    elif action == "remove":
        name = link.user.username
        link.delete()
        messages.success(request, f"{name}: доступ к клубу убран")
    elif role in dict(ClubStaff.Role.choices):
        link.role = role
        link.save(update_fields=["role", "updated_at"])
        messages.success(request, f"{link.user.username}: теперь {link.get_role_display()}")
    return redirect("fitness_dash:setup", club_id=club.id)


@login_required(login_url=LOGIN_URL)
@require(ADMIN)
@require_POST
def staff_password(request, club, staff, staff_id):
    """Задаёт сотруднику новый пароль — когда тот его забыл."""
    link = get_object_or_404(ClubStaff.objects.select_related("user"),
                             id=staff_id, club=club)
    password = (request.POST.get("password") or "").strip()
    if len(password) < 6:
        messages.error(request, "Пароль не короче 6 символов")
    else:
        link.user.set_password(password)
        link.user.save(update_fields=["password"])
        messages.success(request, f"{link.user.username}: пароль изменён")
    return redirect("fitness_dash:setup", club_id=club.id)

