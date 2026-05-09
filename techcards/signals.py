from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal


@receiver(post_save, sender="orders.Order")
def deduct_ingredients_on_close(sender, instance, **kwargs):
    """When an order is closed, deduct ingredients from stock for each ordered dish that has a tech card."""
    if instance.status != "closed":
        return

    from orders.models import OrderItem
    from techcards.models import TechCard, IngredientStock, StockMovement

    # Collect (ingredient, qty) to deduct — aggregate across all items in order
    deductions = {}  # ingredient_id -> qty

    items = instance.items.select_related("item").all()
    for oi in items:
        try:
            tc = TechCard.objects.get(item=oi.item, branch=instance.branch, is_active=True)
        except TechCard.DoesNotExist:
            continue

        # Scale by order qty and yield
        scale = Decimal(str(oi.qty)) / (tc.yield_qty or Decimal("1"))
        for line in tc.ingredients.select_related("ingredient").all():
            if not line.ingredient_id:
                continue
            net = (line.net_qty * scale).quantize(Decimal("0.001"))
            deductions[line.ingredient_id] = deductions.get(line.ingredient_id, Decimal("0")) + net

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
