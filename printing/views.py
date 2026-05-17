import json
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import PrinterGroup, PrintJob, RestaurantPrintConfig


def _authenticate(request):
    """Return (config, error_response). Token from header or query param."""
    token = (
        request.headers.get("X-Print-Token")
        or request.GET.get("token")
    )
    if not token:
        return None, JsonResponse({"error": "No token"}, status=401)
    try:
        cfg = RestaurantPrintConfig.objects.select_related("restaurant").get(
            token=token, enabled=True
        )
        return cfg, None
    except RestaurantPrintConfig.DoesNotExist:
        return None, JsonResponse({"error": "Invalid token"}, status=401)


@require_GET
def api_jobs(request):
    """GET /api/print/jobs/  — агент забирает новые задания."""
    cfg, err = _authenticate(request)
    if err:
        return err

    jobs = (
        PrintJob.objects
        .filter(restaurant=cfg.restaurant, status=PrintJob.Status.NEW)
        .select_related("group")[:20]
    )
    data = [
        {
            "id": j.id,
            "group": j.group.name if j.group else None,
            "content": j.content,
            "created_at": j.created_at.isoformat(),
        }
        for j in jobs
    ]
    return JsonResponse({"jobs": data})


@csrf_exempt
def api_job_ack(request, job_id):
    """POST /api/print/jobs/<id>/ack/  — подтвердить печать или ошибку."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    cfg, err = _authenticate(request)
    if err:
        return err

    try:
        job = PrintJob.objects.get(id=job_id, restaurant=cfg.restaurant)
    except PrintJob.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    body = json.loads(request.body or b"{}")
    if body.get("status") == "printed":
        job.status = PrintJob.Status.PRINTED
        job.printed_at = timezone.now()
        job.error_message = ""
    else:
        job.status = PrintJob.Status.ERROR
        job.error_message = body.get("error", "")
        job.retries += 1
        # Если меньше 3 попыток — вернуть в NEW для повтора
        if job.retries < 3:
            job.status = PrintJob.Status.NEW

    job.save()
    return JsonResponse({"ok": True})


@csrf_exempt
def api_heartbeat(request):
    """POST /api/print/heartbeat/  — агент сообщает что живой."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    cfg, err = _authenticate(request)
    if err:
        return err

    cfg.last_heartbeat = timezone.now()
    cfg.save(update_fields=["last_heartbeat"])

    pending = PrintJob.objects.filter(
        restaurant=cfg.restaurant, status=PrintJob.Status.NEW
    ).count()

    return JsonResponse({
        "ok": True,
        "restaurant": cfg.restaurant.name_ru,
        "pending_jobs": pending,
    })


@require_GET
def api_config(request):
    """GET /api/print/config/  — агент получает конфиг принтеров."""
    cfg, err = _authenticate(request)
    if err:
        return err

    groups = PrinterGroup.objects.filter(
        restaurant=cfg.restaurant
    ).prefetch_related("printers")

    printers = {}
    for group in groups:
        active = [p.windows_name for p in group.printers.all() if p.is_active]
        if active:
            printers[group.name] = active[0]

    return JsonResponse({
        "restaurant_id": cfg.restaurant.id,
        "restaurant": cfg.restaurant.name_ru,
        "printers": printers,
    })
