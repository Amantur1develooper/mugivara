# -*- coding: utf-8 -*-
"""Выгрузка данных клуба в Excel.

Отчёт на экране отвечает на вопрос «как дела», а выгрузка нужна для
другого: свести с кассой, отдать бухгалтеру, прозвонить базу. Поэтому
листов несколько и в них сырые строки, а не только итоги.

Что попадает в файл, зависит от роли: расходы и прибыль видит только
администратор — у кассира этих листов в файле просто нет.
"""
from io import BytesIO

from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone

ACCENT = "FF4D1C"


def _book():
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    return wb


def _head(ws, names, row=1, widths=None):
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    thin = Side(style="thin", color="DDDDDD")
    for col, name in enumerate(names, start=1):
        c = ws.cell(row=row, column=col, value=name)
        c.fill = PatternFill("solid", fgColor=ACCENT)
        c.font = Font(bold=True, color="FFFFFF", size=11)
        c.border = Border(left=thin, right=thin, top=thin, bottom=thin)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    from openpyxl.utils import get_column_letter
    for col, w in enumerate(widths or [], start=1):
        ws.column_dimensions[get_column_letter(col)].width = w
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def _rows(ws, rows, start=2, money_cols=()):
    from openpyxl.styles import Border, Side
    thin = Side(style="thin", color="EEEEEE")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for i, line in enumerate(rows, start=start):
        for col, val in enumerate(line, start=1):
            c = ws.cell(row=i, column=col, value=val)
            c.border = border
            if col in money_cols:
                c.number_format = "#,##0"
    return start + len(rows)


def _answer(wb, name):
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{name}"'
    return resp


def _local(dt):
    return timezone.localtime(dt).strftime("%d.%m.%Y %H:%M") if dt else ""


# ── Полный отчёт за период ──────────────────────────────────────────────────

def report_workbook(club, start, end, *, with_money=True, with_profit=False):
    from fitness.models import (ClassBooking, Expense, Lead, Member, Membership,
                                Payment, TrainerBooking, Visit)
    from openpyxl.styles import Font

    wb = _book()

    pays = Payment.objects.filter(club=club, created_at__date__gte=start,
                                  created_at__date__lte=end)
    visits = Visit.objects.filter(club=club, visit_time__date__gte=start,
                                  visit_time__date__lte=end)
    sold = Membership.objects.filter(member__club=club, created_at__date__gte=start,
                                     created_at__date__lte=end)
    leads = Lead.objects.filter(club=club, created_at__date__gte=start,
                                created_at__date__lte=end)
    expenses = Expense.objects.filter(club=club, spent_on__gte=start, spent_on__lte=end)

    income = pays.aggregate(s=Sum("amount"))["s"] or 0
    spent = expenses.aggregate(s=Sum("amount"))["s"] or 0
    debts = (Membership.objects.filter(member__club=club, debt_amount__gt=0)
             .aggregate(s=Sum("debt_amount"))["s"] or 0)

    # ── Сводка ──
    ws = wb.create_sheet("Сводка")
    ws["A1"] = club.name
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Период: {start:%d.%m.%Y} — {end:%d.%m.%Y}"
    ws["A3"] = f"Файл сформирован: {timezone.localtime():%d.%m.%Y %H:%M}"

    summary = [
        ("Посещений", visits.filter(success=True).count()),
        ("Отказов на входе", visits.filter(success=False).count()),
        ("Продано абонементов", sold.count()),
        ("Клиентов всего", Member.objects.filter(club=club).count()),
        ("Активных клиентов", Member.objects.filter(club=club, is_active=True).count()),
        ("Заявок", leads.count()),
        ("Из них купили", leads.filter(status=Lead.Status.SOLD).count()),
    ]
    if with_money:
        summary.insert(0, ("Поступило, сом", int(income)))
        summary.append(("Долги клиентов, сом", int(debts)))
    if with_profit:
        summary.append(("Расходы, сом", int(spent)))
        summary.append(("Осталось, сом", int(income - spent)))

    _head(ws, ["Показатель", "Значение"], row=5, widths=[34, 18])
    _rows(ws, summary, start=6, money_cols=(2,))

    # ── Платежи ──
    if with_money:
        ws = wb.create_sheet("Платежи")
        _head(ws, ["Дата", "Клиент", "За что", "Способ", "Сумма, сом",
                   "Абонемент", "Примечание", "Кто принял"],
              widths=[18, 26, 16, 12, 13, 24, 28, 18])
        _rows(ws, [
            (_local(p.created_at),
             p.member.full_name if p.member_id else "",
             p.get_kind_display(), p.get_method_display(), int(p.amount),
             p.membership.plan.name if p.membership_id else "",
             p.note,
             (p.created_by.get_full_name() or p.created_by.username) if p.created_by_id else "")
            for p in pays.select_related("member", "membership__plan", "created_by")
                         .order_by("id")
        ], money_cols=(5,))

    # ── Посещения ──
    ws = wb.create_sheet("Посещения")
    _head(ws, ["Дата и время", "Клиент", "Телефон", "Пропущен", "Абонемент",
               "Осталось", "Тренер", "Причина отказа"],
          widths=[18, 26, 16, 11, 24, 11, 18, 26])
    _rows(ws, [
        (_local(v.visit_time),
         v.member.full_name if v.member_id else "",
         v.member.phone if v.member_id else "",
         "да" if v.success else "нет",
         v.membership.plan.name if v.membership_id else "",
         v.membership.remaining_visits if v.membership_id else "",
         v.trainer.name if v.trainer_id else "",
         v.reason)
        for v in visits.select_related("member", "membership__plan", "trainer")
                       .order_by("visit_time")
    ])

    # ── Абонементы ──
    ws = wb.create_sheet("Абонементы")
    _head(ws, ["Клиент", "Телефон", "Абонемент", "Куплен", "Начало", "Окончание",
               "Осталось", "Цена", "Оплачено", "Долг", "Состояние", "Тренер"],
          widths=[26, 16, 24, 13, 13, 13, 11, 11, 12, 11, 16, 18])
    _rows(ws, [
        (ms.member.full_name, ms.member.phone, ms.plan.name,
         ms.purchase_date.strftime("%d.%m.%Y") if ms.purchase_date else "",
         ms.start_date.strftime("%d.%m.%Y") if ms.start_date else "не начат",
         ms.end_date.strftime("%d.%m.%Y") if ms.end_date else "",
         ms.remaining_visits if ms.plan.visits_number else "безлимит",
         int(ms.price), int(ms.paid_amount), int(ms.debt_amount),
         ("закрыт" if not ms.is_active else
          "заморожен" if ms.is_frozen else
          "не начат" if not ms.activated else "активен"),
         ms.trainer.name if ms.trainer_id else "")
        for ms in sold.select_related("member", "plan", "trainer").order_by("id")
    ], money_cols=(8, 9, 10))

    # ── Заявки ──
    ws = wb.create_sheet("Заявки")
    _head(ws, ["Создана", "Имя", "Телефон", "Источник", "Статус", "Секция",
               "Тренер", "Связаться", "Ответственный", "Комментарий"],
          widths=[18, 22, 16, 14, 14, 20, 18, 18, 20, 34])
    _rows(ws, [
        (_local(l.created_at), l.name, l.phone, l.get_source_display(),
         l.get_status_display(),
         l.section.name if l.section_id else "",
         l.trainer.name if l.trainer_id else "",
         _local(l.next_contact_at),
         (l.assigned_to.get_full_name() or l.assigned_to.username) if l.assigned_to_id else "",
         l.comment)
        for l in leads.select_related("section", "trainer", "assigned_to").order_by("id")
    ])

    # ── Тренеры ──
    # Состав групп: кто в какой группе и по каким дням ходит. Это первое,
    # что спрашивают, когда тренер уходит и группу надо передать.
    ws = wb.create_sheet("Группы")
    _head(ws, ["Группа", "Секция", "Тренер", "Людей", "Мест", "Расписание",
               "Состав", "Пометка"],
          widths=[26, 18, 18, 9, 8, 26, 50, 24])
    WD = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    grows = []
    for g in (club.training_groups.filter(is_active=True)
              .select_related("section", "trainer")
              .prefetch_related("slots", "links__member")):
        roster = [l.member.full_name for l in g.links.all() if l.is_active]
        plan = [f"{WD[s.weekday]} {s.time_from:%H:%M}"
                for s in sorted(g.slots.all(), key=lambda x: (x.weekday, x.time_from))
                if s.is_active]
        grows.append((g.title, g.section.name if g.section_id else "",
                      g.trainer.name if g.trainer_id else "не назначен",
                      len(roster), g.capacity, ", ".join(plan),
                      ", ".join(sorted(roster)), g.note))
    _rows(ws, grows)

    ws = wb.create_sheet("Тренеры")
    _head(ws, ["Тренер", "Записей", "Пришли", "Не пришли", "Дошли, %",
               "Групповых занятий", "Цена тренировки"],
          widths=[24, 12, 11, 13, 12, 18, 17])
    load = []
    for t in club.trainers.all():
        p = TrainerBooking.objects.filter(trainer=t, date__gte=start, date__lte=end)
        g = ClassBooking.objects.filter(group_class__trainer=t, date__gte=start,
                                        date__lte=end)
        booked = (p.exclude(status=TrainerBooking.Status.CANCELLED).count()
                  + g.exclude(status=ClassBooking.Status.CANCELLED).count())
        came = (p.filter(status=TrainerBooking.Status.CAME).count()
                + g.filter(status=ClassBooking.Status.CAME).count())
        noshow = (p.filter(status=TrainerBooking.Status.NO_SHOW).count()
                  + g.filter(status=ClassBooking.Status.NO_SHOW).count())
        load.append((t.name, booked, came, noshow,
                     round(came / booked * 100) if booked else 0,
                     t.classes.filter(is_active=True).count(),
                     int(t.price_per_session)))
    load.sort(key=lambda r: -r[2])
    _rows(ws, load, money_cols=(7,))

    # ── Расходы ──
    if with_profit:
        ws = wb.create_sheet("Расходы")
        _head(ws, ["Дата", "Категория", "Сумма, сом", "На что", "Кто записал"],
              widths=[14, 20, 13, 38, 20])
        last = _rows(ws, [
            (e.spent_on.strftime("%d.%m.%Y"), e.get_category_display(), int(e.amount),
             e.note,
             (e.created_by.get_full_name() or e.created_by.username) if e.created_by_id else "")
            for e in expenses.select_related("created_by").order_by("spent_on", "id")
        ], money_cols=(3,))
        ws.cell(row=last, column=2, value="ИТОГО").font = Font(bold=True)
        total = ws.cell(row=last, column=3, value=int(spent))
        total.font, total.number_format = Font(bold=True), "#,##0"

    return wb


def report_response(club, start, end, *, with_money=True, with_profit=False):
    wb = report_workbook(club, start, end, with_money=with_money, with_profit=with_profit)
    return _answer(wb, f"klub_{club.id}_{start:%Y%m%d}_{end:%Y%m%d}.xlsx")


# ── Клиентская база ─────────────────────────────────────────────────────────

def members_response(club, members, *, with_money=True):
    """База клиентов — её выгружают, чтобы прозвонить или свести долги."""
    wb = _book()
    ws = wb.create_sheet("Клиенты")
    cols = ["ФИО", "Телефон", "Карта", "Дата рождения", "Группы", "Абонемент",
            "Осталось", "Действует до", "Состояние", "Последнее посещение",
            "Всего посещений"]
    widths = [28, 16, 14, 14, 26, 24, 11, 14, 16, 20, 16]
    if with_money:
        cols += ["Долг, сом"]
        widths += [12]
    cols += ["Примечание"]
    widths += [34]
    _head(ws, cols, widths=widths)

    rows = []
    for m in members:
        ms = m.active_membership()
        last = m.visits.filter(success=True).order_by("-visit_time").first()
        line = [
            m.full_name, m.phone, m.card_id,
            m.birth_date.strftime("%d.%m.%Y") if m.birth_date else "",
            ", ".join(sorted(l.group.title for l in m.group_links.all()
                             if l.is_active)),
            ms.plan.name if ms else "",
            (ms.remaining_visits if ms and ms.plan.visits_number else
             ("безлимит" if ms else "")),
            ms.end_date.strftime("%d.%m.%Y") if (ms and ms.end_date) else "",
            ("не начат" if ms and not ms.activated else
             "активен" if ms else "без абонемента"),
            _local(last.visit_time) if last else "ни разу",
            m.visits.filter(success=True).count(),
        ]
        if with_money:
            line.append(int(sum(x.debt_amount for x in m.memberships.all())))
        line.append(m.notes)
        rows.append(line)
    _rows(ws, rows, money_cols=((12,) if with_money else ()))
    return _answer(wb, f"klienty_{club.id}_{timezone.localdate():%Y%m%d}.xlsx")


# ── Заявки ──────────────────────────────────────────────────────────────────

def leads_response(club, leads):
    wb = _book()
    ws = wb.create_sheet("Заявки")
    _head(ws, ["Создана", "Имя", "Телефон", "Источник", "Статус", "Секция",
               "Тренер", "Связаться", "Ответственный", "Стал клиентом", "Комментарий"],
          widths=[18, 22, 16, 14, 14, 20, 18, 18, 20, 24, 36])
    _rows(ws, [
        (_local(l.created_at), l.name, l.phone, l.get_source_display(),
         l.get_status_display(),
         l.section.name if l.section_id else "",
         l.trainer.name if l.trainer_id else "",
         _local(l.next_contact_at),
         (l.assigned_to.get_full_name() or l.assigned_to.username) if l.assigned_to_id else "",
         l.member.full_name if l.member_id else "",
         l.comment)
        for l in leads
    ])

    # Воронка рядом: по ней видно, где теряются люди
    ws2 = wb.create_sheet("Воронка")
    _head(ws2, ["Статус", "Заявок"], widths=[24, 12])
    from fitness.models import Lead
    counts = {r["status"]: r["n"] for r in
              Lead.objects.filter(club=club).values("status").annotate(n=Count("id"))}
    _rows(ws2, [(label, counts.get(value, 0)) for value, label in Lead.Status.choices])
    return _answer(wb, f"zayavki_{club.id}_{timezone.localdate():%Y%m%d}.xlsx")
