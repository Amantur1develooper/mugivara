"""Почему товар не виден в магазине — разбор по одному филиалу или по всей сети.

Отвечает на жалобу «добавил категорию и товары, а их нет»: показывает, где
именно товар выпал из показа — нет категории, категория выключена, товар
выключен, товар только для «Собери сам», нулевой остаток (тогда его не видно
в кассе) или товара просто нет в этом филиале, хотя он есть в соседнем.

    python manage.py find_lost_products --branch 47
    python manage.py find_lost_products --store 12
    python manage.py find_lost_products --branch 47 --fix-categories
"""
from django.core.management.base import BaseCommand, CommandError

from shops.models import Store, StoreBranch, StoreStock


def _line(n, text):
    return f"  {n:>4}  {text}"


class Command(BaseCommand):
    help = "Показывает товары, которые не видны на витрине или в кассе, и объясняет почему"

    def add_arguments(self, parser):
        parser.add_argument("--branch", type=int, help="id филиала")
        parser.add_argument("--store", type=int, help="id магазина (все филиалы)")
        parser.add_argument(
            "--fix-categories", action="store_true",
            help="включить обратно выключенные категории, в которых есть товары",
        )

    def handle(self, *args, **opts):
        if opts["branch"]:
            branches = list(StoreBranch.objects.filter(id=opts["branch"]).select_related("store"))
        elif opts["store"]:
            branches = list(
                StoreBranch.objects.filter(store_id=opts["store"]).select_related("store").order_by("id")
            )
        else:
            raise CommandError("Укажите --branch <id> или --store <id>")
        if not branches:
            raise CommandError("Филиал/магазин не найден")

        store = branches[0].store
        for branch in branches:
            self._report(branch)

        # Товары магазина, у которых вообще нет остатка ни в одном филиале —
        # такие не видно нигде, кроме админки.
        orphans = (
            store.products.filter(is_active=True, stocks__isnull=True)
            .order_by("name_ru").values_list("id", "name_ru")
        )
        if orphans:
            self.stdout.write(self.style.WARNING(
                f"\nТовары магазина «{store.name_ru}» без остатка ни в одном филиале "
                f"({len(orphans)}) — их не видно ни на витрине, ни в кассе:"
            ))
            for pid, name in orphans[:50]:
                self.stdout.write(_line(pid, name))

        if opts["fix_categories"]:
            fixed = 0
            for branch in branches:
                cat_ids = {
                    s.product.category_id
                    for s in StoreStock.objects.filter(branch=branch).select_related("product")
                    if s.product.category_id
                }
                fixed += store.categories.filter(id__in=cat_ids, is_active=False).update(is_active=True)
            self.stdout.write(self.style.SUCCESS(f"\nВключено обратно категорий: {fixed}"))

    def _report(self, branch):
        stocks = list(
            StoreStock.objects.filter(branch=branch)
            .select_related("product", "product__category")
            .order_by("product__name_ru")
        )
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n=== Филиал {branch.id}: {branch.name_ru} "
            f"({branch.store.name_ru}) — товаров: {len(stocks)} ==="
        ))
        if not branch.is_active:
            self.stdout.write(self.style.ERROR(
                "  Филиал выключен — витрина этого филиала недоступна покупателям."
            ))

        buckets = {
            "нет категории (раньше такой товар не попадал на витрину)": [],
            "категория выключена — товар не на витрине": [],
            "товар выключен (is_active=False)": [],
            "только для «Собери сам» (sell_direct=False)": [],
            "нулевой остаток — не видно в кассе": [],
        }
        for s in stocks:
            p = s.product
            if not p.is_active:
                buckets["товар выключен (is_active=False)"].append(s)
                continue
            if not p.sell_direct:
                buckets["только для «Собери сам» (sell_direct=False)"].append(s)
                continue
            if p.category_id is None:
                buckets["нет категории (раньше такой товар не попадал на витрину)"].append(s)
            elif not p.category.is_active:
                buckets["категория выключена — товар не на витрине"].append(s)
            if s.qty <= 0 and not p.unlimited:
                buckets["нулевой остаток — не видно в кассе"].append(s)

        clean = True
        for title, rows in buckets.items():
            if not rows:
                continue
            clean = False
            self.stdout.write(self.style.WARNING(f"\n  {title} — {len(rows)}:"))
            for s in rows[:50]:
                cat = s.product.category.name_ru if s.product.category_id else "—"
                self.stdout.write(_line(s.product_id, f"{s.product.name_ru}  [{cat}]  остаток {s.qty}"))
            if len(rows) > 50:
                self.stdout.write(f"       … и ещё {len(rows) - 50}")

        if clean:
            self.stdout.write("  Все товары этого филиала видны и на витрине, и в кассе.")

        # Пустые категории магазина: в кабинете видно, на витрине нет — частая
        # причина жалобы «категорию добавил, а в магазине её не видно».
        empty = []
        used = {s.product.category_id for s in stocks if s.product.category_id}
        for cat in branch.store.categories.order_by("sort_order", "id"):
            if cat.id not in used:
                empty.append(cat)
        if empty:
            self.stdout.write(self.style.WARNING(
                f"\n  Категории без товаров в этом филиале — {len(empty)} "
                "(на витрине они не показываются):"
            ))
            for cat in empty:
                flag = "" if cat.is_active else "  (выключена)"
                self.stdout.write(_line(cat.id, f"{cat.name_ru}{flag}"))
