from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("login/",  views.login_view,  name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("",        views.home,        name="home"),

    path("restaurant/<int:restaurant_id>/edit/", views.restaurant_edit, name="restaurant_edit"),

    path("branch/<int:branch_id>/edit/",  views.branch_edit,  name="branch_edit"),
    path("branch/<int:branch_id>/items/", views.branch_items, name="branch_items"),

    path("item/<int:branch_item_id>/price/",  views.update_item_price, name="update_price"),
    path("item/<int:branch_item_id>/toggle/", views.toggle_item,       name="toggle_item"),
]
