from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from config import settings
from tables.views import table_menu, table_create_order
from django.conf.urls.static import static


urlpatterns = [
    path("i18n/", __import__("django.conf.urls.i18n").conf.urls.i18n.set_language, name="set_language"),
]

urlpatterns += i18n_patterns(
    path("admin/", admin.site.urls),
    
    path("", include("public_site.urls")),
    
    path("t/<str:token>/menu/", table_menu),
    path("t/<str:token>/orders/", table_create_order),
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