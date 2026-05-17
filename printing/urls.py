from django.urls import path
from . import views

urlpatterns = [
    path("jobs/",                views.api_jobs,      name="print_jobs"),
    path("jobs/<int:job_id>/ack/", views.api_job_ack, name="print_job_ack"),
    path("heartbeat/",           views.api_heartbeat, name="print_heartbeat"),
    path("config/",              views.api_config,    name="print_config"),
]
