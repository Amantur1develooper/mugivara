# pharmacy/urls.py
from django.urls import path
from . import views

app_name = "pharmacy"

urlpatterns = [
    path("", views.pharmacy_list, name="pharmacy_list"),
    path("pharmacies/<slug:slug>/", views.pharmacy_detail, name="pharmacy_detail"),
    path("pharmacy/<int:branch_id>/catalog/", views.branch_catalog, name="branch_catalog"),
    path("pharmacy/<int:branch_id>/drug/<int:drug_id>/", views.drug_detail, name="drug_detail"),
    
    
    path("pharmacy/<int:branch_id>/cart/", views.cart_detail, name="cart_detail"),
    path("pharmacy/<int:branch_id>/cart/add/<int:branch_drug_id>/", views.cart_add, name="cart_add"),
    path("pharmacy/<int:branch_id>/cart/update/<int:branch_drug_id>/", views.cart_update, name="cart_update"),
    path("pharmacy/<int:branch_id>/cart/remove/<int:branch_drug_id>/", views.cart_remove, name="cart_remove"),

    # checkout
    path("pharmacy/<int:branch_id>/checkout/", views.checkout, name="checkout"),
    path("pharmacy/<int:branch_id>/checkout/<int:order_id>/success/", views.checkout_success, name="checkout_success"),
]
