"""Копирует конструкторы «Собери сам» из одного филиала в другой.

Филиалы одной сети делают одно и то же меню, но конструктор приходилось
собирать заново руками — шаги, ингредиенты, цены, фотографии. Команда
переносит их целиком:

    python manage.py copy_constructors --from 11 --to 75           # показать план
    python manage.py copy_constructors --from 11 --to 75 --yes     # перенести

Фотографии не копируются файлами: ссылка на тот же файл, что и у исходного
конструктора. Так они не дублируются на диске, а выглядит одинаково.

Ингредиент, привязанный к блюду из меню (branch_item), в новом филиале
ищется по тому же блюду; если такого блюда в меню нет, связь снимается, а
название и цена остаются — конструктор работает, просто без списания.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import (BranchItem, ConstructorGroup,
                            ConstructorIngredient, DishConstructor)
from core.models import Branch


class Command(BaseCommand):
    help = "Копирует конструкторы «Собери сам» из одного филиала в другой"

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="src", type=int, required=True,
                            help="id филиала-источника")
        parser.add_argument("--to", dest="dst", type=int, required=True,
                            help="id филиала, куда копировать")
        parser.add_argument("--yes", action="store_true",
                            help="выполнить (без него только показывает план)")
        parser.add_argument("--replace", action="store_true",
                            help="перезаписать конструкторы с такими же названиями")

    def handle(self, *args, **opts):
        ok, bad, warn = self.style.SUCCESS, self.style.ERROR, self.style.WARNING

        try:
            src = Branch.objects.get(id=opts["src"])
            dst = Branch.objects.get(id=opts["dst"])
        except Branch.DoesNotExist as e:
            raise CommandError(f"Филиал не найден: {e}")
        if src.id == dst.id:
            raise CommandError("Источник и получатель — один и тот же филиал")

        sources = list(
            DishConstructor.objects
            .filter(branch=src)
            .prefetch_related("groups__ingredients")
            .order_by("sort_order", "id")
        )
        if not sources:
            raise CommandError(f"У филиала #{src.id} «{src.name_ru}» конструкторов нет")

        self.stdout.write(f"Из:  #{src.id} {src.name_ru}")
        self.stdout.write(f"В:   #{dst.id} {dst.name_ru}\n")

        existing = {c.name.strip().lower(): c
                    for c in DishConstructor.objects.filter(branch=dst)}
        plan = []
        for cx in sources:
            twin = existing.get(cx.name.strip().lower())
            groups = list(cx.groups.all())
            ings = sum(len(list(g.ingredients.all())) for g in groups)
            if twin and not opts["replace"]:
                self.stdout.write(warn(
                    f"  ✱ «{cx.name}» — уже есть (№{twin.id}), пропускаю. "
                    f"Перезаписать: добавьте --replace"))
                continue
            action = "перезапишу" if twin else "создам"
            self.stdout.write(f"  • «{cx.name}»: {action}, "
                              f"шагов {len(groups)}, ингредиентов {ings}")
            plan.append((cx, twin))

        if not plan:
            self.stdout.write(warn("\nНечего переносить."))
            return

        if not opts["yes"]:
            self.stdout.write(warn(
                "\nЭто только план. Чтобы перенести, повторите с --yes"))
            return

        with transaction.atomic():
            for cx, twin in plan:
                if twin:
                    twin.delete()
                self._copy(cx, dst)

        self.stdout.write(ok(f"\nГотово: перенесено конструкторов — {len(plan)}."))
        self.stdout.write("Проверьте меню филиала и, если нужно, поправьте цены.")

    def _copy(self, cx, dst):
        new_cx = DishConstructor.objects.create(
            branch=dst,
            name=cx.name, name_ky=cx.name_ky, name_en=cx.name_en,
            description=cx.description, description_ky=cx.description_ky,
            description_en=cx.description_en,
            photo=cx.photo.name if cx.photo else None,
            base_price=cx.base_price,
            is_active=cx.is_active, sort_order=cx.sort_order,
        )
        for g in cx.groups.all().order_by("sort_order", "id"):
            new_g = ConstructorGroup.objects.create(
                constructor=new_cx,
                name=g.name, name_ky=g.name_ky, name_en=g.name_en,
                min_select=g.min_select, max_select=g.max_select,
                sort_order=g.sort_order,
            )
            for ing in g.ingredients.all().order_by("sort_order", "id"):
                # Блюдо из меню ищем в новом филиале по тому же товару:
                # id позиции у каждого филиала свой.
                twin_item = None
                if ing.branch_item_id:
                    twin_item = BranchItem.objects.filter(
                        branch=dst, item_id=ing.branch_item.item_id).first()
                ConstructorIngredient.objects.create(
                    group=new_g,
                    branch_item=twin_item,
                    name=ing.name or (ing.branch_item.item.name_ru
                                      if ing.branch_item_id else ""),
                    name_ky=ing.name_ky, name_en=ing.name_en,
                    description=ing.description,
                    description_ky=ing.description_ky,
                    description_en=ing.description_en,
                    price=ing.price,
                    photo=ing.photo.name if ing.photo else None,
                    is_active=ing.is_active, sort_order=ing.sort_order,
                )
        return new_cx
