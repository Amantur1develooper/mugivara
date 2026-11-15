from django.urls import path

from . import print_views

urlpatterns = [
    path("jobs/",                  print_views.api_jobs,      name="bs_print_jobs"),
    path("jobs/<int:job_id>/ack/", print_views.api_job_ack,   name="bs_print_job_ack"),
    path("heartbeat/",             print_views.api_heartbeat, name="bs_print_heartbeat"),
    path("config/",                print_views.api_config,    name="bs_print_config"),
]
