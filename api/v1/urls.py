from django.urls import path
from api.v1.views.restaurant import (
    restaurant_list, restaurant_detail, branch_list, branch_detail,
)
from api.v1.views.menu import branch_menu, branch_constructors
from api.v1.views.qr import qr_menu, qr_order_create, qr_order_status
from api.v1.views.order import branch_order_create, promo_check
from api.v1.views.history import order_history, order_detail
from api.v1.views.reservation import branch_floors, branch_free_places, booking_create, booking_status
from api.v1.views.promo import branch_promos, banner_list as promo_banner_list, banner_click
from api.v1.views.categories import (
    category_list, category_places, category_place_detail, category_place_branches,
)
from api.v1.views.search import search

urlpatterns = [
    # Категории платформы (§2, §3 API.md)
    path("categories/",                                                  category_list,          name="api-category-list"),
    path("categories/<slug:slug>/places/",                               category_places,        name="api-category-places"),
    path("categories/<slug:slug>/places/<slug:place_slug>/",             category_place_detail,  name="api-category-place-detail"),
    path("categories/<slug:slug>/places/<slug:place_slug>/branches/",    category_place_branches, name="api-category-place-branches"),

    # Поиск (§6 API.md)
    path("search/", search, name="api-search"),

    # Рестораны и филиалы (старые пути — алиасы для совместимости)
    path("restaurants/",                      restaurant_list,   name="api-restaurant-list"),
    path("restaurants/<slug:slug>/",          restaurant_detail, name="api-restaurant-detail"),
    path("restaurants/<slug:slug>/branches/", branch_list,       name="api-branch-list"),
    path("branches/<int:branch_id>/",         branch_detail,     name="api-branch-detail"),

    # Меню
    path("branches/<int:branch_id>/menu/",         branch_menu,         name="api-branch-menu"),
    path("branches/<int:branch_id>/constructors/", branch_constructors, name="api-branch-constructors"),

    # QR-стол
    path("qr/<str:token>/menu/",           qr_menu,          name="api-qr-menu"),
    path("qr/<str:token>/order/",          qr_order_create,  name="api-qr-order-create"),
    path("orders/<int:order_id>/status/",  qr_order_status,  name="api-qr-order-status"),

    # Доставка / самовывоз
    path("branches/<int:branch_id>/order/",        branch_order_create, name="api-branch-order-create"),
    path("branches/<int:branch_id>/promo/check/",  promo_check,         name="api-promo-check"),

    # История заказов (требует авторизации)
    path("orders/history/",          order_history, name="api-order-history"),
    path("orders/<int:order_id>/",   order_detail,  name="api-order-detail"),

    # Бронирование столов
    path("branches/<int:branch_id>/floors/",        branch_floors,       name="api-branch-floors"),
    path("branches/<int:branch_id>/places/free/",   branch_free_places,  name="api-branch-free-places"),
    path("branches/<int:branch_id>/book/",          booking_create,      name="api-booking-create"),
    path("bookings/<int:booking_id>/",              booking_status,      name="api-booking-status"),

    # Промокоды и баннеры
    path("branches/<int:branch_id>/promos/", branch_promos,      name="api-branch-promos"),
    path("banners/",                          promo_banner_list,  name="api-banner-list"),
    path("banners/<int:banner_id>/click/",    banner_click,       name="api-banner-click"),
]
