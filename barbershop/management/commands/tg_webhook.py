"""Вебхук Telegram для кнопок под записями барбершопа.

    python manage.py tg_webhook --info          # что сейчас настроено
    python manage.py tg_webhook --set           # включить кнопки
    python manage.py tg_webhook --delete        # выключить
    python manage.py tg_webhook --send 42       # прислать карточку записи #42

Адрес вебхука собирается из SITE_URL и TG_WEBHOOK_SECRET (оба в .env).
Telegram принимает только https и порты 443, 80, 88, 8443.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse

from barbershop import tg
from barbershop.models import Appointment
from integrations import tgbot


class Command(BaseCommand):
    help = "Настраивает вебхук Telegram для кнопок под записями барбершопа"

    def add_arguments(self, parser):
        parser.add_argument("--set", action="store_true", help="включить вебхук")
        parser.add_argument("--delete", action="store_true", help="выключить вебхук")
        parser.add_argument("--info", action="store_true", help="показать настройки")
        parser.add_argument("--send", type=int, metavar="ID",
                            help="прислать карточку записи в чат салона")
        parser.add_argument("--url", default="", metavar="URL",
                            help="адрес сайта вместо SITE_URL, напр. https://webordo.kg")

    def handle(self, *args, **opts):
        if not tg.bot_token():
            raise CommandError("Не задан токен бота (TG_BOT_TOKEN или TELEGRAM_BOT_TOKEN)")

        if opts["send"]:
            return self._send(opts["send"])
        if opts["delete"]:
            return self._delete()
        if opts["set"]:
            return self._set(opts["url"])
        return self._info()

    # ── действия ────────────────────────────────────────────────────────────

    def _url(self, override=""):
        secret = (getattr(settings, "TG_WEBHOOK_SECRET", "") or "").strip()
        if not secret:
            raise CommandError(
                "Не задан TG_WEBHOOK_SECRET. Добавьте в .env строку вида\n"
                "    TG_WEBHOOK_SECRET=<32 случайных символа>\n"
                "Сгенерировать: python -c \"import secrets; print(secrets.token_urlsafe(24))\"")
        base = (override or getattr(settings, "SITE_URL", "") or "").rstrip("/")
        if not base.startswith("https://"):
            raise CommandError(f"SITE_URL должен быть https, сейчас «{base or '—'}»")
        return base + reverse("barbershop_tg:webhook", args=[secret]), secret

    def _set(self, override=""):
        url, secret = self._url(override)
        self.stdout.write(f"Адрес: {url}")
        self._reachable(url, secret)

        # api.telegram.org из Кыргызстана отвечает через раз, поэтому ждём
        # дольше обычного и пробуем трижды.
        res = tgbot.call("setWebhook", _timeout=30, _tries=3,
                         url=url, secret_token=secret,
                         allowed_updates=["callback_query", "message"],
                         drop_pending_updates=True)
        if res is None:
            err = tgbot.last_error or "ответ не получен"
            hint = ""
            if "timed out" in err.lower() or "connection" in err.lower():
                hint = ("  Сам Telegram не ответил за 30 секунд — связь с api.telegram.org.\n"
                        "    Проверьте с сервера: curl -s -m 20 -o /dev/null -w '%{http_code}\\n' "
                        "https://api.telegram.org\n"
                        "    Если и там тишина — дело в сети сервера, повторите позже.\n")
            elif "resolve" in err.lower():
                hint = ("  У Telegram не разрешилось имя домена. Проверьте, что он виден снаружи:\n"
                        "      dig +short " + url.split("/")[2] + " @8.8.8.8\n")
            elif "port" in err.lower():
                hint = "  Telegram принимает только порты 443, 80, 88 и 8443.\n"
            raise CommandError(
                f"Telegram не принял адрес: {err}\n" + hint +
                "  Другой домен задаётся так: manage.py tg_webhook --set --url https://ваш-домен")
        self.stdout.write(self.style.SUCCESS("Вебхук включён"))
        self._info()

    def _reachable(self, url, secret):
        """Стучимся по адресу так же, как это будет делать Telegram."""
        import requests
        try:
            r = requests.post(url, json={}, timeout=10,
                              headers={"X-Telegram-Bot-Api-Secret-Token": secret})
            if r.status_code == 200:
                self.stdout.write("  адрес отвечает и секрет совпадает")
            else:
                self.stdout.write(self.style.WARNING(
                    f"  адрес ответил HTTP {r.status_code} — ждали 200"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  адрес не ответил: {e}"))

        # Заголовок с секретом знает только Telegram: без него должен быть отказ.
        try:
            r = requests.post(url, json={}, timeout=10)
            mark = "" if r.status_code == 403 else "  ← ждали 403!"
            self.stdout.write(f"  без секретного заголовка: HTTP {r.status_code}{mark}")
        except Exception:
            pass

    def _delete(self):
        if tgbot.call("deleteWebhook", _timeout=30, _tries=3,
                      drop_pending_updates=False) is None:
            raise CommandError("Не удалось выключить вебхук")
        self.stdout.write(self.style.SUCCESS("Вебхук выключен — кнопки больше не работают"))

    def _info(self):
        info = tgbot.call("getWebhookInfo", _timeout=30, _tries=3) or {}
        me = tgbot.call("getMe", _timeout=30, _tries=3) or {}
        if me:
            self.stdout.write(f"Бот: @{me.get('username', '?')} ({me.get('first_name', '')})")
        self.stdout.write(f"Адрес вебхука: {info.get('url') or '— не настроен'}")
        self.stdout.write(f"Ожидают доставки: {info.get('pending_update_count', 0)}")
        if info.get("last_error_message"):
            self.stdout.write(self.style.ERROR(
                f"Последняя ошибка: {info['last_error_message']}"))
        if not info.get("url"):
            self.stdout.write("\nВключить: python manage.py tg_webhook --set")

    def _send(self, appt_id):
        appt = Appointment.objects.filter(id=appt_id).select_related("barbershop").first()
        if not appt:
            raise CommandError(f"Записи #{appt_id} нет")
        if not appt.barbershop.tg_chat_id:
            raise CommandError(
                f"У барбершопа «{appt.barbershop.name}» не заполнен TG Chat ID")
        if tg.send_appointment(appt) is None:
            raise CommandError("Telegram не принял сообщение — смотрите лог выше")
        self.stdout.write(self.style.SUCCESS(
            f"Карточка записи #{appt.id} отправлена в чат {appt.barbershop.tg_chat_id}"))
