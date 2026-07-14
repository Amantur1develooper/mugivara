from django.urls import path
from . import views

app_name = "simracing"

urlpatterns = [
    path("<slug:slug>/",                              views.venue,           name="venue"),
    path("<slug:slug>/book/",                         views.book,            name="book"),
    path("<slug:slug>/success/<int:session_id>/",     views.success,         name="success"),
    path("<slug:slug>/status.json",                   views.machines_status, name="machines_status"),
    # Online pre-booking (appointment)
    path("<slug:slug>/slots.json",                    views.slots_json,      name="slots_json"),
    path("<slug:slug>/reserve/",                      views.book_appt,       name="book_appt"),
    path("<slug:slug>/reserved/<int:appt_id>/",       views.appt_success,    name="appt_success"),
]
