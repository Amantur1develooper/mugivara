# -*- coding: utf-8 -*-
"""Часы подачи блюд: завтраки до 11:00, ночное меню после 22:00.

Окно можно задать разделу («Завтраки» целиком) и отдельному блюду. Блюдо
доступно, когда позволяют оба: своё окно и окно хотя бы одного раздела,
в котором оно лежит.
"""
from django.utils import timezone


def now_time():
    return timezone.localtime().time()


def item_window(branch_item, branch_categories=None):
    """(доступно сейчас, текст окна) для блюда филиала.

    branch_categories — разделы, в которых блюдо показано; если не передать,
    достанем из базы. Передавайте, когда рисуете меню: иначе на каждое блюдо
    уйдёт лишний запрос.
    """
    moment = now_time()

    if branch_item.has_serving_window:
        return branch_item.is_servable_at(moment), branch_item.serving_window_text

    if branch_categories is None:
        from .models import BranchCategory
        branch_categories = list(
            BranchCategory.objects.filter(
                items_in_category__branch_item=branch_item, is_active=True
            ).distinct()
        )

    limited = [bc for bc in branch_categories if bc.has_serving_window]
    if not limited or len(limited) < len(branch_categories):
        # хотя бы один раздел без ограничения — блюдо доступно всегда
        return True, ""

    open_now = [bc for bc in limited if bc.is_servable_at(moment)]
    if open_now:
        return True, ""
    # закрыты все разделы: показываем окно ближайшего по времени начала
    text = sorted(limited, key=lambda bc: bc.available_from or bc.available_to)[0]
    return False, text.serving_window_text


def closed_message(window_text):
    return f"Это блюдо подаём {window_text}" if window_text else "Сейчас это блюдо не подаём"
