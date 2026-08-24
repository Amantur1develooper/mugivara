from django.urls import path
from . import views

app_name = "realestate"

urlpatterns = [
    path("", views.agency_list, name="agency_list"),
    path("<slug:slug>/", views.agency_detail, name="agency_detail"),
    path("<slug:slug>/<int:apartment_id>/", views.apartment_detail, name="apartment_detail"),
]
