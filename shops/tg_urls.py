from django.urls import path

from . import tg_views

app_name = "shops_tg"

urlpatterns = [
    path("order/<str:token>/",        tg_views.card,        name="card"),
    path("order/<str:token>/action/", tg_views.card_action, name="card_action"),
]
