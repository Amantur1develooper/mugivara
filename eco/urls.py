from django.urls import path
from . import views

urlpatterns = [
    path("", views.eco_list, name="eco_list"),
    path("<slug:slug>/", views.eco_detail, name="eco_detail"),
]
