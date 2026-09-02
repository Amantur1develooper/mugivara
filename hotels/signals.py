from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import HotelBooking, FinanceAccount, FinanceCategory, FinanceTxn

# статусы, при которых считаем деньги за бронь полученными
PAID_STATUSES = {HotelBooking.Status.CHECKEDIN, HotelBooking.Status.COMPLETED}


def sync_booking_income(booking):
    """Держит автодоход (FinanceTxn is_auto) по брони в согласии с её статусом.

    — статус стал «Заселён»/«Завершена» и есть сумма  → создать/обновить приход
    — иначе (новая / отменена / без суммы)            → удалить авто-приход, если был
    Если у филиала ещё нет ни одной кассы — просто ничего не делаем.
    """
    existing = FinanceTxn.objects.filter(booking=booking, is_auto=True).first()

    if booking.status not in PAID_STATUSES or not booking.total:
        if existing:
            existing.delete()
        return

    account = (
        FinanceAccount.objects.filter(branch=booking.branch, is_active=True, is_default=True).first()
        or FinanceAccount.objects.filter(branch=booking.branch, is_active=True)
                                 .order_by("sort_order", "id").first()
    )
    if not account:
        return

    category, _ = FinanceCategory.objects.get_or_create(
        branch=booking.branch, flow=FinanceCategory.Flow.IN, name="Проживание",
    )
    txn_date = (
        booking.actual_checkin_at.date() if booking.actual_checkin_at
        else booking.checkin_date or booking.created_at.date()
    )
    comment = f"Бронь #{booking.id} · {booking.customer_name}"

    if existing:
        FinanceTxn.objects.filter(pk=existing.pk).update(
            amount=booking.total, date=txn_date, account=account,
            category=category, comment=comment,
        )
    else:
        FinanceTxn.objects.create(
            branch=booking.branch, kind=FinanceTxn.Kind.INCOME, date=txn_date,
            amount=booking.total, account=account, category=category,
            booking=booking, is_auto=True, comment=comment,
        )


@receiver(post_save, sender=HotelBooking)
def _booking_saved(sender, instance, **kwargs):
    sync_booking_income(instance)
