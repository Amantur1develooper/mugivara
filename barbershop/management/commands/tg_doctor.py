"""Почему записи не приходят в Telegram — разбор по шагам.

    python manage.py tg_doctor                 # барбершопы и картинг
    python manage.py tg_doctor --shop 3        # только барбершоп #3
    python manage.py tg_doctor --venue 1       # только площадка картинга #1
    python manage.py tg_doctor --branch 7      # только филиал магазина #7
    python manage.py tg_doctor --shop 3 --send # и отправить пробное сообщение

Проверяет по порядку: токен бота, вебхук, номер чата у заведения, может ли
бот в этот чат писать. Останавливается на первом месте, где рвётся цепочка.
"""
import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from barbershop import tg
from barbershop.models import Appointment, Barbershop
from shops.models import StoreBranch, StoreOrder
from simracing.models import SimRacingAppointment, SimRacingVenue


class Command(BaseCommand):
    help = "Проверяет, доходят ли записи барбершопа в Telegram"

    def add_arguments(self, parser):
        parser.add_argument("--shop", type=int, help="id барбершопа")
        parser.add_argument("--venue", type=int, help="id площадки картинга")
        parser.add_argument("--branch", type=int, help="id филиала магазина")
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
        # У заведений разных направлений поля называются по-разному,
        # поэтому сводим их к одному виду: (вид, название, чат, тема).
        only = opts["shop"] or opts["venue"] or opts["branch"]
        places = []
        if not only or opts["shop"]:
            qs = Barbershop.objects.all().order_by("id")
            if opts["shop"]:
                qs = qs.filter(id=opts["shop"])
            places += [("Барбершоп", p.id, p.name, p.tg_chat_id, p.tg_thread_id) for p in qs]
        if not only or opts["venue"]:
            qs = SimRacingVenue.objects.all().order_by("id")
            if opts["venue"]:
                qs = qs.filter(id=opts["venue"])
            places += [("Картинг", p.id, p.name, p.tg_chat_id, p.tg_thread_id) for p in qs]
        if not only or opts["branch"]:
            qs = StoreBranch.objects.all().order_by("id")
            if opts["branch"]:
                qs = qs.filter(id=opts["branch"])
            places += [("Магазин", b.id, b.name_ru, b.tg_group_chat_id or b.tg_manager_chat_id,
                        b.tg_thread_id) for b in qs]
        if not places:
            self.stdout.write(bad("  заведений нет"))
            return

        for kind, pid, name, chat_id, thread_id in places:
            self.stdout.write(f"\n  {kind} #{pid} {name}")
            if not chat_id:
                self.stdout.write(bad(
                    "    TG Chat ID не заполнен — сюда ничего не отправляется.\n"
                    "    Добавьте бота в чат, напишите там /id и впишите номер\n"
                    "    в карточку заведения в кабинете."))
                continue

            chat = self._api("getChat", chat_id=chat_id)
            if not chat.get("ok"):
                self.stdout.write(bad(f"    чат {chat_id} недоступен: "
                                      f"{chat.get('description')}"))
                self.stdout.write("    чаще всего бота просто нет в этом чате или номер неверный")
                continue
            title = chat["result"].get("title") or chat["result"].get("username") or "личный чат"
            self.stdout.write(ok(f"    чат {chat_id} — «{title}»"))
            if thread_id:
                self.stdout.write(f"    тема: {thread_id}")

            if opts["send"]:
                payload = {"chat_id": chat_id,
                           "text": "🔧 Проверка связи: бот пишет в этот чат."}
                if thread_id:
                    payload["message_thread_id"] = int(thread_id)
                res = self._api("sendMessage", **payload)
                if res.get("ok"):
                    self.stdout.write(ok("    пробное сообщение отправлено"))
                else:
                    self.stdout.write(bad(f"    отправить не вышло: {res.get('description')}"))

        self.stdout.write("\n── 4. Последние записи ─────────────────────────")
        if not only or opts["shop"]:
            qs = Appointment.objects.order_by("-id")
            if opts["shop"]:
                qs = qs.filter(barbershop_id=opts["shop"])
            self._rows("Барбершоп", list(qs[:5]), ok, warn)
        if not only or opts["venue"]:
            qs = SimRacingAppointment.objects.order_by("-id")
            if opts["venue"]:
                qs = qs.filter(venue_id=opts["venue"])
            self._rows("Картинг", list(qs[:5]), ok, warn)
        if not only or opts["branch"]:
            qs = StoreOrder.objects.order_by("-id")
            if opts["branch"]:
                qs = qs.filter(branch_id=opts["branch"])
            self._orders(list(qs[:5]), ok, warn)

    def _rows(self, kind, rows, ok, warn):
        self.stdout.write(f"\n  {kind}:")
        if not rows:
            self.stdout.write("    записей нет — забронируйте через сайт для проверки")
        for a in rows:
            mark = ok("карточка в чате") if a.tg_message_id else warn("в чат не ушла")
            self.stdout.write(f"    #{a.id} {a.appt_date} {a.appt_time:%H:%M} "
                              f"{a.customer_name or 'Гость'} · {a.status} — {mark}")

    def _orders(self, rows, ok, warn):
        self.stdout.write("\n  Магазины:")
        if not rows:
            self.stdout.write("    заказов нет")
        for o in rows:
            mark = ok(f"карточка в {len(o.tg_messages)} чат(ах)") if o.tg_messages \
                else warn("в чат не ушла")
            self.stdout.write(f"    #{o.id} {o.created_at:%d.%m %H:%M} "
                              f"{o.name or '—'} · {o.status} — {mark}")

    def _api(self, method, **payload):
        try:
            return requests.post(tg.API.format(token=tg.bot_token(), method=method),
                                 json=payload, timeout=10).json()
        except Exception as e:
            return {"ok": False, "description": str(e)}
