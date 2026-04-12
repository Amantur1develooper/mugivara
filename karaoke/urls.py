from django.urls import path
from . import views

urlpatterns = [
    path("",                              views.karaoke_list,    name="karaoke_list"),
    path("<slug:slug>/",                  views.karaoke_detail,  name="karaoke_detail"),
    path("<slug:slug>/menu/",             views.karaoke_menu,    name="karaoke_menu"),
    path("<slug:slug>/book/<int:room_id>/", views.karaoke_book,  name="karaoke_book"),
    path("<slug:slug>/slots/",            views.karaoke_slots,   name="karaoke_slots"),
]
