"""
Создание заданий на печать при оформлении заказа.
Вызывается из dashboard/views.py после сохранения Order.
"""
from collections import defaultdict
from django.utils import timezone

from .models import PrintJob, RestaurantPrintConfig


def _build_ticket(order, items_by_group, group):
    """Генерирует plain-text чек для кухонного принтера."""
    now = timezone.localtime()
    lines = []
    SEP = "-" * 32

    lines.append(SEP)
    lines.append(f"  ЗАКАЗ #{order.id}")
    lines.append(f"  {now.strftime('%d.%m.%Y  %H:%M')}")
    lines.append(f"  {order.get_type_display()}")
    if order.table_place:
        lines.append(f"  Стол: {order.table_place.title}")
    if order.customer_name:
        lines.append(f"  Гость: {order.customer_name}")
    if order.comment:
        lines.append(f"  ! {order.comment}")
    lines.append(SEP)

    for name, qty in items_by_group:
        lines.append(f"  {qty}x  {name}")

    lines.append(SEP)
    lines.append("")  # пустая строка для отрыва бумаги

    return "\n".join(lines)


def create_print_jobs(order):
    """
    Вызывается после создания заказа.
    Группирует позиции по printer_group → создаёт PrintJob на каждую группу.
    """
    restaurant = order.branch.restaurant

    # Проверяем что печать включена
    try:
        cfg = RestaurantPrintConfig.objects.get(restaurant=restaurant, enabled=True)
    except RestaurantPrintConfig.DoesNotExist:
        return

    # Собираем позиции заказа с их printer_group
    # OrderItem → item → BranchCategoryItem → BranchCategory → printer_group
    from orders.models import OrderItem, ConstructorOrderItem
    from catalog.models import BranchCategoryItem

    # Строим маппинг item_id → printer_group
    branch = order.branch
    bci_qs = (
        BranchCategoryItem.objects
        .filter(
            branch_category__branch=branch,
            branch_category__printer_group__isnull=False,
        )
        .select_related("branch_category__printer_group", "branch_item__item")
    )
    item_to_group = {}
    for bci in bci_qs:
        item_to_group[bci.branch_item.item_id] = bci.branch_category.printer_group

    # Группируем позиции
    groups: dict = defaultdict(list)  # PrinterGroup → [(name, qty)]
    ungrouped = []

    for oi in order.items.select_related("item").all():
        group = item_to_group.get(oi.item_id)
        if group:
            groups[group].append((oi.item.name_ru, oi.qty))
        else:
            ungrouped.append((oi.item.name_ru, oi.qty))

    for coi in order.constructor_items.all():
        name = coi.constructor_name_snapshot or "Конструктор"
        ungrouped.append((name, coi.qty))

    # Создаём PrintJob для каждой группы
    jobs = []
    for group, items in groups.items():
        content = _build_ticket(order, items, group)
        jobs.append(PrintJob(
            restaurant=restaurant,
            order_id=order.id,
            group=group,
            content=content,
            status=PrintJob.Status.NEW,
        ))

    # Позиции без группы — в группу по умолчанию (если есть)
    if ungrouped:
        default_group = (
            restaurant.printer_groups
            .filter(name="kitchen")
            .first()
            or restaurant.printer_groups.first()
        )
        if default_group:
            content = _build_ticket(order, ungrouped, default_group)
            jobs.append(PrintJob(
                restaurant=restaurant,
                order_id=order.id,
                group=default_group,
                content=content,
                status=PrintJob.Status.NEW,
            ))

    if jobs:
        PrintJob.objects.bulk_create(jobs)
