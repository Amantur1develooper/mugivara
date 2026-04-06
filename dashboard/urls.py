from django.urls import path
from . import views
from hotels import dashboard_views as hv
from shops import dashboard_views as sv

app_name = "dashboard"

urlpatterns = [
    path("login/",  views.login_view,  name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("",        views.home,        name="home"),

    path("restaurant/<int:restaurant_id>/edit/", views.restaurant_edit, name="restaurant_edit"),

    path("branch/<int:branch_id>/edit/",     views.branch_edit,  name="branch_edit"),
    path("branch/<int:branch_id>/items/",    views.branch_items, name="branch_items"),
    path("branch/<int:branch_id>/add-item/", views.item_add,     name="item_add"),

    path("item/<int:branch_item_id>/edit/",   views.item_edit,         name="item_edit"),
    path("item/<int:branch_item_id>/price/",  views.update_item_price, name="update_price"),
    path("item/<int:branch_item_id>/toggle/", views.toggle_item,       name="toggle_item"),

    path("branch/<int:branch_id>/promos/",    views.promo_list,   name="promo_list"),
    path("promo/<int:promo_id>/toggle/",      views.promo_toggle, name="promo_toggle"),
    path("promo/<int:promo_id>/delete/",      views.promo_delete, name="promo_delete"),

    path("analytics/", views.analytics, name="analytics"),

    # ── SHOPS ───────────────────────────────────────────────────────────────
    path("shops/",                                          sv.shop_home,          name="shop_home"),
    path("shops/<int:store_id>/edit/",                      sv.shop_store_edit,    name="shop_store_edit"),
    path("shops/branch/<int:branch_id>/edit/",              sv.shop_branch_edit,   name="shop_branch_edit"),
    path("shops/branch/<int:branch_id>/toggle/",            sv.shop_branch_toggle, name="shop_branch_toggle"),
    path("shops/branch/<int:branch_id>/products/",          sv.shop_product_list,  name="shop_product_list"),
    path("shops/stock/<int:stock_id>/qty/",                 sv.shop_stock_update,  name="shop_stock_update"),
    path("shops/stock/<int:stock_id>/price/",               sv.shop_price_update,  name="shop_price_update"),
    path("shops/branch/<int:branch_id>/orders/",            sv.shop_orders,        name="shop_orders"),
    path("shops/order/<int:order_id>/status/",              sv.shop_order_status,  name="shop_order_status"),

    # ── HOTELS ──────────────────────────────────────────────────────────────
    path("hotels/",                                       hv.hotel_home,          name="hotel_home"),
    path("hotels/<int:hotel_id>/edit/",                   hv.hotel_edit,          name="hotel_edit"),
    path("hotels/branch/<int:branch_id>/edit/",           hv.hotel_branch_edit,   name="hotel_branch_edit"),
    path("hotels/branch/<int:branch_id>/toggle/",         hv.hotel_branch_toggle, name="hotel_branch_toggle"),
    path("hotels/branch/<int:branch_id>/rooms/",          hv.hotel_room_list,     name="hotel_room_list"),
    path("hotels/branch/<int:branch_id>/rooms/add/",      hv.hotel_room_add,      name="hotel_room_add"),
    path("hotels/room/<int:room_id>/edit/",               hv.hotel_room_edit,     name="hotel_room_edit"),
    path("hotels/room/<int:room_id>/toggle/",             hv.hotel_room_toggle,   name="hotel_room_toggle"),
    path("hotels/branch/<int:branch_id>/bookings/",       hv.hotel_bookings,      name="hotel_bookings"),
    path("hotels/booking/<int:booking_id>/status/",       hv.hotel_booking_status, name="hotel_booking_status"),
]
