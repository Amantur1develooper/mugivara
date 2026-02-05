from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from config import settings
from public_site.views_table import table_add_to_cart, table_menu, table_cart, table_checkout, table_success

from django.conf.urls.static import static


urlpatterns = [
    path("i18n/", __import__("django.conf.urls.i18n").conf.urls.i18n.set_language, name="set_language"),
]

urlpatterns += i18n_patterns(
    path("admin/", admin.site.urls),
    path("", include("public_site.urls")),
    
    
     path("t/<str:token>/menu/", table_menu, name="table_menu"),
    path("t/<str:token>/add/<int:branch_item_id>/", table_add_to_cart, name="table_add_to_cart"),
    path("t/<str:token>/cart/", table_cart, name="table_cart"),
    path("t/<str:token>/checkout/", table_checkout, name="table_checkout"),
    path("t/<str:token>/success/<int:order_id>/", table_success, name="table_success"),

    # path("t/<str:token>/menu/", table_menu),
    # path("t/<str:token>/orders/", table_create_order),
    # path("t/<str:token>/menu/", table_menu, name="table_menu"),
    # path("t/<str:token>/cart/", table_cart, name="table_cart"),
    # path("t/<str:token>/checkout/", table_checkout, name="table_checkout"),
    # path("t/<str:token>/success/<int:order_id>/", table_success, name="table_success"),
)


if settings.DEBUG:
    # ВАЖНО: статика в DEV лучше так (из STATICFILES_DIRS и static/ внутри приложений)
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()

    # медиа (upload)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
admin.site.site_header = "Администрирование Санжи"
admin.site.site_title = "Санжи"
admin.site.index_title = "Панель управления"