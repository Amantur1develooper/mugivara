from django.urls import path

from . import views

app_name = "printshop"

urlpatterns = [
    path("", views.center_list, name="center_list"),
    path("<slug:slug>/", views.center_detail, name="center_detail"),
    path("<slug:slug>/b/<int:branch_id>/", views.branch_catalog, name="branch_catalog"),

    path("b/<int:branch_id>/cart.json", views.cart_json, name="cart_json"),
    path("b/<int:branch_id>/cart/add/", views.cart_add, name="cart_add"),
    path("b/<int:branch_id>/cart/update/<str:line_id>/", views.cart_update, name="cart_update"),
    path("b/<int:branch_id>/cart/remove/<str:line_id>/", views.cart_remove, name="cart_remove"),
    path("b/<int:branch_id>/promo/validate/", views.validate_promo, name="validate_promo"),

    path("b/<int:branch_id>/checkout/", views.checkout, name="checkout"),
    path("<slug:slug>/b/<int:branch_id>/checkout/success/<int:order_id>/", views.checkout_success, name="checkout_success"),
]
