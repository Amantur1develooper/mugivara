"""Добавляет клубу типовые направления.

    python manage.py fitness_sections --club 3

То же, что кнопка в кабинете: боевое самбо, бокс, кикбоксинг, вольная
борьба, грэпплинг, ММА, кроссфит, фитнес. Уже существующие пропускает,
поэтому запускать можно сколько угодно.
"""
from django.core.management.base import BaseCommand, CommandError

from fitness.models import SECTION_PRESETS, FitnessClub, Section


class Command(BaseCommand):
    help = "Добавить клубу типовые направления"

    def add_arguments(self, parser):
        parser.add_argument("--club", type=int, required=True, help="id клуба")

    def handle(self, *args, **opts):
        club = FitnessClub.objects.filter(id=opts["club"]).first()
        if not club:
            raise CommandError(f"Клуба #{opts['club']} нет")

        have = {s.name.strip().lower() for s in Section.objects.filter(club=club)}
        order = Section.objects.filter(club=club).count()
        made = []
        for title, icon in SECTION_PRESETS:
            if title.strip().lower() in have:
                continue
            Section.objects.create(club=club, name=title, icon=icon, sort_order=order)
            order += 1
            made.append(f"{icon} {title}")

        self.stdout.write(f"Клуб: {club.name}")
        if made:
            for line in made:
                self.stdout.write(self.style.SUCCESS(f"  + {line}"))
            self.stdout.write("\nЦены и описания допишите в кабинете: Настройки → Направления.")
        else:
            self.stdout.write("Все типовые направления уже есть.")
