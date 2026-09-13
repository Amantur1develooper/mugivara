"""REST API, которым пользуется агент печати кассы магазина (shop_agent.py)."""
import json
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from .models import ShopPrintConfig, ShopPrintJob


def _authenticate(request):
    token = (request.headers.get("X-Print-Token") or request.GET.get("token") or "")
    if not token:
        return None, JsonResponse({"error": "No token"}, status=401)
    try:
        cfg = ShopPrintConfig.objects.select_related("branch").get(token=token, enabled=True)
        return cfg, None
    except ShopPrintConfig.DoesNotExist:
        return None, JsonResponse({"error": "Invalid token"}, status=401)


@require_GET
def api_jobs(request):
    """GET /api/shop-print/jobs/ — агент забирает новые задания."""
    cfg, err = _authenticate(request)
    if err:
        return err
    jobs = ShopPrintJob.objects.filter(branch=cfg.branch, status=ShopPrintJob.Status.NEW)[:20]
    data = [{"id": j.id, "content": j.content, "created_at": j.created_at.isoformat()} for j in jobs]
    return JsonResponse({"jobs": data})


@csrf_exempt
def api_job_ack(request, job_id):
    """POST /api/shop-print/jobs/<id>/ack/ — агент сообщает результат печати."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    cfg, err = _authenticate(request)
    if err:
        return err
    try:
        job = ShopPrintJob.objects.get(id=job_id, branch=cfg.branch)
    except ShopPrintJob.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    body = json.loads(request.body or b"{}")
    if body.get("status") == "printed":
        job.status = ShopPrintJob.Status.PRINTED
        job.printed_at = timezone.now()
        job.error_message = ""
    else:
        job.error_message = body.get("error", "")
        job.retries += 1
        job.status = ShopPrintJob.Status.NEW if job.retries < 3 else ShopPrintJob.Status.ERROR
    job.save()
    return JsonResponse({"ok": True})


@csrf_exempt
def api_heartbeat(request):
    """POST /api/shop-print/heartbeat/ — heartbeat агента."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    cfg, err = _authenticate(request)
    if err:
        return err
    cfg.last_heartbeat = timezone.now()
    cfg.save(update_fields=["last_heartbeat"])
    pending = ShopPrintJob.objects.filter(branch=cfg.branch, status=ShopPrintJob.Status.NEW).count()
    return JsonResponse({"ok": True, "branch": cfg.branch.name_ru, "pending_jobs": pending})


@require_GET
def api_config(request):
    """GET /api/shop-print/config/ — агент получает настройки принтера."""
    cfg, err = _authenticate(request)
    if err:
        return err
    return JsonResponse({
        "branch": cfg.branch.name_ru,
        "printer": cfg.windows_printer,
        "print_mode": cfg.print_mode,
        "codepage": cfg.codepage,
    })
