from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from config import settings
from public_site.views_table import table_call_waiter, table_cart_update, table_add_to_cart, table_create_order, table_menu, table_cart, table_checkout, table_success

from django.conf.urls.static import static

urlpatterns = [
    path("i18n/", __import__("django.conf.urls.i18n").conf.urls.i18n.set_language, name="set_language"),
]

urlpatterns += i18n_patterns(
    path("admin/", admin.site.urls),
    path("", include("public_site.urls")), 
    path("t/<str:token>/cart/update/", table_cart_update, name="table_cart_update"),
    path("t/<str:token>/call-waiter/", table_call_waiter, name="table_call_waiter"),
    path("t/<str:token>/menu/", table_menu, name="table_menu"),
    path("t/<str:token>/add/<int:branch_item_id>/", table_add_to_cart, name="table_add_to_cart"),
    path("t/<str:token>/cart/", table_cart, name="table_cart"),
    path("t/<str:token>/checkout/", table_checkout, name="table_checkout"),
    path("t/<str:token>/success/<int:order_id>/", table_success, name="table_success"),
   # ✅ подтверждение заказа со стола
    path("t/<str:token>/order/create/", table_create_order, name="table_create_order"),


)


if settings.DEBUG:
    # ВАЖНО: статика в DEV лучше так (из STATICFILES_DIRS и static/ внутри приложений)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


    # медиа (upload)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
admin.site.site_header = "Администрирование Санжи"
admin.site.site_title = "Санжи"
admin.site.index_title = "Панель управления"