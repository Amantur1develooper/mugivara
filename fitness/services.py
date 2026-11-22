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
                    trainer=None, start_today=False, method="cash", actor=None):
    """Продаёт абонемент.

    По умолчанию абонемент не активируется: срок пойдёт с первого
    посещения. start_today=True — если клиент просит начать сразу.
    """
    price = Decimal(str(price if price is not None else plan.price))
    discount = Decimal(str(discount or 0))
    to_pay = max(Decimal("0"), price - discount)
    paid = Decimal(str(paid if paid is not None else to_pay))
    debt = max(Decimal("0"), to_pay - paid)

    ms = Membership.objects.create(
        member=member, plan=plan, trainer=trainer,
        remaining_visits=plan.visits_number or 0,
        price=price, discount_amount=discount,
        paid_amount=paid, debt_amount=debt,
        created_by=actor,
    )
    if start_today:
        ms.activate()

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
        if trainer:
            lines.append(f"🧑‍🏫 Тренер: {trainer.name}")
        _notify(club, "\n".join(lines))

    transaction.on_commit(after)
    return ms


# ── Проход в зал ────────────────────────────────────────────────────────────

@transaction.atomic
def check_in(club, member, *, trainer=None, actor=None):
    """Пропускает клиента. Возвращает (ok, сообщение, visit).

    Здесь же случается то, из-за чего всё и затевалось: если абонемент ещё
    не начат, первое посещение его активирует и срок пойдёт с сегодня.
    """
    today = timezone.localdate()
    ms = member.active_membership()

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


# ── Расходы ─────────────────────────────────────────────────────────────────

@transaction.atomic
def add_expense(club, category, amount, *, note="", spent_on=None, actor=None):
    exp = Expense.objects.create(
        club=club, category=category, amount=Decimal(str(amount or 0)),
        note=note, spent_on=spent_on or timezone.localdate(), created_by=actor,
    )
    transaction.on_commit(lambda: _notify(club, tg.expense_text(exp)))
    return exp
