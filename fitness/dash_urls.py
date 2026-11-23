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
    path("<int:club_id>/debt/<int:debt_id>/settle/", v.debt_settle, name="debt_settle"),

    path("<int:club_id>/board/", v.board, name="board"),
    path("<int:club_id>/board/add/", v.booking_save, name="booking_save"),
    path("<int:club_id>/booking/<int:booking_id>/status/", v.booking_status, name="booking_status"),

    path("<int:club_id>/groups/", v.groups, name="groups"),
    path("<int:club_id>/groups/new/", v.group_save, name="group_new"),
    path("<int:club_id>/groups/<int:group_id>/", v.group_detail, name="group_detail"),
    path("<int:club_id>/groups/<int:group_id>/save/", v.group_save, name="group_save"),
    path("<int:club_id>/groups/<int:group_id>/roster/", v.group_roster, name="group_roster"),
    path("<int:club_id>/groups/<int:group_id>/slot/", v.group_slot, name="group_slot"),

    path("<int:club_id>/classes/", v.classes, name="classes"),
    path("<int:club_id>/classes/add/", v.class_save, name="class_save"),
    path("<int:club_id>/classes/<int:class_id>/", v.class_day, name="class_day"),
    path("<int:club_id>/classes/<int:class_id>/book/", v.class_book, name="class_book"),
    path("<int:club_id>/classes/<int:class_id>/mark/", v.class_mark, name="class_mark"),
    path("<int:club_id>/classes/<int:class_id>/cancel/", v.class_cancel, name="class_cancel"),
    path("<int:club_id>/classes/<int:class_id>/mark-all/", v.class_mark_all,
         name="class_mark_all"),
    path("<int:club_id>/class-booking/<int:booking_id>/status/", v.class_booking_status,
         name="class_booking_status"),

    path("<int:club_id>/leads/", v.leads, name="leads"),
    path("<int:club_id>/leads/new/", v.lead_save, name="lead_new"),
    path("<int:club_id>/leads/<int:lead_id>/", v.lead_detail, name="lead_detail"),
    path("<int:club_id>/leads/<int:lead_id>/save/", v.lead_save, name="lead_save"),
    path("<int:club_id>/leads/<int:lead_id>/to-member/", v.lead_to_member, name="lead_to_member"),

    path("<int:club_id>/expenses/", v.expenses, name="expenses"),
    path("<int:club_id>/expenses/add/", v.expense_add, name="expense_add"),
    path("<int:club_id>/reports/", v.reports, name="reports"),
    path("<int:club_id>/reports/export/", v.reports_export, name="reports_export"),
    path("<int:club_id>/members/export/", v.members_export, name="members_export"),
    path("<int:club_id>/leads/export/", v.leads_export, name="leads_export"),
    path("<int:club_id>/setup/", v.setup, name="setup"),
    path("<int:club_id>/staff/add/", v.staff_add, name="staff_add"),
    path("<int:club_id>/staff/<int:staff_id>/edit/", v.staff_edit, name="staff_edit"),
    path("<int:club_id>/staff/<int:staff_id>/password/", v.staff_password,
         name="staff_password"),
]
