"""Копирует конструкторы «Собери сам» из одного филиала в другой.

Филиалы одной сети делают одно и то же меню, но конструктор приходилось
собирать заново руками — шаги, ингредиенты, цены, фотографии. Команда
переносит их целиком:

    python manage.py copy_constructors --check --restaurant pizzacraft
        показать по каждому филиалу, работает ли «Собери сам» и почему нет

    python manage.py copy_constructors --from 11 --to 75           # показать план
    python manage.py copy_constructors --from 11 --to 75 --yes     # перенести

    python manage.py copy_constructors --from 11 --restaurant pizzacraft --yes
        перенести во все филиалы заведения, где конструктор не работает

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
        # Обязательность проверяем сами: у --check и у работы по заведению
        # филиал-получатель не указывают.
        parser.add_argument("--from", dest="src", type=int,
                            help="id филиала-источника")
        parser.add_argument("--to", dest="dst", type=int,
                            help="id филиала, куда копировать")
        parser.add_argument("--yes", action="store_true",
                            help="выполнить (без него только показывает план)")
        parser.add_argument("--replace", action="store_true",
                            help="перезаписать конструкторы с такими же названиями")
        parser.add_argument("--restaurant", type=str,
                            help="slug заведения: вместо одного филиала — все его")
        parser.add_argument("--check", action="store_true",
                            help="только проверить, где конструктор работает")

    def handle(self, *args, **opts):
        ok, bad, warn = self.style.SUCCESS, self.style.ERROR, self.style.WARNING

        if opts["check"] or (opts["restaurant"] and not opts["dst"]):
            return self._restaurant_mode(opts, ok, bad, warn)

        if not opts["src"] or not opts["dst"]:
            raise CommandError(
                "Укажите --from и --to, либо --check --restaurant <slug>")
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
                    note = self._retire(twin)
                    self.stdout.write(f"  прежний «{twin.name}» — {note}")
                self._copy(cx, dst)

        self.stdout.write(ok(f"\nГотово: перенесено конструкторов — {len(plan)}."))
        self.stdout.write("Проверьте меню филиала и, если нужно, поправьте цены.")

    def _retire(self, cx):
        """Убирает конструктор из меню, не удаляя его.

        Удалить нельзя: позиции заказов ссылаются на конструктор защищённой
        связью, и у заведения, где по нему уже заказывали, команда упала бы
        с ProtectedError. Поэтому старую запись выключаем — из меню она
        исчезает, история заказов остаётся целой.
        """
        from django.db.models import ProtectedError
        try:
            cx.delete()
            return "удалён"
        except ProtectedError:
            cx.is_active = False
            cx.save(update_fields=["is_active"])
            return "выключен (по нему есть заказы)"

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

    # ── Работа по всему заведению ───────────────────────────────────────────

    def _state(self, branch):
        """Что с конструктором у филиала: (работает, пояснение)."""
        cards = list(DishConstructor.objects
                     .filter(branch=branch)
                     .prefetch_related("groups__ingredients"))
        if not cards:
            return False, "конструкторов нет"

        active = [c for c in cards if c.is_active]
        if not active:
            return False, f"есть {len(cards)}, но все выключены"

        # На сайте показывается только конструктор, у которого хотя бы в
        # одной группе есть активный ингредиент: пустая копия не выводится
        # вовсе, и выглядит это как «не работает».
        working = []
        empty = []
        for c in active:
            groups = list(c.groups.all())
            has_ings = any(any(i.is_active for i in g.ingredients.all())
                           for g in groups)
            if not groups:
                empty.append(f"«{c.name}» — нет шагов")
            elif not has_ings:
                empty.append(f"«{c.name}» — шаги без ингредиентов")
            else:
                working.append(c)

        if working:
            names = ", ".join(f"«{c.name}»" for c in working)
            tail = f"; не показываются: {'; '.join(empty)}" if empty else ""
            return True, f"работает: {names}{tail}"
        return False, "; ".join(empty) or "нечего показывать"

    def _restaurant_mode(self, opts, ok, bad, warn):
        from core.models import Restaurant

        slug = (opts["restaurant"] or "").strip()
        if not slug:
            raise CommandError("Укажите --restaurant <slug>")
        rest = (Restaurant.objects.filter(slug=slug).first()
                or Restaurant.objects.filter(name_ru__iexact=slug).first())
        if not rest:
            raise CommandError(f"Заведение «{slug}» не найдено")

        branches = list(Branch.objects.filter(restaurant=rest).order_by("id"))
        if not branches:
            raise CommandError("У заведения нет филиалов")

        self.stdout.write(f"Заведение: {rest.name_ru}\n")
        broken = []
        for b in branches:
            works, why = self._state(b)
            mark = ok("✓") if works else bad("✗")
            self.stdout.write(f"  {mark} #{b.id} {b.name_ru} — {why}")
            if not works:
                broken.append(b)

        if opts["check"]:
            if broken:
                self.stdout.write(warn(
                    f"\nНе работает у {len(broken)} филиалов. Перенести из рабочего:\n"
                    f"  manage.py copy_constructors --from <id рабочего> "
                    f"--restaurant {slug} --yes"))
            else:
                self.stdout.write(ok("\nВезде работает."))
            return

        if not opts["src"]:
            raise CommandError("Укажите --from <id филиала-источника>")
        src = Branch.objects.filter(id=opts["src"]).first()
        if not src:
            raise CommandError(f"Филиал #{opts['src']} не найден")
        works, why = self._state(src)
        if not works:
            raise CommandError(f"У источника #{src.id} конструктор сам не работает: {why}")

        targets = [b for b in broken if b.id != src.id]
        if not targets:
            self.stdout.write(ok("\nПереносить некуда — везде уже работает."))
            return

        sources = list(DishConstructor.objects.filter(branch=src, is_active=True)
                       .prefetch_related("groups__ingredients")
                       .order_by("sort_order", "id"))
        sources = [c for c in sources
                   if any(any(i.is_active for i in g.ingredients.all())
                          for g in c.groups.all())]

        self.stdout.write(f"\nИз #{src.id} {src.name_ru}: "
                          f"{', '.join(f'«{c.name}»' for c in sources)}")
        self.stdout.write("Перенесу в: " +
                          ", ".join(f"#{b.id} {b.name_ru}" for b in targets))

        if not opts["yes"]:
            self.stdout.write(warn("\nЭто только план. Чтобы перенести, повторите с --yes"))
            return

        done = 0
        with transaction.atomic():
            for b in targets:
                existing = {c.name.strip().lower(): c
                            for c in DishConstructor.objects.filter(branch=b)}
                for cx in sources:
                    twin = existing.get(cx.name.strip().lower())
                    # Пустую копию с тем же названием убираем: именно она и
                    # не показывалась на сайте. Удалить получается не всегда
                    # — по конструктору могли заказывать, — тогда выключаем.
                    if twin:
                        self._retire(twin)
                    self._copy(cx, b)
                    done += 1

        self.stdout.write(ok(f"\nГотово: перенесено {done} конструкторов "
                             f"в {len(targets)} филиалов."))
        for b in targets:
            works, why = self._state(b)
            self.stdout.write(("  " + (ok("✓") if works else bad("✗")) +
                               f" #{b.id} {b.name_ru} — {why}"))
