# -*- coding: utf-8 -*-
"""Три уровня доступа в клубе.

Администратор видит всё: деньги, расходы, всех клиентов, всех тренеров.
Кассир работает со продажами и приходом в зал, но расходы и отчёты по
прибыли ему не нужны. Тренер видит только своё — свои записи, своих
клиентов, своё расписание, и ничего про кассу.

Проверки собраны здесь, чтобы не расходились по страницам: один раз
решили, кто что может, и зовём отсюда.
"""
from functools import wraps

from django.shortcuts import get_object_or_404, redirect

from .models import ClubStaff, FitnessClub, Trainer

ADMIN = ClubStaff.Role.ADMIN
CASHIER = ClubStaff.Role.CASHIER
TRAINER = ClubStaff.Role.TRAINER


def staff_of(user, club):
    """Запись сотрудника или None. Суперадмин считается администратором."""
    if not user.is_authenticated:
        return None
    if user.is_superuser or user.is_staff:
        return ClubStaff(user=user, club=club, role=ADMIN, is_active=True)
    return ClubStaff.objects.filter(user=user, club=club, is_active=True).first()


def my_clubs(user):
    """Клубы, к которым у человека есть доступ."""
    if not user.is_authenticated:
        return FitnessClub.objects.none()
    if user.is_superuser or user.is_staff:
        return FitnessClub.objects.all().order_by("sort_order", "name")
    return (FitnessClub.objects
            .filter(staff__user=user, staff__is_active=True)
            .distinct().order_by("sort_order", "name"))


def my_trainer(user, club):
    """Тренер, которым этот пользователь является в этом клубе."""
    if not user.is_authenticated:
        return None
    return Trainer.objects.filter(club=club, user=user).first()


def require(*roles):
    """Пускает на страницу клуба только нужные роли.

    Вьюха получает (request, club, staff) — чтобы не искать их заново и не
    забыть проверку.
    """
    def deco(view):
        @wraps(view)
        def inner(request, club_id, *args, **kwargs):
            club = get_object_or_404(FitnessClub, id=club_id)
            staff = staff_of(request.user, club)
            if not staff:
                return redirect("dashboard:home")
            if roles and staff.role not in roles:
                return redirect("fitness_dash:home", club_id=club.id)
            return view(request, club, staff, *args, **kwargs)
        return inner
    return deco


def can_see_money(staff):
    """Деньги клуба — выручка, расходы, прибыль. Тренеру не показываем."""
    return staff and staff.role in (ADMIN, CASHIER)


def can_see_profit(staff):
    """Расходы и прибыль — только администратору."""
    return staff and staff.role == ADMIN
