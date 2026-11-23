"""Утренняя сводка клуба в Telegram: дни рождения и кому позвонить.

    python manage.py fitness_digest                 # все клубы, на сегодня
    python manage.py fitness_digest --club 3        # один клуб
    python manage.py fitness_digest --days 3        # дни рождения на 3 дня вперёд
    python manage.py fitness_digest --dry-run       # только показать текст
    python manage.py fitness_digest --force         # даже если сегодня уже слали

Ставится в cron раз в день, с утра:

    0 9 * * * cd /var/www/mugivara && .venv/bin/python manage.py fitness_digest

Повторный запуск в тот же день ничего не пришлёт — у клуба стоит отметка
о дате отправки, иначе cron каждые пять минут засыпал бы группу.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from fitness import tg
from fitness.models import FitnessClub, Lead, Member, Membership, OwedVisit


class Command(BaseCommand):
    help = "Отправить в чат зала сводку: дни рождения, кому позвонить"

    def add_arguments(self, parser):
        parser.add_argument("--club", type=int, help="id клуба; без него — все")
        parser.add_argument("--days", type=int, default=1,
                            help="на сколько дней вперёд смотреть дни рождения")
        parser.add_argument("--dry-run", action="store_true",
                            help="показать текст, ничего не отправлять")
        parser.add_argument("--force", action="store_true",
                            help="отправить, даже если сегодня уже отправляли")
        parser.add_argument("--only-birthdays", action="store_true",
                            help="без «кончается абонемент» и «давно не приходили»")

    def handle(self, *args, **opts):
        today = timezone.localdate()
        clubs = FitnessClub.objects.filter(is_active=True)
        if opts.get("club"):
            clubs = clubs.filter(id=opts["club"])

        sent = skipped = 0
        for club in clubs:
            if (not opts["force"] and not opts["dry_run"]
                    and club.digest_sent_on == today):
                skipped += 1
                continue

            data = self._collect(club, today, max(1, opts["days"]),
                                 only_birthdays=opts["only_birthdays"])
            text = tg.digest_text(club, today, **data)

            if opts["dry_run"]:
                self.stdout.write(f"\n── {club.name} (#{club.id}) ──")
                self.stdout.write(text)
                continue

            # Если поздравлять и звонить некому — не шлём: ежедневное
            # «никого нет» быстро приучает не читать группу.
            if not any(data.values()):
                skipped += 1
                continue

            if tg.notify_gym(club, text):
                club.digest_sent_on = today
                club.save(update_fields=["digest_sent_on"])
                sent += 1
                self.stdout.write(self.style.SUCCESS(f"  {club.name}: отправлено"))
            else:
                self.stdout.write(self.style.WARNING(
                    f"  {club.name}: чат зала не настроен или Telegram не ответил"))

        if not opts["dry_run"]:
            self.stdout.write(f"\nОтправлено: {sent}, пропущено: {skipped}.")

    def _collect(self, club, today, days, *, only_birthdays=False):
        window = [today + timedelta(days=i) for i in range(days)]
        by_md = {(d.month, d.day): d for d in window}

        birthdays = []
        for m in (Member.objects.filter(club=club, is_active=True,
                                        birth_date__isnull=False)
                  .only("id", "full_name", "phone", "birth_date")):
            when = by_md.get((m.birth_date.month, m.birth_date.day))
            if not when:
                continue
            age = when.year - m.birth_date.year
            birthdays.append({"member": m, "when": when,
                              "age": age if 0 < age < 120 else None})
        birthdays.sort(key=lambda x: (x["when"], x["member"].full_name))

        if only_birthdays:
            return {"birthdays": birthdays}

        expiring = list(Membership.objects
                        .filter(member__club=club, is_active=True,
                                end_date__isnull=False, end_date__gte=today,
                                end_date__lte=today + timedelta(days=3))
                        .select_related("member").order_by("end_date")[:10])

        # «Пропал» — есть действующий абонемент, но две недели не приходил
        edge = timezone.now() - timedelta(days=14)
        lost = []
        for ms in (Membership.objects
                   .filter(member__club=club, is_active=True,
                           start_date__isnull=False, end_date__gte=today)
                   .select_related("member")[:200]):
            last = ms.member.visits.filter(success=True).order_by("-visit_time").first()
            if last and last.visit_time < edge:
                lost.append({"member": ms.member,
                             "days": (timezone.now() - last.visit_time).days})
        lost = lost[:8]

        # Занятия в долг: без них долг тихо копится, пока кто-нибудь не
        # откроет карточку клиента.
        owed = []
        counts = {}
        for d in (OwedVisit.objects.filter(club=club, is_settled=False)
                  .select_related("member")):
            counts.setdefault(d.member_id, {"member": d.member, "count": 0})
            counts[d.member_id]["count"] += 1
        owed = sorted(counts.values(), key=lambda x: -x["count"])[:8]

        overdue = list(Lead.objects
                       .filter(club=club, next_contact_at__lt=timezone.now())
                       .exclude(status__in=[Lead.Status.SOLD, Lead.Status.LOST])
                       .order_by("next_contact_at")[:8])

        return {"birthdays": birthdays, "expiring": expiring,
                "lost": lost, "overdue": overdue, "owed": owed}
