# -*- coding: utf-8 -*-
"""
Безопасно объединяет задвоенные Item (одинаковый restaurant + name_ru) и
задвоенные BranchItem (одинаковый branch + item) в один экземпляр.

Для каждой группы дублей Item выбирается КАНОНИЧЕСКИЙ (тот, у кого больше
order_count — «реальнее» использовался; при равенстве — с наименьшим id,
т.е. самый старый). Все ссылки с остальных дублей переносятся на него:
  - OrderItem.item      (история заказов НЕ теряется, просто указывает на
                          канонический Item вместо дубля)
  - ItemCategory        (без потери sort_order; при конфликте — дубль просто
                          удаляется, у канонического уже есть эта категория)
  - BranchItem          (+ вложенные BranchCategoryItem), с той же логикой

Отдельно (вторым проходом) чинятся задвоенные BranchItem у УЖЕ уникальных
Item — например, если один и тот же товар случайно дважды привязали к
одному филиалу без задвоения самого Item. Логика слияния та же: остаётся
самый старый BranchItem, его BranchCategoryItem объединяются с дублями.

После переноса всех ссылок дубль становится «пустым» и удаляется.

По умолчанию — DRY RUN (ничего не меняет). Запуск на запись — только с --yes.

Запуск:
    python manage.py merge_duplicate_items                       # предпросмотр (по умолчанию)
    python manage.py merge_duplicate_items --yes                 # реально применить
    python manage.py merge_duplicate_items --yes --restaurant-id 1
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from catalog.models import Item, BranchItem, ItemCategory, BranchCategoryItem
from orders.models import OrderItem


def _merge_branch_item_pair(canon_bi, dup_bi, stdout=None):
    """Переносит BranchCategoryItem дубля на канонический BranchItem, удаляет дубль."""
    for bci in BranchCategoryItem.objects.filter(branch_item=dup_bi):
        exists = BranchCategoryItem.objects.filter(
            branch_item=canon_bi, branch_category=bci.branch_category
        ).exists()
        if exists:
            bci.delete()
        else:
            bci.branch_item = canon_bi
            bci.save(update_fields=["branch_item"])
    dup_bi.delete()


class Command(BaseCommand):
    help = "Объединяет задвоенные Item и BranchItem (см. докстринг файла)"

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true",
                             help="Реально выполнить объединение (по умолчанию — только предпросмотр)")
        parser.add_argument("--restaurant-id", type=int, default=None,
                             help="Ограничить одним рестораном")

    def handle(self, *args, **opts):
        write = opts["yes"]
        rid = opts.get("restaurant_id")

        self._merge_items(write, rid)
        self._merge_branch_items(write, rid)

    def _merge_items(self, write, rid):
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

        if not dupe_groups:
            self.stdout.write(self.style.SUCCESS("Задвоенных Item не найдено."))
            return

        mode = "ВЫПОЛНЯЮ" if write else "[DRY RUN] показываю, что будет сделано"
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{mode} (Item) — {len(dupe_groups)} групп(ы) дублей\n"))

        merged_groups = 0
        for g in dupe_groups:
            rows = list(Item.objects.filter(
                restaurant_id=g["restaurant_id"], name_ru=g["name_ru"]
            ).order_by("-order_count", "id"))

            canonical = rows[0]
            dupes = rows[1:]
            self.stdout.write(
                f"\n«{g['name_ru']}» (restaurant_id={g['restaurant_id']}): "
                f"канонический id={canonical.id} (заказов={canonical.order_count}), "
                f"объединяю {len(dupes)} дубль(ей): {[d.id for d in dupes]}"
            )

            if not write:
                continue

            with transaction.atomic():
                for dup in dupes:
                    # OrderItem — просто переставляем FK, историю не теряем
                    n_orders = OrderItem.objects.filter(item=dup).update(item=canonical)
                    if n_orders:
                        self.stdout.write(f"    переставлено OrderItem: {n_orders}")

                    # ItemCategory — переносим, если у канонического в этой категории
                    # ещё нет записи; иначе просто удаляем дубль (unique_together)
                    for ic in ItemCategory.objects.filter(item=dup):
                        exists = ItemCategory.objects.filter(item=canonical, category_id=ic.category_id).exists()
                        if exists:
                            ic.delete()
                        else:
                            ic.item = canonical
                            ic.save(update_fields=["item"])

                    # BranchItem (+ вложенные BranchCategoryItem)
                    for bi in BranchItem.objects.filter(item=dup):
                        canon_bi = BranchItem.objects.filter(item=canonical, branch=bi.branch).first()
                        if canon_bi is None:
                            bi.item = canonical
                            bi.save(update_fields=["item"])
                        else:
                            # у канонического уже есть BranchItem в этом филиале —
                            # переносим его вложенные BranchCategoryItem и удаляем дубль
                            _merge_branch_item_pair(canon_bi, bi)

                    # Само фото у дубля не переносим намеренно — у канонического
                    # уже есть своё (или он новее). Если у дубля фото было, а у
                    # канонического нет — заполним.
                    if dup.photo and not canonical.photo:
                        canonical.photo = dup.photo
                        canonical.save(update_fields=["photo"])
                        dup.photo = None  # чтобы delete() дубля не снёс файл, который теперь у canonical

                    dup.delete()

            merged_groups += 1

        if write:
            self.stdout.write(self.style.SUCCESS(f"\n✅ Item: объединено групп: {merged_groups}"))
        else:
            self.stdout.write(self.style.WARNING(
                "\n[DRY RUN] Item: ничего не изменено. Запустите с --yes, чтобы применить."
            ))

    def _merge_branch_items(self, write, rid):
        """Второй проход: задвоенные BranchItem (branch+item) у уже уникальных Item —
        например, товар случайно дважды привязали к одному филиалу."""
        bi_qs = BranchItem.objects.all()
        if rid:
            bi_qs = bi_qs.filter(item__restaurant_id=rid)

        dupe_groups = (
            bi_qs.values("branch_id", "item_id")
            .annotate(n=Count("id"))
            .filter(n__gt=1)
            .order_by("branch_id", "item_id")
        )
        dupe_groups = list(dupe_groups)

        if not dupe_groups:
            self.stdout.write(self.style.SUCCESS("Задвоенных BranchItem не найдено."))
            return

        mode = "ВЫПОЛНЯЮ" if write else "[DRY RUN] показываю, что будет сделано"
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{mode} (BranchItem) — {len(dupe_groups)} групп(ы) дублей\n"
        ))

        merged_groups = 0
        for g in dupe_groups:
            rows = list(BranchItem.objects.filter(
                branch_id=g["branch_id"], item_id=g["item_id"]
            ).order_by("-is_available", "id"))

            canon_bi = rows[0]
            dupes = rows[1:]
            item = Item.objects.filter(id=g["item_id"]).first()
            self.stdout.write(
                f"\nbranch_id={g['branch_id']} «{item.name_ru if item else '?'}» (item_id={g['item_id']}): "
                f"канонический BranchItem id={canon_bi.id}, объединяю {len(dupes)} дубль(ей): "
                f"{[d.id for d in dupes]}"
            )

            if not write:
                continue

            with transaction.atomic():
                for dup_bi in dupes:
                    _merge_branch_item_pair(canon_bi, dup_bi)

            merged_groups += 1

        if write:
            self.stdout.write(self.style.SUCCESS(f"\n✅ BranchItem: объединено групп: {merged_groups}"))
        else:
            self.stdout.write(self.style.WARNING(
                "\n[DRY RUN] BranchItem: ничего не изменено. Запустите с --yes, чтобы применить."
            ))
