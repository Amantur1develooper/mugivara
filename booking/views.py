from django.shortcuts import render

# Create your views here.
# from booking.models import Reservation

# locked_table_ids = Reservation.objects.filter(
#     released_at__isnull=True,
#     status__in=[Reservation.Status.PENDING, Reservation.Status.CONFIRMED],
# ).values_list("table_id", flat=True)

# free_tables = Table.objects.exclude(id__in=locked_table_ids)
