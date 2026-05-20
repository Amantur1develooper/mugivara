"""
Создание заданий на печать при оформлении заказа.
Вызывается из dashboard/views.py после сохранения Order.
"""
from collections import defaultdict
from django.utils import timezone

from .models import PrintJob, RestaurantPrintConfig

# ESC/POS inline bold (cp866-safe ASCII control bytes)
_B  = "\x1b\x45\x01"   # bold on
_B_ = "\x1b\x45\x00"   # bold off

SEP  = "-" * 40
SEP2 = "=" * 40


def _build_ticket(order, items_by_group, group):
    """Кухонный тикет — компактный, читаемый формат."""
    now = timezone.localtime()
    lines = []

    lines.append(SEP)

    # Строка 1: номер заказа + время
    lines.append(f"{_B}  ЗАКАЗ #{order.id}  {now.strftime('%d.%m  %H:%M')}{_B_}")

    # Строка 2: тип + стол (через разделитель если оба есть)
    parts = [order.get_type_display()]
    if order.table_place:
        parts.append(f"Стол: {order.table_place.title}")
    lines.append("  " + "  |  ".join(parts))

    if order.customer_name:
        lines.append(f"  Гость: {order.customer_name}")
    if order.comment:
        lines.append(f"  ! {order.comment}")

    lines.append(SEP)

    for name, qty in items_by_group:
        lines.append(f"  {qty}x  {name}")

    lines.append(SEP)
    lines.append("")

    return "\n".join(lines)


def create_print_jobs(order, new_order_item_ids=None, new_cx_item_ids=None):
    """
    Вызывается после создания/дополнения заказа.
    Группирует позиции по printer_group → создаёт PrintJob на каждую группу.

    new_order_item_ids / new_cx_item_ids — если переданы, печатаем ТОЛЬКО эти
    позиции (дозаказ к уже открытому столу). Иначе — все позиции заказа.
    """
    restaurant = order.branch.restaurant
    print(f"PRINT DEBUG: order={order.id} restaurant={restaurant.name_ru} branch={order.branch.name_ru}")

    # Проверяем что печать включена
    try:
        cfg = RestaurantPrintConfig.objects.get(restaurant=restaurant, enabled=True)
        print(f"PRINT DEBUG: config found, enabled=True")
    except RestaurantPrintConfig.DoesNotExist:
        print(f"PRINT DEBUG: RestaurantPrintConfig не найден или enabled=False для '{restaurant.name_ru}' — печать пропущена")
        return

    from orders.models import OrderItem, ConstructorOrderItem
    from catalog.models import BranchCategoryItem

    # Строим маппинг item_id → printer_group
    # Приоритет: принтер блюда > принтер категории
    branch = order.branch
    bci_qs = (
        BranchCategoryItem.objects
        .filter(branch_category__branch=branch)
        .select_related(
            "printer_group",
            "branch_category__printer_group",
            "branch_item__item",
        )
    )
    item_to_group = {}
    for bci in bci_qs:
        group = bci.printer_group or bci.branch_category.printer_group
        if group:
            item_to_group[bci.branch_item.item_id] = group

    # Выбираем только новые позиции (если указаны ID) или все
    oi_qs = order.items.select_related("item")
    if new_order_item_ids is not None:
        oi_qs = oi_qs.filter(id__in=new_order_item_ids)

    cx_qs = order.constructor_items.all()
    if new_cx_item_ids is not None:
        cx_qs = cx_qs.filter(id__in=new_cx_item_ids)

    # Группируем позиции
    groups: dict = defaultdict(list)  # PrinterGroup → [(name, qty)]
    ungrouped = []

    for oi in oi_qs:
        group = item_to_group.get(oi.item_id)
        if group:
            groups[group].append((oi.item.name_ru, oi.qty))
        else:
            ungrouped.append((oi.item.name_ru, oi.qty))

    for coi in cx_qs:
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
    print(f"PRINT DEBUG: grouped={len(groups)} ungrouped={len(ungrouped)}")
    if ungrouped:
        default_group = (
            restaurant.printer_groups
            .filter(name="kitchen")
            .first()
            or restaurant.printer_groups.first()
        )
        print(f"PRINT DEBUG: default_group={default_group}")
        if default_group:
            content = _build_ticket(order, ungrouped, default_group)
            jobs.append(PrintJob(
                restaurant=restaurant,
                order_id=order.id,
                group=default_group,
                content=content,
                status=PrintJob.Status.NEW,
            ))

    print(f"PRINT DEBUG: создаётся {len(jobs)} PrintJob(s)")
    if jobs:
        PrintJob.objects.bulk_create(jobs)
        print(f"PRINT DEBUG: PrintJob сохранены в БД ✓")


def create_cancel_job(order, item_name: str, item_qty: int, item_id: int = None):
    """
    Печатает тикет ОТМЕНЫ блюда на принтер, назначенный этому блюду/категории.
    Приоритет: принтер блюда > принтер категории > дефолтная группа.
    item_id=None означает конструктор — отправляем на дефолтную группу.
    """
    from catalog.models import BranchCategoryItem

    restaurant = order.branch.restaurant
    try:
        cfg = RestaurantPrintConfig.objects.get(restaurant=restaurant, enabled=True)
    except RestaurantPrintConfig.DoesNotExist:
        return

    # Определяем целевую группу принтеров
    target_group = None
    if item_id:
        bci = (
            BranchCategoryItem.objects
            .filter(branch_category__branch=order.branch, branch_item__item_id=item_id)
            .select_related("printer_group", "branch_category__printer_group")
            .first()
        )
        if bci:
            target_group = bci.printer_group or bci.branch_category.printer_group

    if not target_group:
        # Дефолтная группа (кухня)
        target_group = (
            restaurant.printer_groups.filter(name="kitchen").first()
            or restaurant.printer_groups.first()
        )

    if not target_group:
        return

    now = timezone.localtime()
    lines = [
        SEP2,
        f"{_B}  !! ОТМЕНА !!{_B_}",
        f"  Заказ #{order.id}   {now.strftime('%d.%m  %H:%M')}",
    ]
    if order.table_place:
        lines.append(f"  Стол: {order.table_place.title}")
    lines.append(SEP2)
    lines.append(f"  ОТМЕНЕНО: {item_qty}x  {item_name}")
    lines.append(SEP2)
    lines.append("")

    PrintJob.objects.create(
        restaurant=restaurant,
        order_id=order.id,
        group=target_group,
        content="\n".join(lines),
        status=PrintJob.Status.NEW,
    )


def create_receipt_job(order):
    """
    Печатает итоговый чек покупателя при закрытии стола/заказа.
    Принтер берётся из настроек ресторана (receipt_printer_group).
    Fallback: первая доступная группа.
    """
    restaurant = order.branch.restaurant
    try:
        cfg = (RestaurantPrintConfig.objects
               .select_related("receipt_printer_group")
               .get(restaurant=restaurant, enabled=True))
    except RestaurantPrintConfig.DoesNotExist:
        return

    # Явно назначенный принтер чеков имеет приоритет
    group = cfg.receipt_printer_group or restaurant.printer_groups.first()
    if not group:
        return

    now = timezone.localtime()
    lines = []

    lines.append(SEP2)
    lines.append(f"  {restaurant.name_ru}  |  {order.branch.name_ru}")
    lines.append(SEP2)
    lines.append(f"{_B}  ЧЕК #{order.id}{_B_}   {now.strftime('%d.%m.%Y  %H:%M')}")
    if order.table_place:
        lines.append(f"  Стол: {order.table_place.title}")
    if order.customer_name:
        lines.append(f"  Гость: {order.customer_name}")
    lines.append(SEP)

    for oi in order.items.select_related("item").all():
        name = oi.item.name_ru
        lines.append(f"  {name}")
        lines.append(f"    {oi.qty} x {oi.price_snapshot:.0f} = {oi.line_total:.0f} сом")

    for coi in order.constructor_items.all():
        name = coi.constructor_name_snapshot or "Конструктор"
        lines.append(f"  {name}")
        lines.append(f"    {coi.qty} x {coi.unit_price:.0f} = {coi.line_total:.0f} сом")

    lines.append(SEP)
    pm = "Наличные" if order.payment_method == "cash" else "Карта"
    lines.append(f"{_B}  ИТОГО: {order.total_amount:.0f} сом{_B_}")
    lines.append(f"  Оплата: {pm}")
    lines.append(SEP2)
    lines.append("      Спасибо за визит!")
    lines.append("")

    PrintJob.objects.create(
        restaurant=restaurant,
        order_id=order.id,
        group=group,
        content="\n".join(lines),
        status=PrintJob.Status.NEW,
    )
