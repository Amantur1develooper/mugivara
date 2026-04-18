from django.urls import path
from . import views
from hotels import dashboard_views as hv
from shops import dashboard_views as sv
from legal import dashboard_views as lv
from agency import dashboard_views as av
from karaoke import dashboard_views as kv

app_name = "dashboard"

urlpatterns = [
    path("login/",  views.login_view,  name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("",        views.home,        name="home"),

    path("restaurant/<int:restaurant_id>/edit/", views.restaurant_edit, name="restaurant_edit"),

    path("branch/<int:branch_id>/edit/",     views.branch_edit,  name="branch_edit"),
    path("branch/<int:branch_id>/items/",    views.branch_items, name="branch_items"),
    path("branch/<int:branch_id>/add-item/",    views.item_add,           name="item_add"),
    path("branch/<int:branch_id>/categories/", views.branch_categories,  name="branch_categories"),
    path("branch/<int:branch_id>/categories/add/", views.category_add,   name="category_add"),

    path("category/<int:bc_id>/toggle/",  views.category_toggle,  name="category_toggle"),
    path("category/<int:bc_id>/reorder/", views.category_reorder, name="category_reorder"),
    path("category/<int:bc_id>/remove/",  views.category_remove,  name="category_remove"),

    # ── Menu Sets (сеты категорий) ───────────────────────────────────────────
    path("restaurant/<int:restaurant_id>/menu-sets/",   views.menu_sets,        name="menu_sets"),
    path("restaurant/<int:restaurant_id>/menu-sets/add/", views.menu_set_add,   name="menu_set_add"),
    path("menu-set/<int:menu_set_id>/rename/",          views.menu_set_rename,  name="menu_set_rename"),
    path("menu-set/<int:menu_set_id>/delete/",          views.menu_set_delete,  name="menu_set_delete"),
    path("menu-set/<int:menu_set_id>/category/add/",    views.ms_category_add,  name="ms_category_add"),
    path("ms-category/<int:category_id>/edit/",         views.ms_category_edit, name="ms_category_edit"),
    path("ms-category/<int:category_id>/delete/",       views.ms_category_delete, name="ms_category_delete"),

    path("item/<int:branch_item_id>/edit/",   views.item_edit,         name="item_edit"),
    path("item/<int:branch_item_id>/price/",  views.update_item_price, name="update_price"),
    path("item/<int:branch_item_id>/toggle/", views.toggle_item,       name="toggle_item"),

    path("branch/<int:branch_id>/promos/",    views.promo_list,   name="promo_list"),
    path("promo/<int:promo_id>/toggle/",      views.promo_toggle, name="promo_toggle"),
    path("promo/<int:promo_id>/delete/",      views.promo_delete, name="promo_delete"),

    path("branch/<int:branch_id>/tables/",         views.branch_tables, name="branch_tables"),
    path("branch/<int:branch_id>/tables/floor/add/", views.floor_add,   name="floor_add"),
    path("floor/<int:floor_id>/delete/",             views.floor_delete, name="floor_delete"),
    path("floor/<int:floor_id>/table/add/",          views.table_add,    name="table_add"),
    path("table/<int:table_id>/delete/",             views.table_delete, name="table_delete"),

    path("analytics/", views.analytics,        name="analytics"),
    path("orders/",    views.orders_analytics, name="orders"),

    # ── POS (Касса) ─────────────────────────────────────────────────────────
    path("pos/<int:branch_id>/",              views.pos,               name="pos"),
    path("pos/<int:branch_id>/order/",        views.pos_order_create,  name="pos_order_create"),
    path("pos/<int:branch_id>/live/",         views.pos_live_orders,   name="pos_live_orders"),
    path("pos/order/<int:order_id>/status/",  views.pos_order_status,  name="pos_order_status"),
    path("pos/receipt/<int:order_id>/",       views.pos_receipt,       name="pos_receipt"),
    path("pos/<int:branch_id>/inventory/",    views.pos_inventory,     name="pos_inventory"),
    path("pos/<int:branch_id>/report/",       views.pos_report,        name="pos_report"),

    # ── SHOPS ───────────────────────────────────────────────────────────────
    path("shops/",                                          sv.shop_home,          name="shop_home"),
    path("shops/<int:store_id>/edit/",                      sv.shop_store_edit,    name="shop_store_edit"),
    path("shops/branch/<int:branch_id>/edit/",              sv.shop_branch_edit,   name="shop_branch_edit"),
    path("shops/branch/<int:branch_id>/toggle/",            sv.shop_branch_toggle, name="shop_branch_toggle"),
    path("shops/branch/<int:branch_id>/products/",          sv.shop_product_list,     name="shop_product_list"),
    path("shops/stock/<int:stock_id>/qty/",                 sv.shop_stock_update,     name="shop_stock_update"),
    path("shops/stock/<int:stock_id>/price/",               sv.shop_price_update,     name="shop_price_update"),
    path("shops/branch/<int:branch_id>/product/add/",       sv.shop_product_add,      name="shop_product_add"),
    path("shops/stock/<int:stock_id>/edit/",                sv.shop_product_edit,     name="shop_product_edit"),
    path("shops/stock/<int:stock_id>/delete/",              sv.shop_product_delete,   name="shop_product_delete"),
    path("shops/stock/<int:stock_id>/toggle/",              sv.shop_product_toggle,   name="shop_product_toggle"),
    path("shops/branch/<int:branch_id>/category/add/",      sv.shop_category_add,     name="shop_category_add"),
    path("shops/category/<int:category_id>/rename/",        sv.shop_category_rename,  name="shop_category_rename"),
    path("shops/category/<int:category_id>/delete/",        sv.shop_category_delete,  name="shop_category_delete"),
    path("shops/branch/<int:branch_id>/orders/",            sv.shop_orders,           name="shop_orders"),
    path("shops/order/<int:order_id>/status/",              sv.shop_order_status,     name="shop_order_status"),
    path("shops/branch/<int:branch_id>/barcode/",           sv.shop_barcode_lookup,   name="shop_barcode_lookup"),

    # ── AGENCY ──────────────────────────────────────────────────────────────
    path("agency/",                                      av.agency_home,           name="agency_home"),
    path("agency/<int:agency_id>/edit/",                 av.agency_edit,           name="agency_edit"),
    path("agency/<int:agency_id>/services/",             av.agency_services,       name="agency_services"),
    path("agency/<int:agency_id>/services/add/",         av.agency_service_add,    name="agency_service_add"),
    path("agency/service/<int:svc_id>/edit/",            av.agency_service_edit,   name="agency_service_edit"),
    path("agency/service/<int:svc_id>/toggle/",          av.agency_service_toggle, name="agency_service_toggle"),
    path("agency/service/<int:svc_id>/delete/",          av.agency_service_delete, name="agency_service_delete"),

    # ── KARAOKE ─────────────────────────────────────────────────────────────
    path("karaoke/",                                         kv.karaoke_home,           name="karaoke_home"),
    path("karaoke/<int:venue_id>/edit/",                     kv.karaoke_venue_edit,     name="karaoke_venue_edit"),
    path("karaoke/<int:venue_id>/rooms/",                    kv.karaoke_rooms,          name="karaoke_rooms"),
    path("karaoke/<int:venue_id>/rooms/add/",                kv.karaoke_room_add,       name="karaoke_room_add"),
    path("karaoke/room/<int:room_id>/edit/",                 kv.karaoke_room_edit,      name="karaoke_room_edit"),
    path("karaoke/room/<int:room_id>/toggle/",               kv.karaoke_room_toggle,    name="karaoke_room_toggle"),
    path("karaoke/room/<int:room_id>/delete/",               kv.karaoke_room_delete,    name="karaoke_room_delete"),
    path("karaoke/<int:venue_id>/cat/add/",                  kv.karaoke_cat_add,        name="karaoke_cat_add"),
    path("karaoke/cat/<int:cat_id>/delete/",                 kv.karaoke_cat_delete,     name="karaoke_cat_delete"),
    path("karaoke/<int:venue_id>/chess/",                    kv.karaoke_chess,          name="karaoke_chess"),
    path("karaoke/<int:venue_id>/booking/add/",              kv.karaoke_booking_add,    name="karaoke_booking_add"),
    path("karaoke/booking/<int:booking_id>/status/",         kv.karaoke_booking_status, name="karaoke_booking_status"),
    path("karaoke/booking/<int:booking_id>/delete/",         kv.karaoke_booking_delete, name="karaoke_booking_delete"),
    path("karaoke/<int:venue_id>/menu/",                     kv.karaoke_menu_manage,    name="karaoke_menu_manage"),
    path("karaoke/<int:venue_id>/menu/cat/add/",             kv.karaoke_menu_cat_add,   name="karaoke_menu_cat_add"),
    path("karaoke/<int:venue_id>/menu/item/add/",            kv.karaoke_menu_item_add,  name="karaoke_menu_item_add"),
    path("karaoke/menu/item/<int:item_id>/delete/",          kv.karaoke_menu_item_delete,  name="karaoke_menu_item_delete"),
    path("karaoke/menu/item/<int:item_id>/toggle/",          kv.karaoke_menu_item_toggle,  name="karaoke_menu_item_toggle"),
    path("karaoke/menu/item/<int:item_id>/update/",          kv.karaoke_menu_item_update,  name="karaoke_menu_item_update"),
    path("karaoke/<int:venue_id>/report/",                   kv.karaoke_report,            name="karaoke_report"),
    path("karaoke/<int:venue_id>/order/add/",                kv.karaoke_order_add,         name="karaoke_order_add"),
    path("karaoke/order/<int:order_id>/delete/",             kv.karaoke_order_delete,      name="karaoke_order_delete"),

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

    # ── LEGAL ────────────────────────────────────────────────────────────────
    path("legal/",                                      lv.legal_home,           name="legal_home"),
    path("legal/<int:org_id>/edit/",                    lv.legal_org_edit,       name="legal_org_edit"),
    path("legal/<int:org_id>/services/",                lv.legal_services,       name="legal_services"),
    path("legal/<int:org_id>/services/add/",            lv.legal_service_add,    name="legal_service_add"),
    path("legal/service/<int:svc_id>/edit/",            lv.legal_service_edit,   name="legal_service_edit"),
    path("legal/service/<int:svc_id>/toggle/",          lv.legal_service_toggle, name="legal_service_toggle"),
    path("legal/service/<int:svc_id>/delete/",          lv.legal_service_delete, name="legal_service_delete"),
]
