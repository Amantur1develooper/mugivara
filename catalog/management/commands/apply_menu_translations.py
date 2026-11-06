# -*- coding: utf-8 -*-
"""Заливает переводы и описания меню из JSON: блюда, категории, конструкторы.

Формат файла — четыре необязательных раздела:

    {
      "items": {
        "Пепперони small": {
          "name_ky": "...", "name_en": "...",
          "description_ru": "...", "description_ky": "...", "description_en": "..."
        }
      },
      "categories": { "Напитки": {"name_ky": "...", "name_en": "..."} },
      "constructors": {
        "Собери свою Пиццу": {
          "name_ky": "...", "name_en": "...",
          "description_ky": "...", "description_en": "...",
          "groups":      { "Тесто":    {"name_ky": "...", "name_en": "..."} },
          "ingredients": { "Говядина": {"name_ky": "...", "name_en": "..."} }
        }
      }
    }

Ключ — всегда русское название (name_ru, а у конструктора — name). Привязки
по id нет намеренно: id блюда на сервере и в локальной базе не совпадают.

По умолчанию заполняются только ПУСТЫЕ поля, поэтому команду можно запускать
повторно — написанное руками она не затрёт. --overwrite меняет поведение.

    python manage.py apply_menu_translations --branch 45 \
        --file catalog/management/commands/_menu_translations/pizzacraft.json
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import (
    Category, ConstructorGroup, ConstructorIngredient, DishConstructor, Item,
)
from core.models import Branch


class Command(BaseCommand):
    help = "Заполняет переводы и описания меню филиала из JSON-файла"

    def add_arguments(self, parser):
        parser.add_argument("--branch", type=int, required=True,
                            help="id филиала (блюда и категории берём из его ресторана)")
        parser.add_argument("--file", required=True, help="путь к JSON с переводами")
        parser.add_argument("--overwrite", action="store_true",
                            help="перезаписывать уже заполненные поля")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **o):
        path = Path(o["file"])
        if not path.exists():
            raise CommandError(f"Файл не найден: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise CommandError(f"Файл не читается как JSON: {e}")

        try:
            branch = Branch.objects.select_related("restaurant").get(id=o["branch"])
        except Branch.DoesNotExist:
            raise CommandError(f"Филиал #{o['branch']} не найден")

        self.stdout.write(f"Филиал:   #{branch.id} {branch.name_ru}")
        self.stdout.write(f"Ресторан: #{branch.restaurant_id} {branch.restaurant.name_ru}")
        self.stdout.write(f"Файл:     {path}")
        self.stdout.write("")

        self.overwrite = o["overwrite"]
        self.missing = []
        self.ambiguous = []
        total = 0

        with transaction.atomic():
            total += self._section(
                "Блюда", data.get("items", {}),
                Item.objects.filter(restaurant_id=branch.restaurant_id), "name_ru")
            total += self._section(
                "Категории", data.get("categories", {}),
                Category.objects.filter(menu_set__restaurant_id=branch.restaurant_id), "name_ru")
            total += self._constructors(branch, data.get("constructors", {}))

            if o["dry_run"]:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(f"Изменено объектов: {total}")
        if self.missing:
            self.stdout.write(self.style.WARNING(
                f"Не нашлось ({len(self.missing)}): " + "; ".join(self.missing)))
        if self.ambiguous:
            self.stdout.write(self.style.WARNING(
                f"Название встречается больше одного раза ({len(self.ambiguous)}): "
                + "; ".join(self.ambiguous)))
        if o["dry_run"]:
            self.stdout.write(self.style.WARNING("--dry-run: ничего не сохранено."))

    # ── вспомогательное ──────────────────────────────────────────────────

    def _index(self, qs, key_field):
        idx = {}
        for obj in qs:
            idx.setdefault((getattr(obj, key_field) or "").strip(), []).append(obj)
        return idx

    def _apply(self, obj, fields, label):
        changed = []
        for field, text in fields.items():
            text = (text or "").strip()
            if not text or not hasattr(obj, field):
                continue
            if (getattr(obj, field) or "").strip() and not self.overwrite:
                continue
            setattr(obj, field, text)
            changed.append(field)
        if changed:
            obj.save(update_fields=changed)
            self.stdout.write(f"  ✓ {label}  ({', '.join(changed)})")
            return 1
        return 0

    def _section(self, title, rows, qs, key_field, prefix=""):
        if not rows:
            return 0
        self.stdout.write(self.style.MIGRATE_HEADING(f"{title} — {len(rows)}"))
        idx = self._index(qs, key_field)
        n = 0
        for key, fields in rows.items():
            found = idx.get(key.strip())
            if not found:
                self.missing.append(f"{prefix}{key}")
                continue
            if len(found) > 1:
                self.ambiguous.append(
                    f"{prefix}{key} (id: {', '.join(str(x.id) for x in found)})")
                continue
            n += self._apply(found[0], fields, prefix + key)
        return n

    def _constructors(self, branch, rows):
        if not rows:
            return 0
        self.stdout.write(self.style.MIGRATE_HEADING(f"Конструкторы — {len(rows)}"))
        idx = self._index(DishConstructor.objects.filter(branch=branch), "name")
        n = 0
        for key, body in rows.items():
            found = idx.get(key.strip())
            if not found:
                self.missing.append(f"конструктор «{key}»")
                continue
            if len(found) > 1:
                self.ambiguous.append(
                    f"конструктор «{key}» (id: {', '.join(str(x.id) for x in found)})")
                continue
            cx = found[0]
            own = {k: v for k, v in body.items() if k not in ("groups", "ingredients")}
            n += self._apply(cx, own, f"конструктор «{key}»")
            n += self._section(
                f"  шаги «{key}»", body.get("groups", {}),
                ConstructorGroup.objects.filter(constructor=cx), "name", prefix="шаг ")
            # позиции конструктора: ручные названия. У позиции, привязанной к
            # блюду меню, своего названия нет — она берёт перевод у блюда, его
            # достаточно задать в разделе "items"
            n += self._section(
                f"  позиции «{key}»", body.get("ingredients", {}),
                ConstructorIngredient.objects.filter(
                    group__constructor=cx, branch_item__isnull=True), "name",
                prefix="позиция ")
        return n
