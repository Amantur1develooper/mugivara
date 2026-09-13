from django.urls import path
from . import print_views

urlpatterns = [
    path("jobs/",                  print_views.api_jobs,      name="shop_print_jobs"),
    path("jobs/<int:job_id>/ack/", print_views.api_job_ack,   name="shop_print_job_ack"),
    path("heartbeat/",             print_views.api_heartbeat, name="shop_print_heartbeat"),
    path("config/",                print_views.api_config,    name="shop_print_config"),
]
