from django.urls import path
from . import views

app_name = "hotels"

urlpatterns = [
    path("", views.hotel_list, name="hotel_list"),
    path("branch/<int:branch_id>/", views.hotel_branch, name="hotel_branch"),
    path("room/<int:room_id>/book/", views.room_book, name="room_book"),
    path("<slug:slug>/", views.hotel_detail, name="hotel_detail"),
]
