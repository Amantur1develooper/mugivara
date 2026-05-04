from django.urls import path
from . import views

app_name = "barbershop"

urlpatterns = [
    path("",                            views.index,          name="index"),
    path("<slug:slug>/",                views.venue,          name="venue"),
    path("<slug:slug>/book/",           views.book,           name="book"),
    path("<slug:slug>/book/barbers/",   views.barbers_json,   name="barbers_json"),
    path("<slug:slug>/book/slots/",     views.slots_json,     name="slots_json"),
    path("<slug:slug>/book/confirm/",   views.book_confirm,   name="book_confirm"),
    path("<slug:slug>/book/success/",   views.book_success,   name="book_success"),
]
