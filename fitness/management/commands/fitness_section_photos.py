# -*- coding: utf-8 -*-
"""Ставит фотографии направлениям фитнес-клуба.

Направления заводят из готового списка — бокс, самбо, ММА, — и каждое
остаётся без картинки, пока владелец не снимет свою. Пустая карточка на
странице клуба выглядит незаконченной, а снимать десять дисциплин сразу
никто не станет. Команда кладёт в такие карточки подобранные снимки.

    python manage.py fitness_section_photos --club elita --dry-run
    python manage.py fitness_section_photos --club elita
    python manage.py fitness_section_photos --all

Фотографии взяты с Викисклада и лежат рядом, в _section_photos. Все —
общественное достояние или CC0: подпись автора не требуется, на
коммерческой странице клуба их использовать можно. Список лицензий с
авторами — в licenses.json там же.

Снимок ставится только в пустую карточку: фото, загруженное владельцем
в настройках клуба, команда не трогает. Перезаписать всё — --replace.
"""
import json
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from fitness.models import FitnessClub, Section

DATA = Path(__file__).resolve().parent / "_section_photos"

# Ключевые слова → файл. Порядок важен: «кикбоксинг» проверяем раньше
# «бокса», а «боевое самбо» раньше просто «самбо», иначе бокс достанется
# кикбоксингу, а виды самбо перепутаются между собой.
RULES = [
    (("кикбокс", "кик-бокс", "муай", "тайск"), "kikboksing"),
    (("боевое самбо", "боевого самбо"),        "boevoe-sambo"),
    (("спортивное самбо", "самбо"),            "sportivnoe-sambo"),
    (("джиу", "jiu", "бжж", "bjj"),            "dzhiu-dzhitsu"),
    (("грэпл", "грепл", "грэппл", "grappl"),   "grepling"),
    (("мма", "mma", "смешан"),                 "mma"),
    (("борьб", "вольн", "греко"),              "volnaya-borba"),
    (("кроссфит", "crossfit", "функционал"),   "krossfit"),
    (("бокс",),                                "boks"),
    (("фитнес", "трена", "зал"),               "fitnes"),
]


def photo_for(name):
    """Какой снимок подходит направлению с таким названием."""
    low = (name or "").strip().lower()
    for words, slug in RULES:
        if any(w in low for w in words):
            path = DATA / f"{slug}.jpg"
            if path.exists():
                return slug, path
    return None, None


class Command(BaseCommand):
    help = "Ставит фотографии направлениям фитнес-клуба"

    def add_arguments(self, parser):
        parser.add_argument("--club", help="slug клуба, напр. elita")
        parser.add_argument("--all", action="store_true",
                            help="все клубы сразу")
        parser.add_argument("--dry-run", action="store_true",
                            help="только показать, что будет поставлено")
        parser.add_argument("--replace", action="store_true",
                            help="перезаписать и те, где фото уже есть")

    def handle(self, *args, **opts):
        ok, warn = self.style.SUCCESS, self.style.WARNING
        if not DATA.exists():
            raise CommandError(f"Нет папки со снимками: {DATA}")

        if opts["all"]:
            clubs = list(FitnessClub.objects.all())
        elif opts["club"]:
            clubs = list(FitnessClub.objects.filter(slug=opts["club"]))
            if not clubs:
                raise CommandError(f"Клуб «{opts['club']}» не найден. "
                                   f"Есть: " + ", ".join(
                                       FitnessClub.objects.values_list("slug", flat=True)))
        else:
            raise CommandError("Укажите --club <slug> или --all")

        put = skipped = unknown = 0
        for club in clubs:
            self.stdout.write(f"\n{club.name} ({club.slug})")
            for sec in Section.objects.filter(club=club).order_by("sort_order", "id"):
                slug, path = photo_for(sec.name)
                if not slug:
                    self.stdout.write(warn(f"  ? {sec.name} — не подобрал снимок"))
                    unknown += 1
                    continue
                if sec.photo and not opts["replace"]:
                    self.stdout.write(f"  · {sec.name} — уже с фото, не трогаю")
                    skipped += 1
                    continue
                if opts["dry_run"]:
                    self.stdout.write(f"  + {sec.name} ← {slug}.jpg")
                    put += 1
                    continue
                sec.photo.save(f"{club.slug}-{slug}.jpg",
                               ContentFile(path.read_bytes()), save=True)
                self.stdout.write(ok(f"  + {sec.name} ← {slug}.jpg"))
                put += 1

        self.stdout.write("")
        if opts["dry_run"]:
            self.stdout.write(warn(f"Это только список: поставил бы {put}. "
                                   f"Запустите без --dry-run"))
        else:
            self.stdout.write(ok(f"Готово. Поставлено: {put}, "
                                 f"пропущено (уже с фото): {skipped}, "
                                 f"без подходящего снимка: {unknown}."))
        self.stdout.write("Поменять фото можно в настройках клуба: "
                          "направление → «Фото».")
        try:
            lic = json.loads((DATA / "licenses.json").read_text())
            self.stdout.write(f"Снимки: Викисклад, {len(lic)} шт., "
                              f"общественное достояние и CC0 — подпись автора не нужна.")
        except Exception:
            pass
