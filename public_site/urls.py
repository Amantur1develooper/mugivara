
from django.urls import path, include
from .views import (
    about, booking_set_status, contacts, hall_plan, home, place_move, reservation, restaurant_about, restaurant_contacts, restaurant_detail, branch_menu, restaurant_branch_menu,
    add_to_cart, cart_detail, cart_json, cart_update, cart_remove,
    checkout, checkout_success, restaurants_list, validate_promo, banner_click,
)
from reservations import views as r
from public_site.views_table import (
    table_cart, table_create_order, table_cart_update,
    table_call_waiter, table_menu, table_add_to_cart,
    branch_tables_page,
)


app_name = "public_site"

urlpatterns = [
    
    path("", home, name="home"),
    path("ads/<int:banner_id>/click/", banner_click, name="banner_click"),
    path("restaurants/", restaurants_list, name="restaurants_list"),
    # path("shops/", include("shops.urls")),
    path("t/<str:token>/menu/", table_menu, name="table_menu"),
    path("t/<str:token>/cart/", table_cart, name="table_cart"),
    path("t/<str:token>/cart/add/<int:branch_item_id>/", table_add_to_cart, name="table_add_to_cart"),
    path("t/<str:token>/cart/update/", table_cart_update, name="table_cart_update"),
    path("t/<str:token>/order/create/", table_create_order, name="table_create_order"),
    path("t/<str:token>/call-waiter/", table_call_waiter, name="table_call_waiter"),
    path("<int:branch_id>/tables/", branch_tables_page, name="branch_tables"),
    # ВАЖНО: без ведущего "/"
    path("<int:branch_id>/menu/", branch_menu, name="branch_menu"),

    # корзина
    path("b/<int:branch_id>/cart/", cart_detail, name="cart_detail"),
    path("b/<int:branch_id>/cart.json/", cart_json, name="cart_json"),
    path("b/<int:branch_id>/cart/update/<int:branch_item_id>/", cart_update, name="cart_update"),
    path("b/<int:branch_id>/cart/remove/<int:branch_item_id>/", cart_remove, name="cart_remove"),

    # add to cart (AJAX)
    path("b/add/<int:branch_item_id>/", add_to_cart, name="add_to_cart"),

    # checkout
    path("b/<int:branch_id>/checkout/", checkout, name="checkout"),
    path("b/<int:branch_id>/promo/validate/", validate_promo, name="validate_promo"),
    # path("b/<int:branch_id>/checkout/success/<int:order_id>/", checkout_success, name="checkout_success"),
    path("about/", about, name="about"),
    # path("contacts/", contacts, name="contacts"),
    path("r/<slug:slug>/contacts/", restaurant_contacts, name="restaurant_contacts"),
    # path("reservation/", reservation, name="reservation"),
    # slug — лучше в конце
    path("<slug:slug>/", restaurant_detail, name="restaurant_detail"),
    path("<slug:restaurant_slug>/<int:branch_id>/", restaurant_branch_menu, name="restaurant_branch_menu"),
    
    path("<int:branch_id>/hall/", hall_plan, name="hall_plan"),
    path("place/<int:place_id>/move/", place_move, name="place_move"),
    path("booking/<int:booking_id>/status/<str:status>/", booking_set_status, name="booking_set_status"),
    
    path("<int:branch_id>/reservation/", r.reservation_page, name="reservation"),
    path("<int:branch_id>/reservation/<int:place_id>/create/", r.reserve_create, name="reserve_create"),
    path("<int:branch_id>/reservation/success/<int:booking_id>/", r.booking_success, name="booking_success"),
    
    path("r/<slug:slug>/about/", restaurant_about, name="restaurant_about"),
path("b/<int:branch_id>/checkout/success/<int:order_id>/", checkout_success, name="checkout_success"),


]
urlpatterns += [
    path("s/<str:token>/bookings/", r.staff_bookings, name="staff_bookings"),
    path("s/<str:token>/booking/<int:booking_id>/status/<str:status>/", r.staff_booking_set_status, name="staff_booking_set_status"),
]
