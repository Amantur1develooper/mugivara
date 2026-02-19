from django.urls import path
from . import views

app_name = "shops"

urlpatterns = [
    path("", views.store_list, name="store_list"),
    path("<slug:slug>/", views.store_detail, name="store_detail"),

    # ДВЕ ССЫЛКИ:
    path("b/<int:branch_id>/delivery/", views.branch_catalog_delivery, name="branch_catalog_delivery"),
    path("b/<int:branch_id>/pickup/", views.branch_catalog_pickup, name="branch_catalog_pickup"),

    # cart
    path("b/<int:branch_id>/cart/", views.cart_detail, name="cart_detail"),
    path("b/<int:branch_id>/cart/add/<int:product_id>/", views.cart_add, name="cart_add"),
    path("b/<int:branch_id>/cart/update/<int:product_id>/", views.cart_update, name="cart_update"),
    path("b/<int:branch_id>/cart/remove/<int:product_id>/", views.cart_remove, name="cart_remove"),
    
     path("b/<int:branch_id>/checkout/success/<int:order_id>/", views.checkout_success, name="checkout_success"),

    # checkout/success
    path("b/<int:branch_id>/checkout/", views.checkout, name="checkout"),
    path("b/<int:branch_id>/success/<int:order_id>/", views.order_success, name="order_success"),
]
