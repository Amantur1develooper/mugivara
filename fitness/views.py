# -*- coding: utf-8 -*-
"""Публичная часть клуба: секции, тренеры, запись и заявка."""
from datetime import datetime, timedelta

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from urllib.parse import quote

from core.phones import normalize as _normalize_phone
from core.phones import wa_digits
from integrations import tgbot

from . import tg
from .models import FitnessClub, Lead, Section, Trainer, TrainerBooking


def _wa_link(club, lines):
    """Ссылка на WhatsApp клуба с готовым текстом заявки.

    Клубу удобнее разговаривать в WhatsApp, а не ждать, пока кто-то
    откроет кабинет: заявка всё равно сохраняется, но человек сразу
    попадает в переписку с готовым сообщением. Номер берём рабочий, а
    если он не заполнен — обычный телефон клуба.
    """
    digits = wa_digits(club.whatsapp) or wa_digits(club.phone)
    if not digits:
        return ""
    text = "\n".join(x for x in lines if x)
    return f"https://wa.me/{digits}?text={quote(text)}"

def _phone(raw):
    """Номер в едином виде или («», ошибка).

    normalize() возвращает пару (номер, ошибка) — её легко принять за
    строку и записать кортеж в базу, что однажды и произошло.
    """
    phone, err = _normalize_phone(raw or "")
    return phone, err

def club_list(request):
    clubs = (FitnessClub.objects.filter(is_active=True)
             .prefetch_related("sections")
             .order_by("sort_order", "name"))
    return render(request, "fitness/public/list.html", {"clubs": clubs})


def club_page(request, slug):
    club = get_object_or_404(FitnessClub, slug=slug, is_active=True)
    sections = club.sections.filter(is_active=True).order_by("sort_order", "id")
    trainers = (club.trainers.filter(is_active=True)
                .prefetch_related("sections").order_by("sort_order", "id"))
    plans = club.plans.filter(is_active=True).order_by("sort_order", "id")
    return render(request, "fitness/public/club.html", {
        "club": club, "sections": sections, "trainers": trainers, "plans": plans,
        "days": _next_days(),
        "schedule_days": _week_schedule(club),
    })


def _week_schedule(club):
    """Расписание групповых занятий на неделю вперёд со свободными местами."""
    from django.db.models import Count, Q

    from .models import ClassBooking, ClassDay, GroupClass

    today = timezone.localdate()
    days = [today + timedelta(days=i) for i in range(7)]
    classes = list(GroupClass.objects.filter(club=club, is_active=True)
                   .select_related("trainer", "group")
                   .annotate(group_size=Count("group__links",
                                              filter=Q(group__links__is_active=True),
                                              distinct=True))
                   .order_by("time_from", "id"))
    if not classes:
        return []

    # Занятость считаем одним запросом на всю неделю: иначе страница клуба
    # делает по запросу на каждое занятие каждого дня.
    taken = {}
    for row in (ClassBooking.objects
                .filter(group_class__in=classes, date__in=days)
                .exclude(status=ClassBooking.Status.CANCELLED)
                .values("group_class_id", "date").annotate(n=Count("id"))):
        taken[(row["group_class_id"], row["date"])] = row["n"]

    # Отменённые дни: человек не должен прийти к закрытой двери, потому
    # что на сайте занятие стояло как обычно.
    cancelled = {(c.group_class_id, c.date) for c in
                 ClassDay.objects.filter(group_class__in=classes, date__in=days,
                                         is_cancelled=True)}

    out = []
    for d in days:
        items = []
        for c in classes:
            if c.weekday != d.weekday():
                continue
            if c.group_id:
                # У группы места считаются по составу, а не по отметкам о
                # приходе: набранная группа из четырнадцати детей иначе
                # показывала бы на сайте «14 мест свободно».
                free = max(0, c.group.capacity - c.group_size)
            else:
                free = max(0, c.capacity - taken.get((c.id, d), 0))
            items.append({"cls": c, "free": free, "is_group": bool(c.group_id),
                          "cancelled": (c.id, d) in cancelled})
        # На сайте показываем группы: их и набирают. Открытые занятия
        # остаются, только если групп в этот день нет вовсе — иначе у клуба,
        # который ведёт всё открытыми записями, расписание опустело бы.
        groups_only = [i for i in items if i["is_group"]]
        if groups_only:
            items = groups_only
        out.append({"day": d, "items": items, "is_today": d == today})
    return out


def trainer_page(request, slug, trainer_id):
    club = get_object_or_404(FitnessClub, slug=slug, is_active=True)
    trainer = get_object_or_404(Trainer.objects.prefetch_related("sections", "schedule"),
                                id=trainer_id, club=club, is_active=True)
    return render(request, "fitness/public/trainer.html", {
        "club": club, "trainer": trainer, "days": _next_days(),
        "schedule": trainer.schedule.filter(is_active=True),
    })


def _next_days(n=14):
    """Ближайшие дни для выбора в форме записи."""
    today = timezone.localdate()
    return [today + timedelta(days=i) for i in range(n)]


@require_POST
def lead_create(request, slug):
    """Заявка: «перезвоните мне»."""
    club = get_object_or_404(FitnessClub, slug=slug, is_active=True)
    phone, err = _phone(request.POST.get("phone"))
    if err or not phone:
        return _answer(request, False, err or "Укажите телефон — перезвонить некуда")

    sec = request.POST.get("section_id")
    tr = request.POST.get("trainer_id")
    lead = Lead.objects.create(
        club=club,
        name=(request.POST.get("name") or "").strip()[:150],
        phone=phone,
        source=Lead.Source.SITE,
        section=Section.objects.filter(id=sec, club=club).first() if (sec or "").isdigit() else None,
        trainer=Trainer.objects.filter(id=tr, club=club).first() if (tr or "").isdigit() else None,
        comment=(request.POST.get("comment") or "").strip()[:500],
    )
    tgbot.in_background(tg.send_lead, lead)

    wa = _wa_link(club, [
        f"Здравствуйте! Заявка с сайта {club.name}.",
        f"Имя: {lead.name}" if lead.name else "",
        f"Телефон: {lead.phone}",
        f"Интересует: {lead.section.name}" if lead.section_id else "",
        f"Тренер: {lead.trainer.name}" if lead.trainer_id else "",
        lead.comment,
    ])
    return _answer(request, True, "Заявка принята — перезвоним", wa=wa)


@require_POST
def booking_create(request, slug):
    """Запись к тренеру с сайта."""
    club = get_object_or_404(FitnessClub, slug=slug, is_active=True)
    trainer = get_object_or_404(Trainer, id=request.POST.get("trainer_id"),
                                club=club, is_active=True)
    phone, err = _phone(request.POST.get("phone"))
    name = (request.POST.get("name") or "").strip()[:150]
    if err or not phone:
        return _answer(request, False, err or "Укажите телефон")

    try:
        day = datetime.strptime(request.POST.get("date") or "", "%Y-%m-%d").date()
        t = datetime.strptime(request.POST.get("time") or "", "%H:%M").time()
    except ValueError:
        return _answer(request, False, "Выберите день и время")
    if day < timezone.localdate():
        return _answer(request, False, "Этот день уже прошёл")

    # Занятое время не отдаём дважды: тренер один, и две записи на один час
    # приводят к разговору на ресепшене, а не к тренировке.
    busy = TrainerBooking.objects.filter(
        trainer=trainer, date=day, time_from=t,
    ).exclude(status=TrainerBooking.Status.CANCELLED).exists()
    if busy:
        return _answer(request, False, "Это время уже занято, выберите другое")

    booking = TrainerBooking.objects.create(
        club=club, trainer=trainer, client_name=name, phone=phone,
        date=day, time_from=t,
        duration_min=int(request.POST.get("duration") or 60),
        comment=(request.POST.get("comment") or "").strip()[:300],
        price=trainer.price_per_session,
    )
    # Заодно заявка: с ней работает администратор, даже если запись отменят
    lead = Lead.objects.create(
        club=club, name=name, phone=phone, source=Lead.Source.SITE,
        trainer=trainer, status=Lead.Status.BOOKED,
        comment=f"Запись к {trainer.name} на {day:%d.%m} {t:%H:%M}",
    )
    booking.lead = lead
    booking.save(update_fields=["lead"])

    tgbot.in_background(tg.send_booking, booking)

    wa = _wa_link(club, [
        f"Здравствуйте! Записался на тренировку через сайт {club.name}.",
        f"Тренер: {trainer.name}",
        f"Когда: {day:%d.%m.%Y} в {t:%H:%M}",
        f"Имя: {name}" if name else "",
        f"Телефон: {phone}",
        booking.comment,
    ])
    return _answer(request, True,
                   f"Записали к {trainer.name} на {day:%d.%m} в {t:%H:%M}",
                   wa=wa)


def _answer(request, ok, text, wa=""):
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": ok, "message": text, "wa": wa},
                            status=200 if ok else 400)
    # Без JavaScript уводим в WhatsApp сразу: заявка уже сохранена, и
    # человеку не нужно возвращаться на страницу, чтобы нажать ссылку.
    if ok and wa:
        return redirect(wa)
    (messages.success if ok else messages.error)(request, text)
    return redirect(request.META.get("HTTP_REFERER", "/"))
