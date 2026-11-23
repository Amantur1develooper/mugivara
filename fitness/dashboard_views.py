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
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from integrations import tgbot

from . import services, tg
from .access import (ADMIN, CASHIER, TRAINER, can_see_money, can_see_profit,
                     my_clubs, my_trainer, require, staff_of)
from .models import (SECTION_PRESETS, ClassBooking, ClassDay, ClubStaff,
                     DiscountPreset, Expense, FitnessClub, GroupClass, GroupMember,
                     Lead, LeadNote,
                     Member, Membership, MembershipPlan, OwedVisit, Payment, Section,
                     Trainer, TrainerBooking, TrainerSchedule, TrainingGroup,
                     Visit)

LOGIN_URL = "dashboard:login"


def _money(raw, default="0"):
    """Сумма из формы. Пробелы любые: браузер и телефонные клавиатуры
    подставляют не только обычный пробел, но и неразрывный, а на нём
    Decimal падал и сумма молча становилась нулевой."""
    text = "".join(ch for ch in str(raw or default) if not ch.isspace())
    try:
        return Decimal(text.replace(",", "."))
    except InvalidOperation:
        return Decimal(default)


def _date(raw, default=None):
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return default or timezone.localdate()


def _int(raw, default=0, lo=0, hi=10000):
    """Число из формы: пустое поле и опечатка не должны валить страницу."""
    try:
        return max(lo, min(hi, int(str(raw).strip())))
    except (TypeError, ValueError):
        return default


def _time(raw):
    """Время из поля type="time" — «19:00». Не разобрали — None."""
    try:
        return datetime.strptime((raw or "").strip()[:5], "%H:%M").time()
    except ValueError:
        return None


def _nav_counts(club, staff):
    """Счётчики на пунктах меню: заявки без ответа и занятия в долг.

    В навигации они нужнее, чем на страницах: по ним видно, куда идти, не
    открывая всё подряд. Кассиру и администратору — тренеру деньги и
    заявки не показываем, у него и счётчиков нет.
    """
    if not can_see_money(staff):
        return {}
    return {
        # Заявки, которые ещё ведут: записанные и пришедшие тоже требуют
        # внимания, пока не купили и не отказались.
        "nav_leads": Lead.objects.filter(club=club).exclude(
            status__in=[Lead.Status.SOLD, Lead.Status.LOST]).count(),
        "nav_debts": OwedVisit.objects.filter(club=club, is_settled=False).count(),
    }


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
    base.update(_nav_counts(club, staff))
    base.update(extra)
    return base


# ── Список клубов и сводка ──────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def clubs(request):
    items = my_clubs(request.user)
    if items.count() == 1:
        return redirect("fitness_dash:home", club_id=items.first().id)
    return render(request, "fitness/dash/clubs.html", {"clubs": items})


CHART_DAYS = 14


def _home_chart(club, today, *, money=True):
    """Данные графика на сводке: посещения и выручка по дням.

    Геометрию считаем здесь, а не в шаблоне: в русской локали числа
    выводятся с запятой, и координаты вида «12,5» ломают и SVG, и JS. А
    рисуем обычным SVG — без библиотек, которые на телефоне с плохой
    связью грузятся дольше самой страницы.
    """
    start = today - timedelta(days=CHART_DAYS - 1)
    days = [start + timedelta(days=i) for i in range(CHART_DAYS)]

    visits = {}
    for row in (Visit.objects
                .filter(club=club, success=True, visit_time__date__gte=start)
                .values("visit_time__date").annotate(n=Count("id"))):
        visits[row["visit_time__date"]] = row["n"]

    cash = {}
    if money:
        for row in (Payment.objects
                    .filter(club=club, created_at__date__gte=start)
                    .values("created_at__date").annotate(s=Sum("amount"))):
            cash[row["created_at__date"]] = int(row["s"] or 0)

    v_max = max([visits.get(d, 0) for d in days] + [1])
    m_max = max([cash.get(d, 0) for d in days] + [1])

    # Сетка: 14 столбиков с отступами, высота 100 — остальное тянется CSS
    step = 100 / CHART_DAYS
    bar_w = step * 0.56
    bars, points = [], []
    for i, d in enumerate(days):
        v = visits.get(d, 0)
        m = cash.get(d, 0)
        x = i * step + (step - bar_w) / 2
        h = (v / v_max) * 72 if v else 0
        bars.append({
            "day": d,
            "visits": v,
            "money": m,
            "x": f"{x:.2f}",
            "w": f"{bar_w:.2f}",
            "y": f"{(78 - h):.2f}",
            "h": f"{h:.2f}",
            "is_today": d == today,
            "label": f"{d.day}",
            "weekend": d.weekday() >= 5,
        })
        if money:
            points.append(f"{(i * step + step / 2):.2f},"
                          f"{(78 - (m / m_max) * 66):.2f}")

    return {
        "bars": bars,
        "line": " ".join(points),
        "visits_total": sum(visits.get(d, 0) for d in days),
        "money_total": sum(cash.get(d, 0) for d in days),
        "visits_max": v_max,
        "money_max": m_max,
        "money": money,
        "from": start,
        "to": today,
    }


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

    data["chart"] = _home_chart(club, today, money=can_see_money(staff))

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


@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
def member_pass_card(request, club, staff, member_id):
    """Короткая карточка клиента для панели прохода.

    На ресепшене нужно одно: посмотреть, пускать ли человека, и пустить.
    Открывать ради этого полную карточку с абонементами, платежами и
    правкой — лишние полэкрана и лишний переход.
    """
    member = get_object_or_404(Member, id=member_id, club=club)
    today = timezone.localdate()
    ms = member.active_membership()
    frozen = Membership.objects.filter(member=member, is_active=True,
                                       is_frozen=True).first()

    state = "none"
    if ms and ms.is_usable(today):
        state = "active"
    elif frozen:
        state = "frozen"

    # Сегодняшняя тренировка его групп: кассиру полезно сказать вслух
    # «вам в малый зал к 19:00», а не просто открыть дверь.
    links = [l for l in member.group_links.filter(is_active=True)
             .select_related("group", "group__trainer")
             .prefetch_related("group__slots__trainer")]
    today_items = _week_plan(links)[today.weekday()]["items"]

    return render(request, "fitness/dash/_pass_card.html", _ctx(
        club, staff, member=member, ms=ms, state=state, frozen=frozen,
        today_items=today_items,
        debts=member.owed_visits.filter(is_settled=False).count(),
        visited_today=member.visits.filter(visit_time__date=today, success=True).exists(),
        trainers=club.trainers.filter(is_active=True),
    ))


# ── Клиенты ─────────────────────────────────────────────────────────────────

def _members_queryset(request, club, staff):
    """Отбор клиентов — один для страницы и для выгрузки.

    Иначе в файл попадает не то, что человек видит на экране: он ищет
    должников, а выгружает всю базу.
    """
    q = (request.GET.get("q") or "").strip()
    rows = (Member.objects.filter(club=club)
            .prefetch_related("memberships__plan", "visits"))
    if q:
        rows = rows.filter(Q(full_name__icontains=q) | Q(phone__icontains=q)
                           | Q(card_id__icontains=q))

    # Тренеру по умолчанию показываем его клиентов: в списке всего зала он
    # своих не найдёт. Но когда он ищет по имени или телефону, отдаём любого
    # клиента клуба — на ресепшене тренера тоже спрашивают, а закрытая
    # карточка просто мешает работать.
    trainer = my_trainer(request.user, club)
    if staff.role == TRAINER and trainer and not q:
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
    return rows.order_by("full_name")


@login_required(login_url=LOGIN_URL)
@require()
def members(request, club, staff):
    rows = _members_queryset(request, club, staff)
    shown = list(rows.prefetch_related("memberships__plan")[:300])

    # Состояние абонемента и долги — одним проходом на всех. Раньше шаблон
    # звал active_membership() на каждую строку, и список из трёхсот человек
    # делал три сотни запросов.
    today = timezone.localdate()
    owed = {}
    for d in OwedVisit.objects.filter(member__in=shown, is_settled=False):
        owed[d.member_id] = owed.get(d.member_id, 0) + 1

    rank = {"active": 3, "frozen": 2, "none": 1}
    for m in shown:
        best, best_ms = "none", None
        for ms in m.memberships.all():
            if not ms.is_active:
                continue
            now = ms.state(today)
            if rank[now] > rank[best]:
                best, best_ms = now, ms
            elif best_ms is None:
                best_ms = ms
        m.state = best
        m.ms = best_ms
        m.owed = owed.get(m.id, 0)

    return render(request, "fitness/dash/members.html",
                  _ctx(club, staff,
                       q=(request.GET.get("q") or "").strip(),
                       only=(request.GET.get("filter") or "").strip(),
                       members=shown,
                       total=rows.count(),
                       export_qs=request.GET.urlencode()))


WEEKDAY_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def _week_plan(group_links):
    """Личное расписание клиента: в какие дни и часы он приходит.

    Расписание лежит у каждой группы отдельно, а человека спрашивают
    иначе: «когда ему приходить?» — значит, недели всех его групп надо
    сложить в одну.
    """
    plan = [{"i": i, "short": WEEKDAY_SHORT[i],
             "name": dict(GroupClass._meta.get_field("weekday").choices)[i],
             "items": []} for i in range(7)]
    for link in group_links:
        for slot in link.group.slots.all():
            if not slot.is_active:
                continue
            plan[slot.weekday]["items"].append({
                "time": slot.time_from, "group": link.group, "slot": slot,
                "room": slot.room, "trainer": slot.trainer,
            })
    for day in plan:
        day["items"].sort(key=lambda x: x["time"])
    return plan


@login_required(login_url=LOGIN_URL)
@require()
def member_detail(request, club, staff, member_id):
    member = get_object_or_404(Member.objects.prefetch_related(
        "memberships__plan", "memberships__trainer"), id=member_id, club=club)
    group_links = list(member.group_links.filter(is_active=True)
                       .select_related("group", "group__section", "group__trainer")
                       .prefetch_related("group__slots__trainer"))
    week_plan = _week_plan(group_links)
    data = _ctx(club, staff,
                member=member,
                # В каких группах человек занимается: с карточки должно быть
                # видно, к кому и когда он ходит.
                group_links=group_links,
                week_plan=week_plan,
                week_days=[d for d in week_plan if d["items"]],
                today_weekday=timezone.localdate().weekday(),
                debts=(member.owed_visits.filter(is_settled=False)
                       .select_related("group_class", "training_group")),
                settled=(member.owed_visits.filter(is_settled=True)
                         .select_related("settled_from__plan")[:10]),
                memberships=member.memberships.select_related("plan", "trainer"),
                visits=member.visits.select_related("membership__plan", "trainer")[:30],
                # В «паспорте» слева нужны итог и последний приход: по ним
                # сразу видно, ходит человек или пропал.
                visits_total=member.visits.filter(success=True).count(),
                last_visit=(member.visits.filter(success=True)
                            .order_by("-visit_time").first()),
                plans=club.plans.filter(is_active=True),
                discounts=club.discounts.filter(is_active=True),
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

    # Скидку принимаем и процентом, и суммой. Считает сервер: на процент в
    # браузере полагаться нельзя — там мог не отработать скрипт, да и
    # подправить поле в отправке может кто угодно.
    price = _money(request.POST.get("price"), str(plan.price))
    discount = _money(request.POST.get("discount"), "0")
    pct = _money(request.POST.get("discount_pct"), "0")

    # Нажали готовую скидку клуба — она и решает, сколько снять: кассир
    # выбирал её, а не цифру в поле.
    note = ""
    raw_preset = request.POST.get("preset")
    if (raw_preset or "").isdigit():
        preset = club.discounts.filter(id=int(raw_preset), is_active=True).first()
        if preset:
            note = preset.name
            if preset.percent:
                pct = Decimal(preset.percent)
            else:
                pct = Decimal("0")
                discount = Decimal(preset.amount)
    if pct > 0:
        pct = min(pct, Decimal("100"))
        by_pct = (price * pct / Decimal("100")).quantize(Decimal("1"))
        # Если сумма в поле не отвечает проценту (скрипт не отработал),
        # верим проценту: его кассир и выбирал.
        if abs(by_pct - discount) > 1:
            discount = by_pct
    discount = max(Decimal("0"), min(discount, price))

    ms = services.sell_membership(
        club, member, plan,
        price=price,
        discount=discount,
        paid=_money(request.POST.get("paid"), str(price - discount)),
        trainer=trainer,
        # «Активация с 1 посещения» — галочка в бланке, поэтому логика
        # обратная: снял её — абонемент начинается сегодня.
        start_today=request.POST.get("by_first_visit") != "on",
        method=request.POST.get("method") or "cash",
        actor=request.user,
        discount_note=note,
    )
    note = "начнётся с первого посещения" if not ms.activated else f"с {ms.start_date:%d.%m.%Y}"
    tail = ""
    if ms.discount_amount:
        share = int(ms.discount_amount / ms.price * 100) if ms.price else 0
        named = f" «{ms.discount_note}»" if ms.discount_note else ""
        tail = f" · скидка{named} {ms.discount_amount:.0f} сом ({share}%)"
    if ms.debt_amount:
        tail += f" · долг {ms.debt_amount:.0f} сом"
    messages.success(request, f"Абонемент продан, {note}{tail}")
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

    # Групповые тренировки этого дня недели: без них в шахматке видны только
    # личные записи, и выходит, что у тренера день пустой, хотя в это время
    # у него группа на двенадцать человек.
    slots = (GroupClass.objects
             .filter(club=club, is_active=True, weekday=day.weekday())
             .select_related("group", "group__section", "trainer", "section")
             .order_by("time_from"))
    if staff.role == TRAINER and trainer:
        slots = slots.filter(trainer=trainer)
    slots = list(slots)

    cancelled = {c.group_class_id for c in
                 ClassDay.objects.filter(group_class__in=slots, date=day,
                                         is_cancelled=True)}

    # Сколько человек уже отметили на каждом занятии — одним запросом на всех
    marked = dict(ClassBooking.objects
                  .filter(group_class__in=slots, date=day,
                          status=ClassBooking.Status.CAME)
                  .values_list("group_class")
                  .annotate(n=Count("id")))

    # Сетка часов: от самого раннего начала до самого позднего конца, но не
    # уже 8:00–22:00 — иначе пустая таблица выглядит сломанной.
    start_hour, end_hour = 8, 22
    for b in rows:
        start_hour = min(start_hour, b.time_from.hour)
        end_hour = max(end_hour, (b.time_to.hour + 1) if b.time_to.minute else b.time_to.hour)
    for sl in slots:
        start_hour = min(start_hour, sl.time_from.hour)
    hours = list(range(start_hour, max(end_hour, start_hour + 1)))

    cells = {}
    for b in rows:
        cells.setdefault(b.trainer_id, {}).setdefault(b.time_from.hour, []).append(b)

    # Группы кладём в ту же сетку отдельным слоем: в клетке сначала группа,
    # потом личные записи — так читается «в 19:00 у него группа и один свой».
    group_cells = {}
    orphans = []
    for sl in slots:
        card = {"slot": sl,
                "title": sl.group.title if sl.group_id else sl.name,
                "size": sl.group.size if sl.group_id else None,
                "came": marked.get(sl.id, 0),
                "cancelled": sl.id in cancelled}
        # Занятие без тренера в колонку не попадёт — колонки именно по
        # тренерам. Молча терять его нельзя, поэтому собираем отдельно и
        # показываем под таблицей: это ещё и напоминание назначить тренера.
        if sl.trainer_id:
            group_cells.setdefault(sl.trainer_id, {}) \
                       .setdefault(sl.time_from.hour, []).append(card)
        else:
            orphans.append(card)

    # «Где будет этот человек» — поиск по имени, телефону и карте. На
    # ресепшене спрашивают именно так, а не «покажи записи тренера».
    q = (request.GET.get("q") or "").strip()
    found = []
    if q:
        for mem in (Member.objects.filter(club=club, is_active=True)
                    .filter(Q(full_name__icontains=q) | Q(phone__icontains=q)
                            | Q(card_id__icontains=q))
                    .prefetch_related("group_links__group__slots__trainer",
                                      "group_links__group__section")
                    .order_by("full_name")[:8]):
            links = [l for l in mem.group_links.all() if l.is_active]
            plan = _week_plan(links)
            # Что у человека сегодня: личная запись к тренеру и тренировки
            # его групп в этот день недели.
            personal = list(TrainerBooking.objects
                            .filter(club=club, member=mem, date=day)
                            .exclude(status=TrainerBooking.Status.CANCELLED)
                            .select_related("trainer").order_by("time_from"))
            found.append({
                "member": mem,
                "today": plan[day.weekday()]["items"],
                "personal": personal,
                "days": [d for d in plan if d["items"]],
            })

    return render(request, "fitness/dash/board.html",
                  _ctx(club, staff, day=day, hours=hours, trainers=list(trainers),
                       q=q, found=found,
                       cells=cells, group_cells=group_cells, total=rows.count(),
                       groups_today=len(slots), orphans=orphans,
                       prev_day=day - timedelta(days=1), next_day=day + timedelta(days=1),
                       today=timezone.localdate()))


@login_required(login_url=LOGIN_URL)
@require()
def members_find(request, club, staff):
    """Короткий ответ для поиска клиента в панелях: имя, карта, телефон.

    Отдаём ровно то, что показывают в списке выбора, — страницу целиком
    ради трёх строк гонять незачем.
    """
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"items": []})
    rows = (Member.objects.filter(club=club, is_active=True)
            .filter(Q(full_name__icontains=q) | Q(phone__icontains=q)
                    | Q(card_id__icontains=q))
            .order_by("full_name")[:10])
    return JsonResponse({"items": [
        {"id": m.id, "name": m.full_name, "card": m.card_id, "phone": m.phone}
        for m in rows
    ]})


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
    # Адрес собираем через reverse: кабинет живёт под /ru/, /ky/ и /en/, а
    # прибитый «/ru/» выкидывал кассира из его языка после каждой записи.
    return redirect(reverse("fitness_dash:board", args=[club.id])
                    + f"?date={booking.date:%Y-%m-%d}")


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


# ── Группы ──────────────────────────────────────────────────────────────────


def _group_or_404(club, group_id):
    return get_object_or_404(
        TrainingGroup.objects.select_related("section", "trainer"),
        id=group_id, club=club)


@login_required(login_url=LOGIN_URL)
@require()
def groups(request, club, staff):
    """Группы клуба: кто с кем занимается и по каким дням."""
    rows = (TrainingGroup.objects.filter(club=club)
            .select_related("section", "trainer")
            .annotate(people=Count("links", filter=Q(links__is_active=True),
                                   distinct=True))
            .prefetch_related("slots")
            .order_by("-is_active", "sort_order", "id"))

    # Тренер видит свои группы первыми: на телефоне листать чужие незачем.
    trainer = my_trainer(request.user, club)
    if staff.role == TRAINER and trainer:
        rows = rows.filter(trainer=trainer)

    return render(request, "fitness/dash/groups.html",
                  _ctx(club, staff, rows=list(rows),
                       sections=club.sections.filter(is_active=True),
                       trainers=club.trainers.filter(is_active=True),
                       is_trainer=(staff.role == TRAINER)))


@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
@require_POST
def group_save(request, club, staff, group_id=None):
    g = _group_or_404(club, group_id) if group_id else TrainingGroup(club=club)
    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "У группы должно быть название.")
        return redirect("fitness_dash:groups", club.id)

    g.name = name
    g.note = (request.POST.get("note") or "").strip()
    g.section = club.sections.filter(id=request.POST.get("section") or 0).first()
    g.trainer = club.trainers.filter(id=request.POST.get("trainer") or 0).first()
    g.capacity = _int(request.POST.get("capacity"), 14)
    g.tg_chat_id = (request.POST.get("tg_chat_id") or "").strip()[:50]
    thread = (request.POST.get("tg_thread_id") or "").strip()
    g.tg_thread_id = int(thread) if thread.isdigit() else None
    g.is_active = bool(request.POST.get("is_active")) or not group_id
    g.save()
    messages.success(request, f"Группа «{g.title}» сохранена.")
    return redirect("fitness_dash:group_detail", club.id, g.id)


@login_required(login_url=LOGIN_URL)
@require()
def group_detail(request, club, staff, group_id):
    """Состав группы и её расписание."""
    g = _group_or_404(club, group_id)
    roster = list(g.roster())
    inside = {link.member_id for link in roster}

    # Кого можно добавить: клиенты клуба, которых в группе ещё нет. Поиск
    # нужен, потому что в зале их бывает несколько сотен.
    q = (request.GET.get("q") or "").strip()
    free = Member.objects.filter(club=club, is_active=True).exclude(id__in=inside)
    if q:
        free = free.filter(Q(full_name__icontains=q) | Q(phone__icontains=q))
    free = free.order_by("full_name")[:40 if q else 20]

    # Ближайшая тренировка: сегодняшнюю отмечают прямо здесь, не уходя на
    # отдельную страницу занятия — на ресепшене лишний переход это время.
    today = timezone.localdate()
    slot_today = (g.slots.filter(is_active=True, weekday=today.weekday())
                  .select_related("trainer").order_by("time_from").first())
    state_today = slot_today.day_state(today) if slot_today else None
    marks = {}
    if slot_today:
        marks = {b.member_id: b for b in
                 ClassBooking.objects.filter(group_class=slot_today, date=today)}

    # У кого абонемент не пускает: отметка «пришёл» у него ничего не спишет,
    # и без пометки он выглядел бы на странице так же, как оплативший.
    # Видно это и до тренировки — понятно, с кого взять деньги. Абонементы
    # берём одним запросом: дёргать active_membership() на каждого значило
    # бы по два запроса на человека.
    # Состояние абонемента каждого: зелёный пускаем, синий заморожен,
    # красный пройти нельзя. Берём одним запросом на весь состав.
    ids = [l.member_id for l in roster]
    state = {}
    for ms in (Membership.objects.filter(member__in=ids, is_active=True)
               .select_related("plan").order_by("-id")):
        now = ms.state(today)
        # У человека может быть несколько абонементов: действующий важнее
        # замороженного, замороженный — важнее кончившегося.
        rank = {"active": 3, "frozen": 2, "none": 1}
        if rank[now] > rank.get(state.get(ms.member_id, "none"), 0):
            state[ms.member_id] = now

    owed = {}
    for d in OwedVisit.objects.filter(member__in=ids, is_settled=False):
        owed[d.member_id] = owed.get(d.member_id, 0) + 1

    for link in roster:
        link.mark = marks.get(link.member_id)
        link.state = state.get(link.member_id, "none")
        link.payless = link.state != "active"
        link.owed = owed.get(link.member_id, 0)

    return render(request, "fitness/dash/group_detail.html",
                  _ctx(club, staff, g=g, roster=roster, free=list(free), q=q,
                       slot_today=slot_today, state_today=state_today, today=today,
                       came_today=sum(1 for m in marks.values() if m.status == "came"),
                       left=list(g.links.filter(is_active=False)
                                 .select_related("member")[:30]),
                       slots=list(g.schedule().select_related("trainer")),
                       sections=club.sections.filter(is_active=True),
                       trainers=club.trainers.filter(is_active=True),
                       weekdays=GroupClass._meta.get_field("weekday").choices))


@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
@require_POST
def group_roster(request, club, staff, group_id):
    """Добавить человека в группу или вывести из неё."""
    g = _group_or_404(club, group_id)
    action = request.POST.get("action")

    if action == "add":
        member = get_object_or_404(Member, id=request.POST.get("member") or 0, club=club)
        link, created = GroupMember.objects.get_or_create(group=g, member=member)
        if not created and not link.is_active:
            # Вернулся: ту же связь включаем обратно, чтобы в истории не
            # появилось два «вошёл» на одного человека.
            link.is_active = True
            link.left_on = None
            link.joined_on = timezone.localdate()
            link.save(update_fields=["is_active", "left_on", "joined_on", "updated_at"])
            created = True
        messages.success(request, f"{member.full_name} в группе «{g.title}»."
                         if created else f"{member.full_name} уже в группе.")
        if request.POST.get("back"):
            return redirect(request.POST["back"])
    elif action == "remove":
        link = get_object_or_404(GroupMember, id=request.POST.get("link") or 0, group=g)
        link.is_active = False
        link.left_on = timezone.localdate()
        link.save(update_fields=["is_active", "left_on", "updated_at"])
        messages.success(request, f"{link.member.full_name} выведен из группы. "
                         "Данные и история занятий остались.")
    return redirect("fitness_dash:group_detail", club.id, g.id)


@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
@require_POST
def group_slot(request, club, staff, group_id):
    """Поставить группе тренировку в расписание или убрать её."""
    g = _group_or_404(club, group_id)

    if request.POST.get("action") == "remove":
        slot = get_object_or_404(GroupClass, id=request.POST.get("slot") or 0,
                                 club=club, group=g)
        slot.is_active = False
        slot.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "Тренировка убрана из расписания.")
        return redirect("fitness_dash:group_detail", club.id, g.id)

    hhmm = _time(request.POST.get("time_from"))
    if hhmm is None:
        messages.error(request, "Укажите время начала.")
        return redirect("fitness_dash:group_detail", club.id, g.id)

    GroupClass.objects.create(
        club=club, group=g, section=g.section, trainer=g.trainer,
        name=g.title,
        weekday=_int(request.POST.get("weekday"), 0),
        time_from=hhmm,
        duration_min=_int(request.POST.get("duration_min"), 60),
        capacity=g.capacity,
        room=(request.POST.get("room") or "").strip(),
    )
    messages.success(request, "Тренировка добавлена в расписание.")
    return redirect("fitness_dash:group_detail", club.id, g.id)


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
                       statuses=Lead.Status.choices,
                       # Для подсветки просроченных звонков прямо в списке
                       now=timezone.now(),
                       export_qs=request.GET.urlencode()))


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
def lead_status(request, club, staff, lead_id):
    """Сменить статус заявки прямо в списке.

    Раньше ради одного нажатия надо было открыть заявку, поменять статус и
    вернуться — а их двадцать, и после обзвона статус меняют у каждой.
    """
    lead = get_object_or_404(Lead, id=lead_id, club=club)
    status = request.POST.get("status")
    if status not in dict(Lead.Status.choices):
        return JsonResponse({"ok": False}, status=400) if _wants_json(request) else \
            redirect("fitness_dash:leads", club_id=club.id)

    was = lead.get_status_display()
    lead.status = status
    if not lead.assigned_to_id:
        lead.assigned_to = request.user
    lead.save(update_fields=["status", "assigned_to", "updated_at"])

    LeadNote.objects.create(
        lead=lead, author=request.user,
        text=f"Статус: {was} → {lead.get_status_display()}")
    tgbot.in_background(tg.refresh_lead, lead,
                        f"{lead.get_status_display()} — "
                        f"{request.user.get_full_name() or request.user.username}")

    if _wants_json(request):
        return JsonResponse({"ok": True, "status": lead.status,
                             "label": lead.get_status_display(),
                             "lead": lead.id})
    messages.success(request, f"{lead.name or lead.phone}: {lead.get_status_display()}")
    return redirect(request.POST.get("back")
                    or reverse("fitness_dash:leads", args=[club.id]))


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
    data["export_qs"] = request.GET.urlencode()
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
        elif what == "trainer_toggle":
            tr = Trainer.objects.filter(id=request.POST.get("trainer_id"), club=club).first()
            if tr:
                tr.is_active = not tr.is_active
                tr.save(update_fields=["is_active", "updated_at"])
                messages.success(request, f"«{tr.name}»: "
                                          + ("показан на сайте" if tr.is_active
                                             else "скрыт с сайта"))
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
                       discount_list=club.discounts.all(),
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
            .select_related("trainer", "section", "group", "group__section")
            .annotate(group_size=Count("group__links",
                                       filter=Q(group__links__is_active=True),
                                       distinct=True))
            .order_by("time_from", "id"))
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

    # Отменённые дни одним запросом на неделю
    cancelled = {(c.group_class_id, c.date) for c in
                 ClassDay.objects.filter(group_class__in=rows, date__in=days,
                                         is_cancelled=True)}

    grid = []
    for d in days:
        items = []
        by_hour = {}
        for c in rows:
            if c.weekday != d.weekday():
                continue
            used = taken.get((c.id, d), 0)
            item = {"cls": c, "used": used,
                    "free": max(0, c.capacity - used),
                    "cancelled": (c.id, d) in cancelled}
            items.append(item)
            # Раскладываем по часам: в сетке занятие стоит в строке своего
            # часа, как на доске расписания.
            by_hour.setdefault(c.time_from.hour, []).append(item)
        grid.append({"day": d, "items": items, "by_hour": by_hour,
                     "is_today": d == timezone.localdate()})

    # Часы сетки: от самого раннего занятия до самого позднего, но не уже
    # 8:00–21:00 — иначе пустое расписание выглядит сломанным.
    start_hour, end_hour = 8, 21
    for c in rows:
        start_hour = min(start_hour, c.time_from.hour)
        end_hour = max(end_hour, c.time_from.hour)
    hours = list(range(start_hour, end_hour + 1))

    return render(request, "fitness/dash/classes.html",
                  _ctx(club, staff, grid=grid, day=day, week_start=week_start,
                       hours=hours,
                       today_weekday=timezone.localdate().weekday(),
                       groups=club.training_groups.filter(is_active=True)
                              .select_related("section", "trainer"),
                       prev_week=week_start - timedelta(days=7),
                       next_week=week_start + timedelta(days=7),
                       all_classes=rows,
                       weekdays=GroupClass._meta.get_field("weekday").choices,
                       sections=club.sections.filter(is_active=True),
                       trainers=club.trainers.filter(is_active=True)))


@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
@require_POST
def schedule_add(request, club, staff):
    """Ставит тренировку в расписание из клетки сетки.

    День и час приходят из нажатой клетки, остальное — из панели: либо
    тренировка существующей группы, либо открытое занятие, на которое
    записываются по одному.
    """
    weekday = _int(request.POST.get("weekday"), 0, hi=6)
    hhmm = _time(request.POST.get("time_from"))
    if hhmm is None:
        messages.error(request, "Укажите время начала.")
        return redirect("fitness_dash:classes", club_id=club.id)

    back = reverse("fitness_dash:classes", args=[club.id])
    if request.POST.get("date"):
        back += f"?date={request.POST['date']}"

    raw_group = request.POST.get("group")
    if (raw_group or "").isdigit():
        group = club.training_groups.filter(id=int(raw_group)).first()
        if not group:
            messages.error(request, "Группа не найдена.")
            return redirect(back)
        GroupClass.objects.create(
            club=club, group=group, section=group.section, trainer=group.trainer,
            name=group.title, weekday=weekday, time_from=hhmm,
            duration_min=_int(request.POST.get("duration_min"), 60, lo=15, hi=300),
            capacity=group.capacity,
            room=(request.POST.get("room") or "").strip()[:100],
        )
        messages.success(request, f"«{group.title}» встала в расписание: "
                                  f"{dict(GroupClass._meta.get_field('weekday').choices)[weekday]}"
                                  f", {hhmm:%H:%M}.")
        return redirect(back)

    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Выберите группу или назовите открытое занятие.")
        return redirect(back)

    tr = request.POST.get("trainer_id")
    sec = request.POST.get("section_id")
    GroupClass.objects.create(
        club=club, name=name[:150], weekday=weekday, time_from=hhmm,
        duration_min=_int(request.POST.get("duration_min"), 60, lo=15, hi=300),
        capacity=_int(request.POST.get("capacity"), 12, lo=1, hi=200),
        price=_money(request.POST.get("price"), "0"),
        trainer=Trainer.objects.filter(id=tr, club=club).first() if (tr or "").isdigit() else None,
        section=Section.objects.filter(id=sec, club=club).first() if (sec or "").isdigit() else None,
        room=(request.POST.get("room") or "").strip()[:100],
    )
    messages.success(request, f"«{name}» встало в расписание.")
    return redirect(back)


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
    cls = get_object_or_404(
        GroupClass.objects.select_related("trainer", "section", "group"),
        id=class_id, club=club)
    day = _date(request.GET.get("date"))
    trainer_of = my_trainer(request.user, club)
    rows = list(cls.bookings.filter(date=day).select_related("member")
                .order_by("id"))

    # У занятия группы состав известен заранее: показываем весь список и
    # отмечаем каждого одним нажатием. Записи на эту дату заводить заранее
    # незачем — они появляются в момент отметки.
    roster = []
    if cls.group_id:
        marks = {b.member_id: b for b in rows if b.member_id}
        for link in cls.group.roster():
            roster.append({"member": link.member, "booking": marks.get(link.member_id)})
        rows = [b for b in rows if b.member_id not in marks or not b.member_id]

    # Поиск по имени и карте прямо здесь: выпадающий список из пятисот
    # человек на ресепшене бесполезен, а карту называют чаще имени.
    q = (request.GET.get("q") or "").strip()
    found = []
    if q:
        inside = set()
        if cls.group_id:
            inside = {l.member_id for l in cls.group.links.filter(is_active=True)}
        rows_q = (Member.objects.filter(club=club, is_active=True)
                  .filter(Q(full_name__icontains=q) | Q(phone__icontains=q)
                          | Q(card_id__icontains=q))
                  .order_by("full_name")[:12])
        marks = {b.member_id: b for b in cls.bookings.filter(date=day) if b.member_id}
        for mem in rows_q:
            found.append({"member": mem,
                          "in_group": mem.id in inside,
                          "mark": marks.get(mem.id)})

    state = cls.day_state(day)
    return render(request, "fitness/dash/class_day.html",
                  _ctx(club, staff, cls=cls, day=day, rows=rows, roster=roster,
                       state=state, q=q, found=found,
                       can_cancel=(staff.role != TRAINER
                                   or (trainer_of and cls.trainer_id == trainer_of.id)),
                       came=sum(1 for r in roster
                                if r["booking"] and r["booking"].status == "came"),
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
def class_cancel(request, club, staff, class_id):
    """Отменить тренировку в один конкретный день — или вернуть её.

    Убирать занятие из расписания целиком ради праздника неправильно: оно
    пропадёт и на все следующие недели. Отмена живёт на дате.
    """
    cls = get_object_or_404(GroupClass.objects.select_related("group", "trainer"),
                            id=class_id, club=club)
    day = _date(request.POST.get("date"))
    back = (reverse("fitness_dash:class_day", args=[club.id, cls.id])
            + f"?date={day:%Y-%m-%d}")

    # Тренер отменяет только свою тренировку: чужие отменять ему незачем.
    trainer = my_trainer(request.user, club)
    if staff.role == TRAINER and (not trainer or cls.trainer_id != trainer.id):
        messages.error(request, "Отменить можно только свою тренировку.")
        return redirect(back)

    state, _ = ClassDay.objects.get_or_create(group_class=cls, date=day)
    # В родительском чате логин вида «boss_cn» выглядит мусором: если имя
    # сотрудника не заполнено, строку «отменил» лучше не писать вовсе.
    actor = request.user.get_full_name().strip()

    if request.POST.get("action") == "restore":
        state.is_cancelled = False
        state.reason = ""
        state.save(update_fields=["is_cancelled", "reason", "updated_at"])
        if cls.group_id:
            tgbot.in_background(tg.notify_group, cls.group,
                                tg.class_restored_text(cls, day))
        messages.success(request, "Тренировка возвращена в расписание.")
        return redirect(back)

    state.is_cancelled = True
    state.reason = (request.POST.get("reason") or "").strip()[:200]
    state.cancelled_by = request.user
    state.save(update_fields=["is_cancelled", "reason", "cancelled_by", "updated_at"])

    # Группе сообщаем сразу: отмена, о которой узнали у закрытой двери,
    # хуже самой отмены.
    if cls.group_id:
        tgbot.in_background(tg.notify_group, cls.group,
                            tg.class_cancelled_text(cls, day, state.reason, actor))
        messages.success(request, "Тренировка отменена, группе отправлено сообщение.")
    else:
        tgbot.in_background(tg.notify_gym, club,
                            tg.class_cancelled_text(cls, day, state.reason, actor))
        messages.success(request, "Тренировка отменена.")
    return redirect(back)


@login_required(login_url=LOGIN_URL)
@require()
@require_POST
def class_mark(request, club, staff, class_id):
    """Отметить человека из состава группы: пришёл или нет.

    Запись на дату создаём в момент отметки: заводить её заранее на весь
    состав и на все дни значило бы засорить базу занятиями, которых никто
    не открывал.
    """
    cls = get_object_or_404(GroupClass.objects.select_related("group", "trainer"),
                            id=class_id, club=club)
    day = _date(request.POST.get("date"))
    member = get_object_or_404(Member, id=request.POST.get("member") or 0, club=club)
    action = request.POST.get("action")

    b, _ = ClassBooking.objects.get_or_create(
        group_class=cls, date=day, member=member,
        defaults={"created_by": request.user,
                  "client_name": member.full_name, "phone": member.phone})
    note = _booking_mark(request, club, b, action)

    # Со страницы отмечают подряд десяток человек: отвечаем коротко, чтобы
    # строка обновилась на месте и страница не прыгала после каждого.
    if _wants_json(request):
        return JsonResponse({"ok": True, "status": b.status,
                             "member": member.id, "note": note,
                             "came": _came_count(cls, day)})
    return redirect(request.POST.get("back")
                    or reverse("fitness_dash:class_day", args=[club.id, cls.id])
                    + f"?date={day:%Y-%m-%d}")


@login_required(login_url=LOGIN_URL)
@require()
@require_POST
def class_mark_all(request, club, staff, class_id):
    """Отметить пришедшими весь состав группы.

    Обычно приходят почти все, а не пришли один-двое: быстрее отметить
    всех и снять отметку у отсутствующих, чем жать по человеку.
    """
    cls = get_object_or_404(GroupClass.objects.select_related("group", "trainer"),
                            id=class_id, club=club)
    day = _date(request.POST.get("date"))
    if not cls.group_id:
        messages.error(request, "У этого занятия нет состава — отмечайте по записям.")
        return redirect(request.POST.get("back") or reverse(
            "fitness_dash:class_day", args=[club.id, cls.id]) + f"?date={day:%Y-%m-%d}")

    done = skipped = 0
    for link in cls.group.roster():
        b, created = ClassBooking.objects.get_or_create(
            group_class=cls, date=day, member=link.member,
            defaults={"created_by": request.user,
                      "client_name": link.member.full_name,
                      "phone": link.member.phone})
        # Уже отмеченных не трогаем: иначе «все пришли» затрёт поставленное
        # вручную «не пришёл».
        if not created and b.status != ClassBooking.Status.BOOKED:
            skipped += 1
            continue
        _booking_mark(request, club, b, "came")
        done += 1

    note = (f"Отмечено пришедшими: {done}."
            + (f" Уже были отмечены: {skipped}." if skipped else ""))
    if _wants_json(request):
        return JsonResponse({"ok": True, "done": done, "skipped": skipped,
                             "note": note, "came": _came_count(cls, day)})
    messages.success(request, note)
    return redirect(request.POST.get("back") or reverse(
        "fitness_dash:class_day", args=[club.id, cls.id]) + f"?date={day:%Y-%m-%d}")


def _wants_json(request):
    return (request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or "application/json" in request.headers.get("Accept", ""))


def _came_count(cls, day):
    return cls.bookings.filter(date=day, status=ClassBooking.Status.CAME).count()


def _booking_mark(request, club, b, action):
    """Ставит отметку на записи; «пришёл» списывает посещение."""
    labels = {"came": ClassBooking.Status.CAME,
              "no_show": ClassBooking.Status.NO_SHOW,
              "cancel": ClassBooking.Status.CANCELLED,
              "back": ClassBooking.Status.BOOKED}
    if action not in labels:
        return
    b.status = labels[action]
    b.save(update_fields=["status", "updated_at"])
    # Пришёл на групповое — это посещение зала: списываем, как на входе
    if b.status == ClassBooking.Status.CAME and b.member_id:
        ok, note, _visit = services.check_in(club, b.member,
                                             trainer=b.group_class.trainer,
                                             actor=request.user)
        # Не пропустили — говорим вслух: у человека мог кончиться абонемент,
        # и отметка «пришёл» без предупреждения выглядела бы как списание.
        if not ok:
            # Не пустить человека из-за просроченного абонемента в клубе всё
            # равно не станут: отмечаем приход и вешаем долг, чтобы занятие
            # не растворилось.
            services.owe_visit(club, b.member, group_class=b.group_class,
                               day=b.date, actor=request.user, note=note)
            messages.warning(request, f"{b.member.full_name}: {note} — "
                                      f"занятие записано в долг")
            return f"{note} · в долг"
    return ""


@login_required(login_url=LOGIN_URL)
@require()
@require_POST
def class_booking_status(request, club, staff, booking_id):
    b = get_object_or_404(ClassBooking.objects.select_related("group_class", "member"),
                          id=booking_id, group_class__club=club)
    _booking_mark(request, club, b, request.POST.get("action"))
    # Адрес собираем через reverse: кабинет живёт под /ru/, /ky/ и /en/, а
    # прибитый «/ru/» выкидывал кассира из его языка на каждой отметке.
    return redirect(reverse("fitness_dash:class_day",
                            args=[club.id, b.group_class_id])
                    + f"?date={b.date:%Y-%m-%d}")

# ── Сотрудники клуба ────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
@require_POST
def debt_settle(request, club, staff, debt_id):
    """Закрыть занятие в долг: списать с абонемента или простить."""
    debt = get_object_or_404(OwedVisit.objects.select_related("member"),
                             id=debt_id, club=club, is_settled=False)
    note = (request.POST.get("note") or "").strip()
    raw = request.POST.get("membership")

    ms = None
    if (raw or "").isdigit():
        ms = Membership.objects.filter(id=int(raw), member=debt.member).first()
        if ms is None:
            messages.error(request, "Абонемент не найден.")
            return redirect("fitness_dash:member_detail", club.id, debt.member_id)
    elif not note:
        # Прощаем — причина обязательна: через месяц никто не вспомнит,
        # почему это занятие просто исчезло.
        messages.error(request, "Чтобы закрыть долг без абонемента, "
                                "напишите причину.")
        return redirect("fitness_dash:member_detail", club.id, debt.member_id)

    services.settle_visit_debt(debt, membership=ms, note=note, actor=request.user)
    if ms:
        messages.success(request, f"Занятие от {debt.date:%d.%m} списано с "
                                  f"«{ms.plan.name}». Осталось: {ms.remaining_visits}.")
    else:
        messages.success(request, f"Занятие от {debt.date:%d.%m} закрыто: {note}")
    return redirect("fitness_dash:member_detail", club.id, debt.member_id)


@login_required(login_url=LOGIN_URL)
@require(ADMIN)
@require_POST
def discount_save(request, club, staff):
    """Заводит готовую скидку клуба или выключает её."""
    raw = request.POST.get("off")
    if (raw or "").isdigit():
        club.discounts.filter(id=int(raw)).update(is_active=False)
        messages.success(request, "Скидка убрана из бланка продажи.")
        return redirect("fitness_dash:setup", club_id=club.id)

    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "У скидки должно быть название.")
        return redirect("fitness_dash:setup", club_id=club.id)

    percent = _int(request.POST.get("percent"), 0, hi=100)
    amount = _money(request.POST.get("amount"), "0")
    if not percent and not amount:
        messages.error(request, "Укажите процент или сумму скидки.")
        return redirect("fitness_dash:setup", club_id=club.id)

    DiscountPreset.objects.create(club=club, name=name[:100],
                                  percent=percent if percent else 0,
                                  amount=0 if percent else amount)
    messages.success(request, f"Скидка «{name}» появится в бланке продажи.")
    return redirect("fitness_dash:setup", club_id=club.id)


@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
def debts(request, club, staff):
    """Все занятия в долг по клубу — списком, по людям.

    В карточке клиента долг видно только у него одного, а на входе нужен
    общий список: кто сколько отходил без абонемента.
    """
    show_settled = request.GET.get("show") == "settled"
    rows = (OwedVisit.objects
            .filter(club=club, is_settled=show_settled)
            .select_related("member", "training_group", "settled_from__plan")
            .order_by("member__full_name", "date"))

    # Группируем по человеку: «Орозов Данияр — 3 занятия» читается, а
    # двадцать строк с датами вперемешку по людям — нет.
    people = []
    current = None
    for d in rows:
        if current is None or current["member"].id != d.member_id:
            current = {"member": d.member, "items": []}
            people.append(current)
        current["items"].append(d)

    # Чем закрывать: действующие абонементы этих людей
    plans = {}
    if not show_settled and people:
        for ms in (Membership.objects
                   .filter(member__in=[p["member"].id for p in people], is_active=True)
                   .select_related("plan")):
            plans.setdefault(ms.member_id, []).append(ms)
    for p in people:
        p["plans"] = plans.get(p["member"].id, [])

    return render(request, "fitness/dash/debts.html",
                  _ctx(club, staff, people=people, show_settled=show_settled,
                       total=rows.count(),
                       open_count=OwedVisit.objects.filter(club=club,
                                                           is_settled=False).count()))


@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
@require_POST
def debts_settle_member(request, club, staff, member_id):
    """Закрыть все долги человека одним действием."""
    member = get_object_or_404(Member, id=member_id, club=club)
    rows = list(member.owed_visits.filter(is_settled=False).order_by("date"))
    if not rows:
        messages.info(request, "Долгов нет.")
        return redirect("fitness_dash:debts", club.id)

    note = (request.POST.get("note") or "").strip()
    raw = request.POST.get("membership")
    ms = None
    if (raw or "").isdigit():
        ms = Membership.objects.filter(id=int(raw), member=member).first()
    elif not note:
        messages.error(request, "Чтобы закрыть долги без абонемента, "
                                "напишите причину.")
        return redirect("fitness_dash:debts", club.id)

    closed, left = services.settle_many(rows, membership=ms, note=note,
                                        actor=request.user)
    tail = ""
    if left:
        tail = (f" На абонементе не хватило посещений — осталось не закрыто: "
                f"{len(left)}.")
    messages.success(request, f"{member.full_name}: закрыто занятий — {closed}."
                     + (f" Списано с «{ms.plan.name}», осталось "
                        f"{ms.remaining_visits}." if ms else "") + tail)
    return redirect("fitness_dash:debts", club.id)


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

    # Человека могли увольнять: тогда аккаунт закрыли, и доступ к клубу сам
    # по себе вход не вернёт. Принимаем обратно — открываем и вход.
    reopened = False
    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])
        reopened = True

    if ClubStaff.objects.filter(user=user, club=club).exists():
        link = ClubStaff.objects.get(user=user, club=club)
        link.role = role
        link.is_active = True
        link.save(update_fields=["role", "is_active", "updated_at"])
        messages.success(request, f"{login}: доступ обновлён — {link.get_role_display()}"
                                  + (" · вход снова открыт" if reopened else ""))
    else:
        ClubStaff.objects.create(user=user, club=club, role=role)
        messages.success(
            request,
            f"{login} добавлен как «{dict(ClubStaff.Role.choices)[role]}»"
            + (" · логин создан" if created else "")
            + (" · вход снова открыт" if reopened else ""))

    # Тренеру нужна карточка, иначе он войдёт и не увидит ни своих записей,
    # ни своих групп: роль дали, а привязать к карточке забыли. Поэтому
    # связываем сами — с выбранной карточкой, с подходящей по имени, а если
    # никакой нет, заводим новую.
    if role == TRAINER:
        raw = request.POST.get("trainer_id")
        name = ((request.POST.get("full_name") or "").strip()
                or user.get_full_name() or login)
        card = None
        if (raw or "").isdigit():
            card = Trainer.objects.filter(id=int(raw), club=club).first()
        if card is None:
            card = Trainer.objects.filter(club=club, user=user).first()
        if card is None:
            # Карточка этого человека могла остаться с прошлого раза — после
            # увольнения её отвязывают от аккаунта и прячут. Находим по имени
            # и возвращаем, чтобы не плодить второго «Руслана».
            card = Trainer.objects.filter(club=club, user__isnull=True,
                                          name__iexact=name).first()
        if card:
            card.user = user
            card.is_active = True
            card.save(update_fields=["user", "is_active", "updated_at"])
            messages.info(request, f"Привязан к карточке тренера «{card.name}»")
        else:
            card = Trainer.objects.create(
                club=club, user=user, name=name[:150],
                phone=(request.POST.get("phone") or "").strip()[:50])
            messages.info(request, f"Создана карточка тренера «{card.name}»")
    return redirect("fitness_dash:setup", club_id=club.id)


def _remove_staff(club, link):
    """Убирает сотрудника из клуба, сохраняя всё, что он сделал.

    Сам аккаунт не удаляем: к нему привязаны проданные абонементы,
    принятые платежи и отмеченные посещения — удаление обнулило бы
    авторство во всей истории. Вместо этого забираем доступ, а если
    человеку больше некуда входить, закрываем и вход на сайт.
    """
    user = link.user
    role = link.get_role_display()
    link.delete()

    # Карточка тренера остаётся с записями и историей, но с сайта уходит и
    # от аккаунта отвязывается: иначе уволенный тренер по-прежнему виден
    # клиентам и может войти в чужое расписание.
    hidden = Trainer.objects.filter(club=club, user=user).update(
        user=None, is_active=False)

    tail = ""
    others = ClubStaff.objects.filter(user=user, is_active=True).exists()
    if not others and not (user.is_superuser or user.is_staff):
        user.is_active = False
        user.save(update_fields=["is_active"])
        tail = " · вход на сайт закрыт"
    elif others:
        tail = " · остался доступ в другие клубы"

    note = f"{user.username} ({role}) убран из клуба{tail}"
    if hidden:
        note += " · карточка тренера скрыта с сайта, записи сохранены"
    return note + ". Платежи, посещения и абонементы остались на месте."

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
        messages.success(request, _remove_staff(club, link))
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

# ── Выгрузка в Excel ────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
def reports_export(request, club, staff):
    """Полный отчёт за период: сводка, платежи, посещения, абонементы, заявки."""
    from . import export

    start = _date(request.GET.get("from"), timezone.localdate().replace(day=1))
    end = _date(request.GET.get("to"))
    return export.report_response(club, start, end,
                                  with_money=can_see_money(staff),
                                  with_profit=can_see_profit(staff))


@login_required(login_url=LOGIN_URL)
@require()
def members_export(request, club, staff):
    """Клиентская база — с теми же фильтрами, что на странице."""
    from . import export

    rows = _members_queryset(request, club, staff)
    return export.members_response(club, rows, with_money=can_see_money(staff))


@login_required(login_url=LOGIN_URL)
@require(ADMIN, CASHIER)
def leads_export(request, club, staff):
    from . import export

    status = (request.GET.get("status") or "").strip()
    rows = Lead.objects.filter(club=club).select_related("section", "trainer",
                                                         "assigned_to", "member")
    if status:
        rows = rows.filter(status=status)
    return export.leads_response(club, rows.order_by("id"))

