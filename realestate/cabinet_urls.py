from django.urls import path
from . import dashboard_views as views

app_name = "rcabinet"

urlpatterns = [
    path("login/",  views.login_view,  name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("",        views.home,        name="home"),

    path("agency/<int:agency_id>/apartment/add/", views.apartment_add, name="apartment_add"),
    path("apartment/<int:apartment_id>/edit/",     views.apartment_edit,   name="apartment_edit"),
    path("apartment/<int:apartment_id>/status/",   views.apartment_status, name="apartment_status"),
    path("apartment/<int:apartment_id>/delete/",   views.apartment_delete, name="apartment_delete"),
]
