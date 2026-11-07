from django.urls import path

from . import views

app_name = "metalwork"

urlpatterns = [
    path("", views.company_list, name="company_list"),
    path("<slug:slug>/", views.company_detail, name="company_detail"),
    path("<slug:slug>/<int:product_id>/", views.product_detail, name="product_detail"),
    path("<slug:slug>/lead/", views.lead_create, name="lead_create"),
    path("<slug:slug>/<int:product_id>/lead/", views.lead_create, name="product_lead_create"),
]
