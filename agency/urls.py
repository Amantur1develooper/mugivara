from django.urls import path
from . import views

urlpatterns = [
    path("", views.agency_list, name="agency_list"),
    path("<slug:slug>/", views.agency_detail, name="agency_detail"),
    path("<slug:slug>/inquiry/", views.agency_inquiry, name="agency_inquiry"),
]
