from django.urls import path

from . import tg_views

app_name = "simracing_tg"

urlpatterns = [
    path("appt/<str:token>/",        tg_views.card,        name="card"),
    path("appt/<str:token>/action/", tg_views.card_action, name="card_action"),
]
