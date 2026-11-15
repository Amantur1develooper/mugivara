"""REST API агента печати барбершопа — тот же протокол, что у кассы магазина."""
import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from .models import BarbershopPrintConfig, BarbershopPrintJob


def _authenticate(request):
    token = (request.headers.get("X-Print-Token") or request.GET.get("token") or "")
    if not token:
        return None, JsonResponse({"error": "No token"}, status=401)
    cfg = (BarbershopPrintConfig.objects.select_related("barbershop")
           .filter(token=token, enabled=True).first())
    if not cfg:
        return None, JsonResponse({"error": "Invalid token"}, status=401)
    return cfg, None


@require_GET
def api_jobs(request):
    """GET /api/bs-print/jobs/ — агент забирает новые задания."""
    cfg, err = _authenticate(request)
    if err:
        return err
    jobs = BarbershopPrintJob.objects.filter(
        barbershop=cfg.barbershop, status=BarbershopPrintJob.Status.NEW)[:20]
    return JsonResponse({"jobs": [
        {"id": j.id, "content": j.content, "created_at": j.created_at.isoformat()}
        for j in jobs
    ]})


@csrf_exempt
def api_job_ack(request, job_id):
    """POST /api/bs-print/jobs/<id>/ack/ — агент сообщает результат печати."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    cfg, err = _authenticate(request)
    if err:
        return err
    job = BarbershopPrintJob.objects.filter(id=job_id, barbershop=cfg.barbershop).first()
    if not job:
        return JsonResponse({"error": "Not found"}, status=404)

    body = json.loads(request.body or b"{}")
    if body.get("status") == "printed":
        job.status = BarbershopPrintJob.Status.PRINTED
        job.printed_at = timezone.now()
        job.error_message = ""
    else:
        job.error_message = body.get("error", "")
        job.retries += 1
        job.status = (BarbershopPrintJob.Status.NEW if job.retries < 3
                      else BarbershopPrintJob.Status.ERROR)
    job.save()
    return JsonResponse({"ok": True})


@csrf_exempt
def api_heartbeat(request):
    """POST /api/bs-print/heartbeat/ — агент отмечается, что жив."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    cfg, err = _authenticate(request)
    if err:
        return err
    cfg.last_heartbeat = timezone.now()
    cfg.save(update_fields=["last_heartbeat"])
    pending = BarbershopPrintJob.objects.filter(
        barbershop=cfg.barbershop, status=BarbershopPrintJob.Status.NEW).count()
    return JsonResponse({"ok": True, "barbershop": cfg.barbershop.name,
                         "pending_jobs": pending})


@require_GET
def api_config(request):
    """GET /api/bs-print/config/ — настройки принтера для агента."""
    cfg, err = _authenticate(request)
    if err:
        return err
    return JsonResponse({
        "barbershop": cfg.barbershop.name,
        "printer": cfg.windows_printer,
        "print_mode": cfg.print_mode,
        "codepage": cfg.codepage,
    })
