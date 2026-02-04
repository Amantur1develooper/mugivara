from django.urls import path
from .views import (
    about, booking_set_status, contacts, hall_plan, home, place_move, reservation, restaurant_about, restaurant_contacts, restaurant_detail, branch_menu,
    add_to_cart, cart_detail, cart_update, cart_remove,
    checkout, checkout_success
)
from reservations import views as r



app_name = "public_site"

urlpatterns = [
    path("", home, name="home"),

    # ВАЖНО: без ведущего "/"
    path("<int:branch_id>/menu/", branch_menu, name="branch_menu"),

    # корзина
    path("b/<int:branch_id>/cart/", cart_detail, name="cart_detail"),
    path("b/<int:branch_id>/cart/update/<int:branch_item_id>/", cart_update, name="cart_update"),
    path("b/<int:branch_id>/cart/remove/<int:branch_item_id>/", cart_remove, name="cart_remove"),

    # add to cart (AJAX)
    path("b/add/<int:branch_item_id>/", add_to_cart, name="add_to_cart"),

    # checkout
    path("b/<int:branch_id>/checkout/", checkout, name="checkout"),
    path("b/<int:branch_id>/checkout/success/<int:order_id>/", checkout_success, name="checkout_success"),
    path("about/", about, name="about"),
    # path("contacts/", contacts, name="contacts"),
    path("r/<slug:slug>/contacts/", restaurant_contacts, name="restaurant_contacts"),
    # path("reservation/", reservation, name="reservation"),
    # slug — лучше в конце
    path("<slug:slug>/", restaurant_detail, name="restaurant_detail"),
    
    path("<int:branch_id>/hall/", hall_plan, name="hall_plan"),
    path("place/<int:place_id>/move/", place_move, name="place_move"),
    path("booking/<int:booking_id>/status/<str:status>/", booking_set_status, name="booking_set_status"),
    
    path("<int:branch_id>/reservation/", r.reservation_page, name="reservation"),
    path("<int:branch_id>/reservation/<int:place_id>/create/", r.reserve_create, name="reserve_create"),
    path("<int:branch_id>/reservation/success/<int:booking_id>/", r.booking_success, name="booking_success"),
    
    path("r/<slug:slug>/about/", restaurant_about, name="restaurant_about"),


]
urlpatterns += [

    
    
    path("s/<str:token>/bookings/", r.staff_bookings, name="staff_bookings"),
    path("s/<str:token>/booking/<int:booking_id>/status/<str:status>/", r.staff_booking_set_status, name="staff_booking_set_status"),
]

# urlpatterns += [
#     # path("<int:branch_id>/reservation/", r.reservation_page, name="reservation"),
#     # path("<int:branch_id>/reservation/<int:place_id>/create/", r.reserve_create, name="reserve_create"),
# ]