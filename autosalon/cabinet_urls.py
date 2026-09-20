from django.urls import path
from . import cabinet_views as views

app_name = "acabinet"

urlpatterns = [
    path("login/",  views.login_view,  name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("",          views.home,      name="home"),
    path("switch/<int:dealership_id>/", views.switch_dealership, name="switch_dealership"),

    path("leads/", views.leads, name="leads"),
    path("leads/<int:lead_id>/update/", views.lead_update, name="lead_update"),

    path("reports/", views.reports, name="reports"),
    path("reports/<int:dealership_id>/export/cars/",  views.reports_export_cars,  name="reports_export_cars"),
    path("reports/<int:dealership_id>/export/leads/", views.reports_export_leads, name="reports_export_leads"),

    path("dealership/<int:dealership_id>/settings/", views.dealership_settings, name="dealership_settings"),

    path("car/add/<int:dealership_id>/", views.car_add, name="car_add"),
    path("car/<int:car_id>/edit/",   views.car_edit,   name="car_edit"),
    path("car/<int:car_id>/status/", views.car_status, name="car_status"),
    path("car/<int:car_id>/delete/", views.car_delete, name="car_delete"),
]
