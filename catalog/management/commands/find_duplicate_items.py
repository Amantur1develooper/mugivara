# -*- coding: utf-8 -*-
"""
Находит задвоенные Item (одинаковый restaurant + name_ru) и задвоенные
BranchItem (одинаковый branch + item) — только ОТЧЁТ, ничего не меняет в БД.

Запуск:
    python manage.py find_duplicate_items
    python manage.py find_duplicate_items --restaurant-id 1
"""
from django.core.management.base import BaseCommand
from django.db.models import Count

from catalog.models import Item, BranchItem


class Command(BaseCommand):
    help = "Отчёт о задвоенных Item и BranchItem (без изменений в БД)"

    def add_arguments(self, parser):
        parser.add_argument("--restaurant-id", type=int, default=None,
                             help="Ограничить отчёт одним рестораном")

    def handle(self, *args, **opts):
        rid = opts.get("restaurant_id")

        # ── Задвоенные Item (одно и то же название дважды у одного ресторана) ──
        items_qs = Item.objects.all()
        if rid:
            items_qs = items_qs.filter(restaurant_id=rid)

        dupe_groups = (
            items_qs.values("restaurant_id", "name_ru")
            .annotate(n=Count("id"))
            .filter(n__gt=1)
            .order_by("restaurant_id", "name_ru")
        )
        dupe_groups = list(dupe_groups)

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n=== Задвоенные Item: {len(dupe_groups)} групп(ы) ===\n"
        ))
        total_extra_items = 0
        for g in dupe_groups:
            rows = list(
                Item.objects.filter(restaurant_id=g["restaurant_id"], name_ru=g["name_ru"])
                .order_by("id")
                .values("id", "base_price", "order_count")
            )
            total_extra_items += len(rows) - 1
            restaurant_name = rows and Item.objects.get(id=rows[0]["id"]).restaurant.name_ru or "?"
            self.stdout.write(
                f"  [{restaurant_name} / rest_id={g['restaurant_id']}] "
                f"«{g['name_ru']}» — {g['n']} штук: "
                + ", ".join(f"id={r['id']} (цена={r['base_price']}, заказов={r['order_count']})" for r in rows)
            )

        # ── Задвоенные BranchItem (одна и та же пара филиал+блюдо дважды) ──
        bi_qs = BranchItem.objects.all()
        if rid:
            bi_qs = bi_qs.filter(item__restaurant_id=rid)

        bi_dupe_groups = (
            bi_qs.values("branch_id", "item_id")
            .annotate(n=Count("id"))
            .filter(n__gt=1)
            .order_by("branch_id", "item_id")
        )
        bi_dupe_groups = list(bi_dupe_groups)

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n=== Задвоенные BranchItem: {len(bi_dupe_groups)} групп(ы) ===\n"
        ))
        total_extra_bi = 0
        for g in bi_dupe_groups:
            rows = list(
                BranchItem.objects.filter(branch_id=g["branch_id"], item_id=g["item_id"])
                .order_by("id").values("id", "price", "is_available")
            )
            total_extra_bi += len(rows) - 1
            item = Item.objects.filter(id=g["item_id"]).first()
            self.stdout.write(
                f"  [branch_id={g['branch_id']}] «{item.name_ru if item else '?'}» (item_id={g['item_id']}) "
                f"— {g['n']} штук: "
                + ", ".join(f"id={r['id']} (цена={r['price']}, доступно={r['is_available']})" for r in rows)
            )

        self.stdout.write("\n" + self.style.SUCCESS(
            f"Итого лишних строк: {total_extra_items} Item, {total_extra_bi} BranchItem."
        ))
        if dupe_groups or bi_dupe_groups:
            self.stdout.write(
                "\nЧтобы безопасно объединить дубли (с уважением к истории заказов — "
                "их удалить нельзя, PROTECT), запустите:\n"
                "  python manage.py merge_duplicate_items          # предпросмотр\n"
                "  python manage.py merge_duplicate_items --yes    # применить\n"
            )
        else:
            self.stdout.write("Дублей не найдено — можно применять миграцию с unique_together.")
