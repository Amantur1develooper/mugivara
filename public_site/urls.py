from django.urls import path
from .views import branch_menu, cart_add, cart_detail, cart_remove, cart_update, checkout, checkout_success, home, restaurant_detail

app_name = "public_site"

urlpatterns = [
    path("", home, name="home"),
    path("<slug:slug>/", restaurant_detail, name="restaurant_detail"),
     path("/<int:branch_id>/menu/", branch_menu, name="branch_menu"),
     
    path("b/<int:branch_id>/cart/", cart_detail, name="cart_detail"),
    path("b/<int:branch_id>/cart/add/<int:branch_item_id>/", cart_add, name="cart_add"),
    path("b/<int:branch_id>/cart/update/<int:branch_item_id>/", cart_update, name="cart_update"),
    path("b/<int:branch_id>/cart/remove/<int:branch_item_id>/", cart_remove, name="cart_remove"),

    path("b/<int:branch_id>/checkout/", checkout, name="checkout"),
    path("b/<int:branch_id>/checkout/success/<int:order_id>/", checkout_success, name="checkout_success"),
]
