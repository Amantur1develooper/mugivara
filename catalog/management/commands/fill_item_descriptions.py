# -*- coding: utf-8 -*-
"""Заливает описания блюд на трёх языках из JSON-файла.

Ключ в файле — название блюда по-русски (name_ru), значение — описания:

    {"Чай чёрный": {"ru": "...", "ky": "...", "en": "..."}}

Привязка по названию, а не по id: id блюда на сервере и в локальной базе
могут не совпадать, а названия внутри одного ресторана уникальны.

По умолчанию заполняются только ПУСТЫЕ поля — команду можно запускать
повторно, уже написанный вручную текст она не затрёт. --overwrite меняет
это поведение.

    python manage.py fill_item_descriptions --branch 45 \
        --file catalog/management/commands/_item_descriptions/sushi_ordo.json
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Item
from core.models import Branch, Restaurant

LANGS = ("ru", "ky", "en")


class Command(BaseCommand):
    help = "Заполняет description_ru/ky/en у блюд ресторана из JSON-файла"

    def add_arguments(self, parser):
        who = parser.add_mutually_exclusive_group(required=True)
        who.add_argument("--branch", type=int, help="id филиала — ресторан возьмём из него")
        who.add_argument("--restaurant", type=int, help="id ресторана")
        parser.add_argument("--file", required=True, help="путь к JSON с описаниями")
        parser.add_argument("--overwrite", action="store_true",
                            help="перезаписывать уже заполненные описания")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **o):
        path = Path(o["file"])
        if not path.exists():
            raise CommandError(f"Файл не найден: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise CommandError(f"Файл не читается как JSON: {e}")

        if o["branch"]:
            try:
                rest = Branch.objects.select_related("restaurant").get(id=o["branch"]).restaurant
            except Branch.DoesNotExist:
                raise CommandError(f"Филиал #{o['branch']} не найден")
        else:
            try:
                rest = Restaurant.objects.get(id=o["restaurant"])
            except Restaurant.DoesNotExist:
                raise CommandError(f"Ресторан #{o['restaurant']} не найден")

        self.stdout.write(f"Ресторан: #{rest.id} {rest.name_ru}")
        self.stdout.write(f"Файл:     {path}  ({len(data)} позиций)")

        by_name = {}
        for it in Item.objects.filter(restaurant=rest):
            by_name.setdefault(it.name_ru.strip(), []).append(it)

        filled = skipped = 0
        not_found, ambiguous = [], []

        with transaction.atomic():
            for name, texts in data.items():
                found = by_name.get(name.strip())
                if not found:
                    not_found.append(name)
                    continue
                if len(found) > 1:
                    # одно название на несколько блюд: какое из них имелось в виду,
                    # команда решить не может — пусть разберётся человек
                    ambiguous.append(f"{name} (блюда {', '.join(str(i.id) for i in found)})")
                    continue
                item = found[0]
                changed = []
                for lang in LANGS:
                    text = (texts.get(lang) or "").strip()
                    if not text:
                        continue
                    field = f"description_{lang}"
                    if getattr(item, field).strip() and not o["overwrite"]:
                        continue
                    setattr(item, field, text)
                    changed.append(field)
                if changed:
                    if not o["dry_run"]:
                        item.save(update_fields=changed)
                    filled += 1
                    self.stdout.write(f"  ✓ {name}  ({', '.join(c[-2:] for c in changed)})")
                else:
                    skipped += 1

            if o["dry_run"]:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(f"Заполнено:    {filled}")
        self.stdout.write(f"Уже было:     {skipped}")
        if not_found:
            self.stdout.write(self.style.WARNING(
                f"Не нашлось в меню ({len(not_found)}): " + "; ".join(not_found)))
        if ambiguous:
            self.stdout.write(self.style.WARNING(
                f"Название встречается больше одного раза ({len(ambiguous)}): "
                + "; ".join(ambiguous)))
        if o["dry_run"]:
            self.stdout.write(self.style.WARNING("--dry-run: ничего не сохранено."))
