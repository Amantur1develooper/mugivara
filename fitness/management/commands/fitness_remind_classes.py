"""Напоминание группам о тренировке в Telegram.

    python manage.py fitness_remind_classes             # на завтра, все клубы
    python manage.py fitness_remind_classes --today     # на сегодня
    python manage.py fitness_remind_classes --club 3
    python manage.py fitness_remind_classes --dry-run   # только показать

Ставится в cron вечером — напомнить про завтрашние тренировки:

    0 20 * * * cd /var/www/mugivara && .venv/bin/python manage.py fitness_remind_classes

Напоминание уходит в чат группы, если он заполнен (у детских групп это
чат родителей), иначе в общий чат зала. Отменённые тренировки
пропускаются, а повторный запуск ничего не дублирует: на каждой дате
стоит отметка об отправке.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from fitness import tg
from fitness.models import ClassDay, FitnessClub, GroupClass


class Command(BaseCommand):
    help = "Напомнить группам о тренировке в Telegram"

    def add_arguments(self, parser):
        parser.add_argument("--club", type=int, help="id клуба; без него — все")
        parser.add_argument("--today", action="store_true",
                            help="напомнить про сегодняшние, а не завтрашние")
        parser.add_argument("--date", help="конкретная дата, ГГГГ-ММ-ДД")
        parser.add_argument("--dry-run", action="store_true",
                            help="показать текст, ничего не отправлять")
        parser.add_argument("--force", action="store_true",
                            help="отправить, даже если уже напоминали")

    def handle(self, *args, **opts):
        day = self._day(opts)
        clubs = FitnessClub.objects.filter(is_active=True)
        if opts.get("club"):
            clubs = clubs.filter(id=opts["club"])

        sent = skipped = 0
        for club in clubs:
            slots = (GroupClass.objects
                     .filter(club=club, is_active=True, weekday=day.weekday())
                     .select_related("group", "group__section", "trainer")
                     .order_by("time_from"))
            for slot in slots:
                state = ClassDay.objects.filter(group_class=slot, date=day).first()
                if state and state.is_cancelled:
                    self.stdout.write(self.style.WARNING(
                        f"  {club.name}: «{slot.name}» {day:%d.%m} отменена — не напоминаю"))
                    skipped += 1
                    continue
                if state and state.reminded_at and not opts["force"] and not opts["dry_run"]:
                    skipped += 1
                    continue

                text = tg.class_reminder_text(slot, day)
                if opts["dry_run"]:
                    chat, _ = tg.group_chat(slot.group) if slot.group_id \
                        else tg.gym_chat(club)
                    where = "чат группы" if (slot.group_id and slot.group.tg_chat_id) \
                        else "чат зала"
                    self.stdout.write(f"\n── {club.name} → {where} ({chat or 'не задан'}) ──")
                    self.stdout.write(text)
                    continue

                ok = (tg.notify_group(slot.group, text) if slot.group_id
                      else tg.notify_gym(club, text))
                if ok:
                    state = state or ClassDay.objects.create(group_class=slot, date=day)
                    state.reminded_at = timezone.now()
                    state.save(update_fields=["reminded_at", "updated_at"])
                    sent += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"  {club.name}: «{slot.who}» {slot.time_from:%H:%M} — напомнили"))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"  {club.name}: «{slot.name}» — чат не настроен"))
                    skipped += 1

        if not opts["dry_run"]:
            self.stdout.write(f"\nОтправлено: {sent}, пропущено: {skipped}.")

    def _day(self, opts):
        if opts.get("date"):
            from datetime import datetime
            return datetime.strptime(opts["date"], "%Y-%m-%d").date()
        today = timezone.localdate()
        return today if opts["today"] else today + timedelta(days=1)
