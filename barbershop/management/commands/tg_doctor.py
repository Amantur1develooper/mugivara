"""Почему записи не приходят в Telegram — разбор по шагам.

    python manage.py tg_doctor              # проверить все барбершопы
    python manage.py tg_doctor --shop 3     # только один
    python manage.py tg_doctor --shop 3 --send   # и отправить пробное сообщение

Проверяет по порядку: токен бота, вебхук, номер чата у заведения, может ли
бот в этот чат писать. Останавливается на первом месте, где рвётся цепочка.
"""
import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from barbershop import tg
from barbershop.models import Appointment, Barbershop


class Command(BaseCommand):
    help = "Проверяет, доходят ли записи барбершопа в Telegram"

    def add_arguments(self, parser):
        parser.add_argument("--shop", type=int, help="id барбершопа")
        parser.add_argument("--send", action="store_true",
                            help="отправить в чат пробное сообщение")

    def handle(self, *args, **opts):
        ok, bad, warn = self.style.SUCCESS, self.style.ERROR, self.style.WARNING

        self.stdout.write("── 1. Бот ──────────────────────────────────────")
        token = tg.bot_token()
        if not token:
            self.stdout.write(bad("  токен не задан: TG_BOT_TOKEN / TELEGRAM_BOT_TOKEN"))
            return
        me = self._api("getMe")
        if not me.get("ok"):
            self.stdout.write(bad(f"  токен не работает: {me.get('description')}"))
            return
        self.stdout.write(ok(f"  @{me['result'].get('username')} — токен рабочий"))

        self.stdout.write("\n── 2. Вебхук (кнопки под записью) ──────────────")
        info = self._api("getWebhookInfo").get("result", {})
        if info.get("url"):
            self.stdout.write(ok("  включён"))
            if info.get("last_error_message"):
                self.stdout.write(warn(f"  последняя ошибка: {info['last_error_message']}"))
            if info.get("pending_update_count"):
                self.stdout.write(warn(f"  не доставлено: {info['pending_update_count']}"))
        else:
            self.stdout.write(warn("  не настроен — сообщения придут, но кнопки работать не будут"
                                   "\n  включить: manage.py tg_webhook --set"))

        self.stdout.write("\n── 3. Заведения ────────────────────────────────")
        shops = Barbershop.objects.all().order_by("id")
        if opts["shop"]:
            shops = shops.filter(id=opts["shop"])
        if not shops:
            self.stdout.write(bad("  барбершопов нет"))
            return

        for shop in shops:
            self.stdout.write(f"\n  #{shop.id} {shop.name}")
            if not shop.tg_chat_id:
                self.stdout.write(bad(
                    "    TG Chat ID не заполнен — сюда ничего не отправляется.\n"
                    "    Добавьте бота в чат, напишите там /id и впишите номер\n"
                    "    в карточку заведения в кабинете."))
                continue

            chat = self._api("getChat", chat_id=shop.tg_chat_id)
            if not chat.get("ok"):
                self.stdout.write(bad(f"    чат {shop.tg_chat_id} недоступен: "
                                      f"{chat.get('description')}"))
                self.stdout.write("    чаще всего бота просто нет в этом чате или номер неверный")
                continue
            title = chat["result"].get("title") or chat["result"].get("username") or "личный чат"
            self.stdout.write(ok(f"    чат {shop.tg_chat_id} — «{title}»"))
            if shop.tg_thread_id:
                self.stdout.write(f"    тема: {shop.tg_thread_id}")

            if opts["send"]:
                payload = {"chat_id": shop.tg_chat_id,
                           "text": "🔧 Проверка связи: бот пишет в этот чат."}
                if shop.tg_thread_id:
                    payload["message_thread_id"] = int(shop.tg_thread_id)
                res = self._api("sendMessage", **payload)
                if res.get("ok"):
                    self.stdout.write(ok("    пробное сообщение отправлено"))
                else:
                    self.stdout.write(bad(f"    отправить не вышло: {res.get('description')}"))

        self.stdout.write("\n── 4. Последние записи ─────────────────────────")
        qs = Appointment.objects.order_by("-id")
        if opts["shop"]:
            qs = qs.filter(barbershop_id=opts["shop"])
        rows = list(qs[:5])
        if not rows:
            self.stdout.write("  записей ещё нет — забронируйте через сайт для проверки")
        for a in rows:
            mark = ok("карточка в чате") if a.tg_message_id else warn("в чат не ушла")
            self.stdout.write(f"  #{a.id} {a.appt_date} {a.appt_time:%H:%M} "
                              f"{a.customer_name} · {a.status} — {mark}")

    def _api(self, method, **payload):
        try:
            return requests.post(tg.API.format(token=tg.bot_token(), method=method),
                                 json=payload, timeout=10).json()
        except Exception as e:
            return {"ok": False, "description": str(e)}
