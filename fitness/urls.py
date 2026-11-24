# -*- coding: utf-8 -*-
"""Публичная часть фитнес-клуба."""
from django.urls import path

from . import views

app_name = "fitness"

urlpatterns = [
    path("", views.club_list, name="index"),
    path("<slug:slug>/", views.club_page, name="club"),
    path("<slug:slug>/icon.png", views.club_icon, name="club_icon"),
    path("<slug:slug>/preview.jpg", views.club_preview, name="club_preview"),
    path("<slug:slug>/trainer/<int:trainer_id>/", views.trainer_page, name="trainer"),
    path("<slug:slug>/lead/", views.lead_create, name="lead_create"),
    path("<slug:slug>/book/", views.booking_create, name="booking_create"),
]
