from django.urls import path
from . import views

app_name = "autosalon"

urlpatterns = [
    path("", views.dealership_list, name="dealership_list"),
    path("<slug:slug>/", views.dealership_detail, name="dealership_detail"),
    path("<slug:slug>/lead/", views.lead_create, name="lead_create"),
    path("<slug:slug>/<int:car_id>/", views.car_detail, name="car_detail"),
    path("<slug:slug>/<int:car_id>/lead/", views.lead_create, name="car_lead_create"),
]
