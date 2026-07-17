from django.urls import path
from . import print_views

urlpatterns = [
    path("jobs/",             print_views.api_jobs,      name="sr_print_jobs"),
    path("jobs/<int:job_id>/ack/", print_views.api_job_ack,  name="sr_print_job_ack"),
    path("heartbeat/",        print_views.api_heartbeat, name="sr_print_heartbeat"),
    path("config/",           print_views.api_config,    name="sr_print_config"),
]
