# -*- coding: utf-8 -*-
"""Проставляет существующим настройкам печати все филиалы ресторана.

Поле branches появилось, чтобы агент одной точки не печатал чеки другой.
Но выбрать «правильный» филиал за владельца нельзя: в базе не записано,
где физически стоит принтер. Поэтому при обновлении отмечаем все филиалы —
печать продолжает работать ровно как раньше, ничего не ломается, — а в
кабинете у ресторанов с несколькими точками появляется предупреждение
с просьбой оставить галочку только там, где принтер есть.
"""
from django.db import migrations


def fill(apps, schema_editor):
    Config = apps.get_model("printing", "RestaurantPrintConfig")
    Branch = apps.get_model("core", "Branch")
    for cfg in Config.objects.all():
        if cfg.branches.exists():
            continue
        ids = list(Branch.objects.filter(restaurant_id=cfg.restaurant_id)
                   .values_list("id", flat=True))
        if ids:
            cfg.branches.set(ids)

    # Непечатанные задания помним по филиалу заказа: иначе после настройки
    # агента зависшая очередь всё равно уехала бы не на ту точку.
    PrintJob = apps.get_model("printing", "PrintJob")
    Order = apps.get_model("orders", "Order")
    pending = PrintJob.objects.filter(status="new", branch__isnull=True)
    order_ids = [j.order_id for j in pending if j.order_id]
    if not order_ids:
        return
    by_order = dict(Order.objects.filter(id__in=order_ids)
                    .values_list("id", "branch_id"))
    for job in pending:
        branch_id = by_order.get(job.order_id)
        if branch_id:
            PrintJob.objects.filter(pk=job.pk).update(branch_id=branch_id)


def unfill(apps, schema_editor):
    Config = apps.get_model("printing", "RestaurantPrintConfig")
    for cfg in Config.objects.all():
        cfg.branches.clear()


class Migration(migrations.Migration):
    dependencies = [
        ("printing", "0003_printjob_branch_restaurantprintconfig_branches"),
        ("core", "0001_initial"),
        ("orders", "0001_initial"),
    ]
    operations = [migrations.RunPython(fill, unfill)]
