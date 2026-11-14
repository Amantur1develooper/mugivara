from django.urls import path

from . import tg_views

app_name = "barbershop_tg"

urlpatterns = [
    # Вне i18n_patterns: Telegram стучится по точному адресу, а префикс языка
    # дал бы редирект, который вебхук не отработает.
    path("webhook/<str:secret>/",    tg_views.webhook,     name="webhook"),
    path("appt/<str:token>/",        tg_views.card,        name="card"),
    path("appt/<str:token>/action/", tg_views.card_action, name="card_action"),
]
