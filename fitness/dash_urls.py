# -*- coding: utf-8 -*-
"""Адреса кабинета фитнес-клуба."""
from django.urls import path

from . import dashboard_views as v

app_name = "fitness_dash"

urlpatterns = [
    path("", v.clubs, name="clubs"),
    path("<int:club_id>/", v.home, name="home"),

    path("<int:club_id>/checkin/", v.checkin, name="checkin"),
    path("<int:club_id>/checkin/<int:member_id>/pass/", v.checkin_pass, name="checkin_pass"),

    path("<int:club_id>/members/", v.members, name="members"),
    path("<int:club_id>/members/new/", v.member_save, name="member_new"),
    path("<int:club_id>/members/<int:member_id>/", v.member_detail, name="member_detail"),
    path("<int:club_id>/members/<int:member_id>/save/", v.member_save, name="member_save"),
    path("<int:club_id>/members/<int:member_id>/sell/", v.membership_sell, name="membership_sell"),
    path("<int:club_id>/membership/<int:membership_id>/action/", v.membership_action,
         name="membership_action"),

    path("<int:club_id>/board/", v.board, name="board"),
    path("<int:club_id>/board/add/", v.booking_save, name="booking_save"),
    path("<int:club_id>/booking/<int:booking_id>/status/", v.booking_status, name="booking_status"),

    path("<int:club_id>/leads/", v.leads, name="leads"),
    path("<int:club_id>/leads/new/", v.lead_save, name="lead_new"),
    path("<int:club_id>/leads/<int:lead_id>/", v.lead_detail, name="lead_detail"),
    path("<int:club_id>/leads/<int:lead_id>/save/", v.lead_save, name="lead_save"),
    path("<int:club_id>/leads/<int:lead_id>/to-member/", v.lead_to_member, name="lead_to_member"),

    path("<int:club_id>/expenses/", v.expenses, name="expenses"),
    path("<int:club_id>/expenses/add/", v.expense_add, name="expense_add"),
    path("<int:club_id>/reports/", v.reports, name="reports"),
    path("<int:club_id>/setup/", v.setup, name="setup"),
]
