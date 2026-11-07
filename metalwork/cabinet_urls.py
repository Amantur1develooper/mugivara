from django.urls import path

from . import cabinet_views as views

app_name = "mcabinet"

urlpatterns = [
    path("login/",  views.login_view,  name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("",        views.home,        name="home"),
    path("switch/<int:company_id>/", views.switch_company, name="switch_company"),

    path("product/add/",              views.product_form,   name="product_add"),
    path("product/<int:product_id>/", views.product_form,   name="product_edit"),
    path("product/<int:product_id>/toggle/", views.product_toggle, name="product_toggle"),
    path("product/<int:product_id>/delete/", views.product_delete, name="product_delete"),
    path("photo/<int:photo_id>/delete/",     views.photo_delete,   name="photo_delete"),

    path("categories/",        views.categories,      name="categories"),
    path("categories/add/",    views.category_add,    name="category_add"),
    path("categories/<int:category_id>/delete/", views.category_delete, name="category_delete"),

    path("leads/", views.leads, name="leads"),
    path("leads/<int:lead_id>/update/", views.lead_update, name="lead_update"),

    path("settings/", views.settings_view, name="settings"),
]
