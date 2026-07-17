from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from config import settings
from public_site.views_table import table_call_waiter, table_cart_update, table_add_to_cart, table_create_order, table_menu, table_cart, table_checkout, table_success
from django.conf.urls.static import static

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView
from api.auth_views import register_view, login_view, me_view, change_password_view

urlpatterns = [
    path("i18n/", __import__("django.conf.urls.i18n").conf.urls.i18n.set_language, name="set_language"),
    path("api/print/",    include("printing.urls")),
    path("api/sr-print/", include("simracing.print_urls")),

    # Swagger / OpenAPI
    path("api/schema/",  SpectacularAPIView.as_view(),                        name="schema"),
    path("api/docs/",    SpectacularSwaggerView.as_view(url_name="schema"),   name="swagger-ui"),

    # Auth
    path("api/auth/register/",        register_view,              name="api-register"),
    path("api/auth/login/",           login_view,                 name="api-login"),
    path("api/auth/refresh/",         TokenRefreshView.as_view(), name="api-token-refresh"),
    path("api/auth/me/",              me_view,                    name="api-me"),
    path("api/auth/change-password/", change_password_view,       name="api-change-password"),

    # REST API v1
    path("api/v1/", include("api.v1.urls")),

    # ── QR-стол: без языкового префикса, без редиректа на язык браузера ──────
    path("t/<str:token>/menu/",                       table_menu,         name="table_menu"),
    path("t/<str:token>/cart/",                       table_cart,         name="table_cart"),
    path("t/<str:token>/cart/update/",                table_cart_update,  name="table_cart_update"),
    path("t/<str:token>/call-waiter/",                table_call_waiter,  name="table_call_waiter"),
    path("t/<str:token>/add/<int:branch_item_id>/",   table_add_to_cart,  name="table_add_to_cart"),
    path("t/<str:token>/checkout/",                   table_checkout,     name="table_checkout"),
    path("t/<str:token>/success/<int:order_id>/",     table_success,      name="table_success"),
    path("t/<str:token>/order/create/",               table_create_order, name="table_create_order"),
]

urlpatterns += i18n_patterns(
    path("admin/", admin.site.urls),

    path("pharmacy/", include(("pharmacy.urls", "pharmacy"), namespace="pharmacy")),
    path("shops/", include(("shops.urls", "shops"), namespace="shops")),
    path("hotels/", include(("hotels.urls", "hotels"), namespace="hotels")),
    path("markets/", include(("markets.urls", "markets"), namespace="markets")),
    path("legal/", include(("legal.urls", "legal"), namespace="legal")),
    path("agency/", include(("agency.urls", "agency"), namespace="agency")),
    path("entertainment/karaoke/", include(("karaoke.urls", "karaoke"), namespace="karaoke")),
    path("barbershop/", include(("barbershop.urls", "barbershop"), namespace="barbershop")),
    path("simracing/", include(("simracing.urls", "simracing"), namespace="simracing")),
    path("eco/", include(("eco.urls", "eco"), namespace="eco")),
    path("printshop/", include(("printshop.urls", "printshop"), namespace="printshop")),
    path("cabinet/", include(("dashboard.urls", "dashboard"), namespace="dashboard")),
    path("", include("public_site.urls")),
)


if settings.DEBUG:
    # ВАЖНО: статика в DEV лучше так (из STATICFILES_DIRS и static/ внутри приложений)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
admin.site.site_header = "Администрирование Webordo"
admin.site.site_title = "Webordo"
admin.site.index_title = "Панель управления"