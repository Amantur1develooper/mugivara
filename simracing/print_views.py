"""REST API consumed by the simracing printer agent."""
import json
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from .models import SimRacingPrintConfig, SimRacingPrintJob


def _authenticate(request):
    token = (request.headers.get("X-Print-Token") or request.GET.get("token") or "")
    if not token:
        return None, JsonResponse({"error": "No token"}, status=401)
    try:
        cfg = SimRacingPrintConfig.objects.select_related("venue").get(token=token, enabled=True)
        return cfg, None
    except SimRacingPrintConfig.DoesNotExist:
        return None, JsonResponse({"error": "Invalid token"}, status=401)


@require_GET
def api_jobs(request):
    """GET /api/sr-print/jobs/ — agent fetches new jobs."""
    cfg, err = _authenticate(request)
    if err:
        return err
    jobs = (
        SimRacingPrintJob.objects
        .filter(venue=cfg.venue, status=SimRacingPrintJob.Status.NEW)[:20]
    )
    data = [
        {"id": j.id, "content": j.content, "created_at": j.created_at.isoformat()}
        for j in jobs
    ]
    return JsonResponse({"jobs": data})


@csrf_exempt
def api_job_ack(request, job_id):
    """POST /api/sr-print/jobs/<id>/ack/ — agent reports result."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    cfg, err = _authenticate(request)
    if err:
        return err
    try:
        job = SimRacingPrintJob.objects.get(id=job_id, venue=cfg.venue)
    except SimRacingPrintJob.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    body = json.loads(request.body or b"{}")
    if body.get("status") == "printed":
        job.status = SimRacingPrintJob.Status.PRINTED
        job.printed_at = timezone.now()
        job.error_message = ""
    else:
        job.error_message = body.get("error", "")
        job.retries += 1
        job.status = (SimRacingPrintJob.Status.NEW
                      if job.retries < 3
                      else SimRacingPrintJob.Status.ERROR)
    job.save()
    return JsonResponse({"ok": True})


@csrf_exempt
def api_heartbeat(request):
    """POST /api/sr-print/heartbeat/ — agent heartbeat."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    cfg, err = _authenticate(request)
    if err:
        return err
    cfg.last_heartbeat = timezone.now()
    cfg.save(update_fields=["last_heartbeat"])
    pending = SimRacingPrintJob.objects.filter(
        venue=cfg.venue, status=SimRacingPrintJob.Status.NEW
    ).count()
    return JsonResponse({"ok": True, "venue": cfg.venue.name, "pending_jobs": pending})


@require_GET
def api_config(request):
    """GET /api/sr-print/config/ — agent gets printer config."""
    cfg, err = _authenticate(request)
    if err:
        return err
    return JsonResponse({
        "venue": cfg.venue.name,
        "printer": cfg.windows_printer,
        "print_mode": cfg.print_mode,
        "codepage": cfg.codepage,
    })
