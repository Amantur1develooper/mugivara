from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal


@receiver(post_save, sender="orders.Order")
def deduct_ingredients_on_close(sender, instance, **kwargs):
    """When an order is closed, deduct ingredients from stock."""
    if instance.status != "closed":
        return

    from orders.models import OrderItem
    from techcards.models import TechCard, IngredientStock, StockMovement

    deductions = {}  # ingredient_id -> Decimal qty

    # ── Обычные блюда через техкарты ─────────────────────────────────────────
    for oi in instance.items.select_related("item").all():
        try:
            tc = TechCard.objects.get(item=oi.item, branch=instance.branch, is_active=True)
        except TechCard.DoesNotExist:
            continue
        scale = Decimal(str(oi.qty)) / (tc.yield_qty or Decimal("1"))
        for line in tc.ingredients.select_related("ingredient").all():
            if not line.ingredient_id:
                continue
            net = (line.net_qty * scale).quantize(Decimal("0.001"))
            deductions[line.ingredient_id] = deductions.get(line.ingredient_id, Decimal("0")) + net

    # ── Конструктор (Собери сам) — списание по прямой привязке ───────────────
    try:
        from catalog.models import ConstructorIngredient
        for coi in instance.constructor_items.all():
            for sel in (coi.ingredients_snapshot or []):
                for ing_entry in sel.get("ings", []):
                    ci_id = ing_entry.get("id")
                    if not ci_id:
                        continue
                    try:
                        ci = ConstructorIngredient.objects.select_related(
                            "warehouse_ingredient"
                        ).get(id=ci_id)
                    except ConstructorIngredient.DoesNotExist:
                        continue
                    if not ci.warehouse_ingredient_id:
                        continue
                    ing_qty = Decimal(str(ing_entry.get("qty", 1)))
                    total = (ci.write_off_qty * ing_qty * Decimal(str(coi.qty))).quantize(Decimal("0.001"))
                    deductions[ci.warehouse_ingredient_id] = (
                        deductions.get(ci.warehouse_ingredient_id, Decimal("0")) + total
                    )
    except Exception:
        pass

    # ── Применяем списание ────────────────────────────────────────────────────
    for ing_id, qty in deductions.items():
        stock, _ = IngredientStock.objects.get_or_create(
            branch=instance.branch,
            ingredient_id=ing_id,
            defaults={"qty": Decimal("0"), "cost_per_unit": Decimal("0")},
        )
        stock.qty = max(Decimal("0"), stock.qty - qty)
        stock.save(update_fields=["qty", "updated_at"])

        StockMovement.objects.create(
            branch=instance.branch,
            ingredient_id=ing_id,
            qty=-qty,
            move_type=StockMovement.TYPE_SALE,
            order=instance,
        )
