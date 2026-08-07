from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal


@receiver(post_save, sender="orders.Order")
def handle_order_stock(sender, instance, **kwargs):
    """Deduct ingredients on close; return them on cancellation."""
    if instance.status == "cancelled":
        _return_ingredients(instance)
    elif instance.status == "closed":
        _deduct_ingredients(instance)


def _return_ingredients(order):
    """Return ingredients to stock when an order is cancelled."""
    from techcards.models import IngredientStock, StockMovement

    # Prevent double-return if already processed
    if StockMovement.objects.filter(order=order, move_type=StockMovement.TYPE_RETURN).exists():
        return

    sale_movements = StockMovement.objects.filter(
        order=order, move_type=StockMovement.TYPE_SALE
    )
    if not sale_movements.exists():
        return

    for movement in sale_movements:
        return_qty = abs(movement.qty)
        stock, _ = IngredientStock.objects.get_or_create(
            branch=order.branch,
            ingredient=movement.ingredient,
            defaults={"qty": Decimal("0"), "cost_per_unit": Decimal("0")},
        )
        stock.qty += return_qty
        stock.save(update_fields=["qty", "updated_at"])

        StockMovement.objects.create(
            branch=order.branch,
            ingredient=movement.ingredient,
            qty=return_qty,
            move_type=StockMovement.TYPE_RETURN,
            order=order,
            note="Возврат при отмене заказа",
        )


def _deduct_ingredients(order):
    """Deduct ingredients from stock when an order is closed."""

    from orders.models import OrderItem
    from techcards.models import TechCard, IngredientStock, StockMovement

    deductions = {}  # ingredient_id -> Decimal qty

    # ── Обычные блюда через техкарты ─────────────────────────────────────────
    for oi in order.items.select_related("item").all():
        try:
            tc = TechCard.objects.get(item=oi.item, branch=order.branch, is_active=True)
        except TechCard.DoesNotExist:
            continue
        scale = Decimal(str(oi.qty)) / (tc.yield_qty or Decimal("1"))
        for line in tc.ingredients.select_related("ingredient").all():
            if not line.ingredient_id:
                continue
            net = (line.net_qty * scale).quantize(Decimal("0.001"))
            deductions[line.ingredient_id] = deductions.get(line.ingredient_id, Decimal("0")) + net

    # ── Конструктор (Собери сам) ──────────────────────────────────────────────
    # Приоритет: 1) прямая привязка warehouse_ingredient + write_off_qty
    #            2) техкарта привязанного branch_item (если есть)
    try:
        from catalog.models import ConstructorIngredient
        for coi in order.constructor_items.all():
            order_qty = Decimal(str(coi.qty))
            for sel in (coi.ingredients_snapshot or []):
                for ing_entry in sel.get("ings", []):
                    ci_id = ing_entry.get("id")
                    if not ci_id:
                        continue
                    try:
                        ci = ConstructorIngredient.objects.select_related(
                            "warehouse_ingredient",
                            "branch_item__item",
                        ).get(id=ci_id)
                    except ConstructorIngredient.DoesNotExist:
                        continue

                    ing_qty = Decimal(str(ing_entry.get("qty", 1)))

                    if ci.warehouse_ingredient_id:
                        # ── Вариант 1: прямое списание ────────────────────────
                        total = (ci.write_off_qty * ing_qty * order_qty).quantize(Decimal("0.001"))
                        deductions[ci.warehouse_ingredient_id] = (
                            deductions.get(ci.warehouse_ingredient_id, Decimal("0")) + total
                        )

                    elif ci.branch_item_id:
                        # ── Вариант 2: техкарта блюда из меню ────────────────
                        try:
                            tc = TechCard.objects.get(
                                item=ci.branch_item.item,
                                branch=order.branch,
                                is_active=True,
                            )
                        except TechCard.DoesNotExist:
                            continue
                        scale = (ing_qty * order_qty) / (tc.yield_qty or Decimal("1"))
                        for line in tc.ingredients.select_related("ingredient").all():
                            if not line.ingredient_id:
                                continue
                            net = (line.net_qty * scale).quantize(Decimal("0.001"))
                            deductions[line.ingredient_id] = (
                                deductions.get(line.ingredient_id, Decimal("0")) + net
                            )
    except Exception:
        pass

    # ── Применяем списание ────────────────────────────────────────────────────
    for ing_id, qty in deductions.items():
        stock, _ = IngredientStock.objects.get_or_create(
            branch=order.branch,
            ingredient_id=ing_id,
            defaults={"qty": Decimal("0"), "cost_per_unit": Decimal("0")},
        )
        stock.qty = max(Decimal("0"), stock.qty - qty)
        stock.save(update_fields=["qty", "updated_at"])

        StockMovement.objects.create(
            branch=order.branch,
            ingredient_id=ing_id,
            qty=-qty,
            move_type=StockMovement.TYPE_SALE,
            order=order,
        )
