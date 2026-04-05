from django.urls import path
from . import views

urlpatterns = [
    path("", views.market_list, name="market_list"),
    path("<slug:slug>/", views.market_detail, name="market_detail"),
]
