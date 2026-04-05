from django.urls import path
from . import views

urlpatterns = [
    path("", views.legal_list, name="legal_list"),
    path("<slug:slug>/", views.legal_detail, name="legal_detail"),
]
