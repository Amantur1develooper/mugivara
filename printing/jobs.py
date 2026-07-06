"""
Создание заданий на печать при оформлении заказа.
Вызывается через transaction.on_commit после сохранения Order.

Символы \x02 / \x03 — плейсхолдеры bold-on / bold-off.
PostgreSQL не принимает NUL-байт (\x00), поэтому реальные ESC/POS
коды подставляет агент непосредственно перед отправкой на принтер.
"""
from collections import defaultdict
from django.utils import timezone

from .models import PrintJob, RestaurantPrintConfig


# ── Вспомогательные константы ────────────────────────────────────────────────

SEP  = "-" * 32
SEP2 = "=" * 32

# Плейсхолдеры жирного текста (агент заменит на ESC E 1 / ESC E 0)
_BOLD  = "\x02"
_RESET = "\x03"


# ── Построение текста тикета ─────────────────────────────────────────────────

def _ticket(order, items):
    """
    Кухонный тикет.
    items = [(name, qty), ...] или [(name, qty, ingredient_lines), ...]
    ingredient_lines — список строк с составом (для заказов «собери сам»).
    """
    now = timezone.localtime()

    parts = [order.get_type_display()]
    try:
        if order.table_place:
            floor_name = getattr(getattr(order.table_place, "floor", None), "name_ru", "") or ""
            table_str = f"Стол {order.table_place.title}"
            if floor_name:
                table_str += f"  |  Зал {floor_name}"
            parts.append(table_str)
    except Exception as e:
        print("PRINT _ticket table_place ERROR:", e)
    info = "  |  ".join(parts)

    lines = [
        SEP,
        f"{_BOLD}  ЗАКАЗ #{order.id}   {now.strftime('%d.%m  %H:%M')}{_RESET}",
        f"  {info}",
    ]
    if order.customer_name:
        lines.append(f"  Гость: {order.customer_name}")
    if order.comment:
        lines.append(f"  ! {order.comment}")

    lines.append(SEP)
    for row in items:
        name, qty = row[0], row[1]
        ingredient_lines = row[2] if len(row) > 2 else None
        lines.append(f"  {qty}x  {name}")
        if ingredient_lines:
            for ing_line in ingredient_lines:
                lines.append(f"      {ing_line}")
    lines.append(SEP)
    lines.append("")

    return "\n".join(lines)


def _cancel_ticket(order, item_name, item_qty):
    now = timezone.localtime()
    lines = [
        SEP2,
        f"{_BOLD}  !! ОТМЕНА !!{_RESET}",
        f"  Заказ #{order.id}   {now.strftime('%d.%m  %H:%M')}",
    ]
    if order.table_place:
        lines.append(f"  Стол: {order.table_place.title}")
    lines += [SEP2, f"  ОТМЕНЕНО: {item_qty}x  {item_name}", SEP2, ""]
    return "\n".join(lines)


def _receipt_ticket(order, restaurant):
    now = timezone.localtime()
    pm  = "Наличные" if order.payment_method == "cash" else "Карта"
    lines = [
        SEP2,
        f"  {restaurant.name_ru}  |  {order.branch.name_ru}",
        SEP2,
        f"{_BOLD}  ЧЕК #{order.id}{_RESET}   {now.strftime('%d.%m.%Y  %H:%M')}",
    ]
    if order.table_place:
        lines.append(f"  Стол: {order.table_place.title}")
    if order.customer_name:
        lines.append(f"  Гость: {order.customer_name}")
    lines.append(SEP)

    for oi in order.items.select_related("item").all():
        lines.append(f"  {oi.item.name_ru}")
        lines.append(f"    {oi.qty} x {oi.price_snapshot:.0f} = {oi.line_total:.0f} сом")

    for coi in order.constructor_items.all():
        lines.append(f"  {coi.constructor_name_snapshot or 'Конструктор'}")
        lines.append(f"    {coi.qty} x {coi.unit_price:.0f} = {coi.line_total:.0f} сом")

    lines += [
        SEP,
        f"{_BOLD}  ИТОГО: {order.total_amount:.0f} сом{_RESET}",
        f"  Оплата: {pm}",
        SEP2,
        "      Спасибо за визит!",
        "",
    ]
    return "\n".join(lines)


# ── Вспомогательные функции ──────────────────────────────────────────────────

def _print_enabled(restaurant):
    """True если для ресторана включена облачная печать."""
    return RestaurantPrintConfig.objects.filter(
        restaurant=restaurant, enabled=True
    ).exists()


def _default_group(restaurant):
    """Дефолтная группа принтеров: сначала ищем 'kitchen', потом первую доступную."""
    return (
        restaurant.printer_groups.filter(name="kitchen").first()
        or restaurant.printer_groups.first()
    )


def _item_group_map(branch):
    """Возвращает {item_id: PrinterGroup} по настройкам ветки."""
    from catalog.models import BranchCategoryItem
    mapping = {}
    qs = (
        BranchCategoryItem.objects
        .filter(branch_category__branch=branch)
        .select_related(
            "printer_group",
            "branch_category__printer_group",
            "branch_item__item",
        )
    )
    for bci in qs:
        grp = bci.printer_group or bci.branch_category.printer_group
        if grp:
            mapping[bci.branch_item.item_id] = grp
    return mapping


# ── Публичные функции ────────────────────────────────────────────────────────

def create_print_jobs(order, new_item_ids=None, new_cx_ids=None):
    """
    Создаёт PrintJob для каждой группы принтеров по позициям заказа.

    new_item_ids  — список ID OrderItem, которые нужно напечатать.
                    None = все позиции заказа (новый заказ).
    new_cx_ids    — список ID ConstructorOrderItem аналогично.
    """
    print(f"PRINT DEBUG: create_print_jobs вызван для заказа #{order.id}")
    restaurant = order.branch.restaurant

    if not _print_enabled(restaurant):
        print(f"PRINT DEBUG: печать отключена для ресторана '{restaurant}' — выходим")
        return

    item_group = _item_group_map(order.branch)

    # Выбираем нужные позиции
    oi_qs = order.items.select_related("item")
    if new_item_ids is not None:
        oi_qs = oi_qs.filter(id__in=new_item_ids)

    cx_qs = order.constructor_items.all()
    if new_cx_ids is not None:
        cx_qs = cx_qs.filter(id__in=new_cx_ids)

    # Группируем по принтерам
    by_group  = defaultdict(list)
    no_group  = []

    for oi in oi_qs:
        grp = item_group.get(oi.item_id)
        if grp:
            by_group[grp].append((oi.item.name_ru, oi.qty))
        else:
            no_group.append((oi.item.name_ru, oi.qty))

    for coi in cx_qs:
        ing_lines = []
        for sel in (coi.ingredients_snapshot or []):
            ings = sel.get("ings") or []
            if ings:
                gname = sel.get("gname", "")
                names = ", ".join(i.get("name", "") for i in ings if i.get("name"))
                if names:
                    ing_lines.append(f"{gname}: {names}" if gname else names)
        no_group.append((coi.constructor_name_snapshot or "Собери сам", coi.qty, ing_lines))

    # Позиции без группы → дефолтная группа
    if no_group:
        default = _default_group(restaurant)
        print(f"PRINT DEBUG: no_group={len(no_group)} позиций, default_group={default}")
        if default:
            by_group[default].extend(no_group)

    if not by_group:
        print(f"PRINT DEBUG: by_group пустой — нет групп принтеров, PrintJob не создан")
        return

    jobs = PrintJob.objects.bulk_create([
        PrintJob(
            restaurant=restaurant,
            order_id=order.id,
            group=grp,
            content=_ticket(order, items),
            status=PrintJob.Status.NEW,
        )
        for grp, items in by_group.items()
    ])
    print(f"PRINT DEBUG: создано {len(jobs)} PrintJob для заказа #{order.id}, группы: {[str(grp) for grp in by_group]}")


def _create_job(restaurant, order, group, content):
    """Создаёт и сохраняет один PrintJob."""
    PrintJob.objects.create(
        restaurant=restaurant,
        order_id=order.id,
        group=group,
        content=content,
        status=PrintJob.Status.NEW,
    )


def create_cancel_job(order, item_name: str, item_qty: int, item_id: int = None):
    """Печатает тикет отмены блюда."""
    restaurant = order.branch.restaurant

    if not _print_enabled(restaurant):
        return

    target = None
    if item_id:
        from catalog.models import BranchCategoryItem
        bci = (
            BranchCategoryItem.objects
            .filter(branch_category__branch=order.branch, branch_item__item_id=item_id)
            .select_related("printer_group", "branch_category__printer_group")
            .first()
        )
        if bci:
            target = bci.printer_group or bci.branch_category.printer_group

    if not target:
        target = _default_group(restaurant)

    if not target:
        return

    _create_job(restaurant, order, target, _cancel_ticket(order, item_name, item_qty))


def create_receipt_job(order):
    """Печатает итоговый чек при закрытии стола."""
    print(f"PRINT DEBUG: create_receipt_job вызван для заказа #{order.id}")
    restaurant = order.branch.restaurant

    try:
        cfg = (
            RestaurantPrintConfig.objects
            .select_related("receipt_printer_group")
            .get(restaurant=restaurant, enabled=True)
        )
    except RestaurantPrintConfig.DoesNotExist:
        print(f"PRINT DEBUG: RestaurantPrintConfig не найден или выключен для '{restaurant}' — чек не напечатан")
        return

    group = cfg.receipt_printer_group or _default_group(restaurant)
    if not group:
        print(f"PRINT DEBUG: нет группы принтеров для чека у ресторана '{restaurant}'")
        return

    print(f"PRINT DEBUG: создаём PrintJob чека для заказа #{order.id}, группа: {group}")
    _create_job(restaurant, order, group, _receipt_ticket(order, restaurant))
