from django.urls import path
from . import views

urlpatterns = [
    path("",                      views.eco_list,   name="eco_list"),
    path("<slug:slug>/",          views.eco_detail, name="eco_detail"),
    path("<slug:slug>/apply/",    views.eco_apply,  name="eco_apply"),
]
