"""Присылает карточку заказа магазина в чаты филиала ещё раз.

Пригодится для заказов, которые пришли до того, как кнопки появились, или
если Telegram отказал и карточка не доехала.

    python manage.py shop_order_card --order 45
    python manage.py shop_order_card --branch 7 --last 5   # последние пять
    python manage.py shop_order_card --branch 7 --new      # все неподтверждённые
"""
from django.core.management.base import BaseCommand, CommandError

from shops import tg as shop_tg
from shops.models import StoreOrder


class Command(BaseCommand):
    help = "Присылает карточку заказа магазина в Telegram заново"

    def add_arguments(self, parser):
        parser.add_argument("--order", type=int, help="id заказа")
        parser.add_argument("--branch", type=int, help="id филиала")
        parser.add_argument("--last", type=int, default=0, help="сколько последних заказов")
        parser.add_argument("--new", action="store_true", help="все неподтверждённые заказы")

    def handle(self, *args, **opts):
        if not shop_tg.bot_token():
            raise CommandError("Не задан токен бота (TG_BOT_TOKEN / TELEGRAM_BOT_TOKEN)")

        qs = StoreOrder.objects.select_related("branch").order_by("-id")
        if opts["order"]:
            qs = qs.filter(id=opts["order"])
        else:
            if opts["branch"]:
                qs = qs.filter(branch_id=opts["branch"])
            if opts["new"]:
                qs = qs.filter(status=StoreOrder.Status.NEW)
            qs = qs[:max(1, opts["last"] or 1)]

        orders = list(qs)
        if not orders:
            raise CommandError("Подходящих заказов не нашлось")

        for order in orders:
            chats = shop_tg.recipients(order.branch)
            if not chats:
                self.stdout.write(self.style.ERROR(
                    f"  #{order.id}: у филиала «{order.branch.name_ru}» не заполнен TG Chat ID"))
                continue
            # карточка этого заказа могла уже висеть в чате — забываем её,
            # иначе повторная отправка пропустит все чаты
            order.tg_messages = {}
            order.save(update_fields=["tg_messages"])
            sent, errors = shop_tg.send_order(order)
            style = self.style.SUCCESS if sent else self.style.ERROR
            self.stdout.write(style(
                f"  #{order.id} {order.status}: отправлено в {sent} чат(ов), ошибок {errors}"))
