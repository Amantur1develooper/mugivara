"""Узнать номер чата, в который добавили бота.

Обычный способ — написать в группе «/id», бот ответит сам. Но он работает
только при включённом вебхуке. Эта команда — запасной путь: она на минуту
снимает вебхук, слушает свежие сообщения напрямую и возвращает вебхук на
место.

    python manage.py tg_chat_id            # послушать 30 секунд
    python manage.py tg_chat_id --wait 60  # подольше

Перед запуском добавьте бота в группу и напишите там любое сообщение.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from integrations import tgbot


class Command(BaseCommand):
    help = "Показывает Chat ID чатов, где бот видел свежие сообщения"

    def add_arguments(self, parser):
        parser.add_argument("--wait", type=int, default=30,
                            help="сколько секунд слушать (по умолчанию 30)")

    def handle(self, *args, **opts):
        if not tgbot.bot_token():
            raise CommandError("Не задан токен бота (TELEGRAM_BOT_TOKEN в .env)")

        wait = max(5, min(opts["wait"], 120))
        info = tgbot.call("getWebhookInfo", _timeout=30, _tries=3) or {}
        saved_url = info.get("url") or ""

        if saved_url:
            self.stdout.write("Снимаю вебхук на время прослушивания…")
            tgbot.call("deleteWebhook", _timeout=30, _tries=3,
                       drop_pending_updates=False)

        try:
            self.stdout.write(self.style.WARNING(
                f"Напишите в группе любое сообщение. Слушаю {wait} секунд…"))
            # long polling: Telegram держит запрос, пока не придёт сообщение
            updates = tgbot.call("getUpdates", _timeout=wait + 10, _tries=1,
                                 timeout=wait, allowed_updates=["message"]) or []
            self._report(updates)
        finally:
            if saved_url:
                self.stdout.write("\nВозвращаю вебхук на место…")
                secret = (getattr(settings, "TG_WEBHOOK_SECRET", "") or "").strip()
                ok = tgbot.call("setWebhook", _timeout=30, _tries=3,
                                url=saved_url, secret_token=secret,
                                allowed_updates=["callback_query", "message"])
                if ok:
                    self.stdout.write(self.style.SUCCESS("  вебхук снова включён"))
                else:
                    self.stdout.write(self.style.ERROR(
                        "  вебхук вернуть не удалось — включите вручную:\n"
                        "    python manage.py tg_webhook --set"))

    def _report(self, updates):
        seen = {}
        for u in updates:
            msg = u.get("message") or u.get("channel_post") or {}
            chat = msg.get("chat") or {}
            if not chat.get("id"):
                continue
            key = (chat["id"], msg.get("message_thread_id"))
            seen[key] = (chat.get("title") or chat.get("username")
                         or chat.get("first_name") or "личный чат", chat.get("type"))

        if not seen:
            self.stdout.write(self.style.ERROR(
                "\nНичего не услышал. Проверьте:\n"
                "  • бот добавлен в группу;\n"
                "  • после добавления в ней написали сообщение;\n"
                "  • у бота в @BotFather выключен Privacy Mode "
                "(/mybots → Bot Settings → Group Privacy → Turn off),\n"
                "    иначе он не видит обычные сообщения группы."))
            return

        self.stdout.write(self.style.SUCCESS("\nНайденные чаты:"))
        for (chat_id, thread), (title, kind) in seen.items():
            line = f"  {chat_id}   {title} ({kind})"
            if thread:
                line += f"   тема: {thread}"
            self.stdout.write(line)
        self.stdout.write(
            "\nЭтот номер вписывается в карточке заведения в поле TG Chat ID "
            "(а номер темы — в TG Thread ID).")
