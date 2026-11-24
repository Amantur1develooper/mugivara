# -*- coding: utf-8 -*-
"""Что происходит в клубе: продажи, проход в зал, долги, расходы.

Вся логика в одном месте, потому что её зовут из разных углов: со
страницы кассы, из карточки клиента, из заявки. Если держать её во
вьюхах, они разойдутся — где-то забудут списать посещение, где-то не
отправят в Telegram.
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from integrations import tgbot

from . import tg
from .models import Expense, Member, Membership, Payment, Visit

log = logging.getLogger(__name__)


def _notify(club, text):
    """Сообщение в чат зала — в фоне, чтобы касса не ждала Telegram."""
    tgbot.in_background(tg.notify_gym, club, text)


# ── Продажа абонемента ──────────────────────────────────────────────────────

@transaction.atomic
def sell_membership(club, member, plan, *, price=None, discount=0, paid=None,
                    trainer=None, start_today=False, method="cash", actor=None,
                    discount_note="", section=None, start_date=None, used_visits=0):
    """Продаёт абонемент.

    По умолчанию абонемент не активируется: срок пойдёт с первого
    посещения. start_today=True — если клиент просит начать сразу.

    start_date — срок идёт с этого дня, в том числе прошедшего. Так
    оформляют задним числом: человек ходит неделю, а абонемент пробивают
    сегодня. Тогда и дни уже идут, и used_visits списывает те посещения,
    которые он успел отходить, — иначе кассир вычитала их вручную.
    """
    price = Decimal(str(price if price is not None else plan.price))
    discount = Decimal(str(discount or 0))
    to_pay = max(Decimal("0"), price - discount)
    paid = Decimal(str(paid if paid is not None else to_pay))
    debt = max(Decimal("0"), to_pay - paid)

    ms = Membership.objects.create(
        member=member, plan=plan, trainer=trainer,
        # Направление: что выбрали при продаже, иначе из тарифа — чаще
        # всего тариф и заведён под направление.
        section=section or plan.section,
        remaining_visits=plan.visits_number or 0,
        price=price, discount_amount=discount,
        discount_note=(discount_note or "")[:100],
        paid_amount=paid, debt_amount=debt,
        created_by=actor,
    )
    if start_date:
        ms.start_date = start_date
        ms.end_date = start_date + timedelta(days=plan.validity_days or 0)
        ms.save(update_fields=["start_date", "end_date", "updated_at"])
    elif start_today:
        ms.activate()

    # Посещения за уже отхоженные дни. Больше, чем есть в тарифе, списать
    # нельзя: остаток ушёл бы в минус и абонемент выглядел бы испорченным.
    used = max(0, int(used_visits or 0))
    if used and plan.visits_number:
        used = min(used, ms.remaining_visits)
        ms.remaining_visits -= used
        ms.save(update_fields=["remaining_visits", "updated_at"])
    else:
        used = 0

    if paid > 0:
        Payment.objects.create(
            club=club, member=member, membership=ms, amount=paid,
            method=method, kind=Payment.Kind.MEMBERSHIP,
            note=plan.name, created_by=actor,
        )

    def after():
        lines = ["💳 ПРОДАЖА АБОНЕМЕНТА",
                 f"👤 {member.full_name}",
                 f"🎫 {plan.name} — {tg._money(price)}"]
        if discount:
            lines.append(f"🏷 Скидка: {tg._money(discount)}")
        lines.append(f"💰 Оплачено: {tg._money(paid)}")
        if debt:
            lines.append(f"⚠️ Долг: {tg._money(debt)}")
        lines.append("📅 Начало: " +
                     (f"{ms.start_date:%d.%m.%Y}" if ms.activated
                      else "с первого посещения"))
        # Задним числом — отдельной строкой: в чате зала это видно сразу,
        # и вопросов «почему срок уже идёт» не возникает.
        if ms.activated and ms.start_date < timezone.localdate():
            lines.append(f"↩️ Оформлен задним числом, до {ms.end_date:%d.%m.%Y}")
        if used:
            lines.append(f"➖ Списано за отхоженные дни: {used} "
                         f"(осталось {ms.remaining_visits})")
        if trainer:
            lines.append(f"🧑‍🏫 Тренер: {trainer.name}")
        _notify(club, "\n".join(lines))

    transaction.on_commit(after)
    return ms


# ── Проход в зал ────────────────────────────────────────────────────────────

@transaction.atomic
def check_in(club, member, *, trainer=None, actor=None, section=None):
    """Пропускает клиента. Возвращает (ok, сообщение, visit).

    Здесь же случается то, из-за чего всё и затевалось: если абонемент ещё
    не начат, первое посещение его активирует и срок пойдёт с сегодня.

    section — направление тренировки, если приход отмечают в группе:
    списываем с абонемента этого направления, а не с первого попавшегося.
    """
    today = timezone.localdate()
    ms = member.active_membership(section=section)

    if ms is None:
        # Причину называем точно: «нет абонемента» и «срок вышел» — разные
        # разговоры на ресепшене.
        last = member.memberships.order_by("-id").first()
        if last is None:
            reason = "Нет абонемента"
        elif last.is_frozen:
            reason = "Абонемент заморожен"
        elif last.plan.visits_number and last.remaining_visits <= 0:
            reason = "Посещения закончились"
        elif last.end_date and last.end_date < today:
            reason = f"Срок вышел {last.end_date:%d.%m.%Y}"
        else:
            reason = "Нет действующего абонемента"
        # Самый частый случай с направлениями: абонемент есть и он живой,
        # но на другое направление. Так и говорим, иначе кассир смотрит на
        # действующий абонемент и не понимает, почему не пускает.
        if section is not None and member.active_membership() is not None:
            reason = f"Абонемент другого направления, не «{section.name}»"
        visit = Visit.objects.create(club=club, member=member, success=False,
                                     reason=reason, created_by=actor)
        transaction.on_commit(lambda: _notify(club, tg.visit_text(visit)))
        return False, reason, visit

    activated_now = ms.activate(today) if not ms.activated else False
    if ms.plan.visits_number:
        ms.remaining_visits = max(0, ms.remaining_visits - 1)
        ms.save(update_fields=["remaining_visits", "updated_at"])

    visit = Visit.objects.create(club=club, member=member, membership=ms,
                                 trainer=trainer, success=True, created_by=actor)

    def after():
        text = tg.visit_text(visit)
        if activated_now:
            text += f"\n🟢 Абонемент активирован, действует до {ms.end_date:%d.%m.%Y}"
        _notify(club, text)

    transaction.on_commit(after)
    msg = "Проходите"
    if activated_now:
        msg = f"Абонемент активирован до {ms.end_date:%d.%m.%Y}"
    return True, msg, visit


# ── Долги и заморозка ───────────────────────────────────────────────────────

@transaction.atomic
def pay_debt(club, membership, amount, *, method="cash", actor=None):
    amount = Decimal(str(amount or 0))
    if amount <= 0:
        return None
    pay = min(amount, membership.debt_amount)
    membership.debt_amount -= pay
    membership.paid_amount += pay
    membership.save(update_fields=["debt_amount", "paid_amount", "updated_at"])

    payment = Payment.objects.create(
        club=club, member=membership.member, membership=membership,
        amount=pay, method=method, kind=Payment.Kind.DEBT,
        note=f"Долг по «{membership.plan.name}»", created_by=actor,
    )
    transaction.on_commit(lambda: _notify(club, tg.payment_text(payment)))
    return payment


@transaction.atomic
def freeze(membership, days, *, actor=None):
    """Замораживает абонемент: срок сдвигается на эти дни."""
    days = max(1, int(days or 0))
    membership.is_frozen = True
    membership.freeze_start = timezone.localdate()
    membership.freeze_days = days
    if membership.end_date:
        membership.end_date = membership.end_date + timedelta(days=days)
    membership.save(update_fields=["is_frozen", "freeze_start", "freeze_days",
                                   "end_date", "updated_at"])
    return membership


@transaction.atomic
def unfreeze(membership, *, actor=None):
    """Снимает заморозку. Неиспользованные дни возвращаются клубу."""
    if not membership.is_frozen:
        return membership
    used = 0
    if membership.freeze_start:
        used = (timezone.localdate() - membership.freeze_start).days
    unused = max(0, (membership.freeze_days or 0) - max(0, used))
    if membership.end_date and unused:
        membership.end_date = membership.end_date - timedelta(days=unused)
    membership.is_frozen = False
    membership.freeze_days = 0
    membership.freeze_start = None
    membership.save(update_fields=["is_frozen", "freeze_days", "freeze_start",
                                   "end_date", "updated_at"])
    return membership


@transaction.atomic
def edit_membership(ms, data, *, actor=None):
    """Правит уже проданный абонемент. Возвращает список изменений словами.

    Продают абонементы на ходу и ошибаются: не тот тариф, не то
    направление, не та дата окончания, посещение списалось зря. Раньше
    такое правили только через админку, то есть никак.

    Оплату тут не трогают. Выручка в отчётах считается по кассе
    (Payment), и ручная правка «оплачено» разошлась бы с ней: деньги
    принимают кнопкой «Принять долг», она и проводит платёж. Долг же
    пересчитывается сам — из цены, скидки и того, что уже оплачено.

    В data кладут только те поля, которые меняют; остальных ключей нет.
    """
    def money(x):
        return f"{Decimal(str(x or 0)):.0f}"

    changes = []
    fields = []

    if "section" in data and data["section"] != ms.section:
        was = ms.section.name if ms.section else "без направления"
        now = data["section"].name if data["section"] else "без направления"
        ms.section = data["section"]
        fields.append("section")
        changes.append(f"направление: {was} → {now}")

    if "trainer" in data and data["trainer"] != ms.trainer:
        was = ms.trainer.name if ms.trainer else "без тренера"
        now = data["trainer"].name if data["trainer"] else "без тренера"
        ms.trainer = data["trainer"]
        fields.append("trainer")
        changes.append(f"тренер: {was} → {now}")

    # Безлимитному тарифу остаток посещений ни на что не влияет, и
    # показывать его там незачем — значит и править нечего.
    if "remaining_visits" in data and ms.plan.visits_number:
        want = max(0, int(data["remaining_visits"] or 0))
        if want != ms.remaining_visits:
            changes.append(f"осталось посещений: {ms.remaining_visits} → {want}")
            ms.remaining_visits = want
            fields.append("remaining_visits")

    if "start_date" in data and data["start_date"] != ms.start_date:
        was = f"{ms.start_date:%d.%m.%Y}" if ms.start_date else "с первого посещения"
        now = f"{data['start_date']:%d.%m.%Y}" if data["start_date"] else "с первого посещения"
        ms.start_date = data["start_date"]
        fields.append("start_date")
        changes.append(f"начало: {was} → {now}")

    if "end_date" in data and data["end_date"] != ms.end_date:
        was = f"{ms.end_date:%d.%m.%Y}" if ms.end_date else "без срока"
        now = f"{data['end_date']:%d.%m.%Y}" if data["end_date"] else "без срока"
        ms.end_date = data["end_date"]
        fields.append("end_date")
        changes.append(f"действует до: {was} → {now}")

    # Дату начала поставили, а до какого числа — не сказали: считаем по
    # сроку тарифа, иначе абонемент остался бы бессрочным по недосмотру.
    if ms.start_date and not ms.end_date and ms.plan.validity_days:
        ms.end_date = ms.start_date + timedelta(days=ms.plan.validity_days)
        if "end_date" not in fields:
            fields.append("end_date")
        changes.append(f"действует до: {ms.end_date:%d.%m.%Y} (по сроку тарифа)")

    for key, field, label in (("price", "price", "цена"),
                              ("discount", "discount_amount", "скидка")):
        if key in data:
            want = Decimal(str(data[key] or 0))
            if want != getattr(ms, field):
                changes.append(f"{label}: {money(getattr(ms, field))} → {money(want)} сом")
                setattr(ms, field, want)
                fields.append(field)

    if "discount_note" in data:
        want = (data["discount_note"] or "")[:100]
        if want != ms.discount_note:
            ms.discount_note = want
            fields.append("discount_note")
            changes.append(f"название скидки: {want or '—'}")

    if "is_active" in data and bool(data["is_active"]) != ms.is_active:
        ms.is_active = bool(data["is_active"])
        fields.append("is_active")
        changes.append("возвращён в работу" if ms.is_active else "закрыт")

    # Долг не вводят руками: он всегда равен недоплате по текущим условиям.
    debt = max(Decimal("0"), ms.price - ms.discount_amount - ms.paid_amount)
    if debt != ms.debt_amount:
        changes.append(f"долг: {money(ms.debt_amount)} → {money(debt)} сом")
        ms.debt_amount = debt
        fields.append("debt_amount")

    if not fields:
        return []

    fields.append("updated_at")
    ms.save(update_fields=fields)

    who = getattr(actor, "get_full_name", lambda: "")() or getattr(actor, "username", "")
    text = ("✏️ ПРАВКА АБОНЕМЕНТА\n"
            f"👤 {ms.member.full_name}\n"
            f"🎫 {ms.plan.name}\n"
            + "\n".join(f"• {c}" for c in changes)
            + (f"\n👟 {who}" if who else ""))
    transaction.on_commit(lambda: _notify(ms.member.club, text))
    return changes


# ── Расходы ─────────────────────────────────────────────────────────────────

@transaction.atomic
def add_expense(club, category, amount, *, note="", spent_on=None, actor=None):
    exp = Expense.objects.create(
        club=club, category=category, amount=Decimal(str(amount or 0)),
        note=note, spent_on=spent_on or timezone.localdate(), created_by=actor,
    )
    transaction.on_commit(lambda: _notify(club, tg.expense_text(exp)))
    return exp

# ── Занятия в долг ──────────────────────────────────────────────────────────

def owe_visit(club, member, *, group_class=None, day=None, actor=None, note=""):
    """Записывает занятие в долг: пришёл, а абонемент не пускает.

    Причину определяем сами: заморожен — одно дело, кончился — другое.
    Повторная отметка того же занятия долг не удваивает.
    """
    from .models import Membership, OwedVisit

    day = day or timezone.localdate()
    ms = member.active_membership()
    frozen = bool(Membership.objects.filter(member=member, is_active=True,
                                            is_frozen=True).exists())
    reason = (OwedVisit.Reason.FROZEN if (frozen and not ms)
              or (ms and ms.is_frozen) else OwedVisit.Reason.NO_PASS)

    debt, created = OwedVisit.objects.get_or_create(
        member=member, group_class=group_class, date=day,
        defaults={"club": club, "reason": reason, "note": note,
                  "training_group": group_class.group if group_class and
                                    group_class.group_id else None,
                  "created_by": actor if getattr(actor, "pk", None) else None})
    return debt, created


def settle_visit_debt(debt, *, membership=None, note="", actor=None):
    """Закрывает долг: списывает занятие с абонемента или прощает.

    Списываем ровно одно посещение — то самое, что человек уже отходил.
    Без абонемента долг можно закрыть «просто так», но причина
    обязательна: иначе через месяц никто не вспомнит, почему простили.
    """
    from django.db import transaction as db_tx

    with db_tx.atomic():
        if membership is not None:
            if membership.plan.visits_number and membership.remaining_visits > 0:
                membership.remaining_visits -= 1
                membership.save(update_fields=["remaining_visits", "updated_at"])
            debt.settled_from = membership
        debt.is_settled = True
        debt.settled_on = timezone.localdate()
        debt.settle_note = (note or "").strip()[:200]
        debt.settled_by = actor if getattr(actor, "pk", None) else None
        debt.save(update_fields=["is_settled", "settled_on", "settled_from",
                                 "settle_note", "settled_by", "updated_at"])
    return debt

def settle_many(debts, *, membership=None, note="", actor=None):
    """Закрывает несколько долгов разом.

    Если абонемент с посещениями, а долгов больше, чем на нём осталось,
    закрываем столько, сколько абонемент покрывает, и возвращаем остаток:
    молча списать в минус хуже, чем сказать «хватило на два из трёх».
    """
    closed = 0
    left_over = []
    for debt in debts:
        if membership is not None and membership.plan.visits_number:
            membership.refresh_from_db(fields=["remaining_visits"])
            if membership.remaining_visits <= 0:
                left_over.append(debt)
                continue
        settle_visit_debt(debt, membership=membership, note=note, actor=actor)
        closed += 1
    return closed, left_over

