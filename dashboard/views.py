import secrets as _secrets
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.db import transaction
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from django.db.models import Count, Max, Sum, Q
from datetime import timedelta
from core.models import Restaurant, Branch, Membership, PromoCode, PageView
from catalog.models import (
    BranchItem, BranchCategory, BranchCategoryItem,
    Item, ItemCategory, Category, MenuSet, BranchMenuSet,
    DishConstructor, ConstructorGroup, ConstructorIngredient,
)
from catalog.services import ensure_links_for_branch_item
from reservations.models import Floor, Place


def _user_restaurants(user):
    ids = Membership.objects.filter(user=user).values_list("restaurant_id", flat=True)
    return Restaurant.objects.filter(id__in=ids)


def _has_branch_access(user, branch):
    return Membership.objects.filter(user=user, restaurant=branch.restaurant).exists()


# ── AUTH ─────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")

    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username", "").strip(),
            password=request.POST.get("password", ""),
        )
        if user:
            login(request, user)
            return redirect("dashboard:home")
        messages.error(request, "Неверный логин или пароль")

    return render(request, "dashboard/login.html")


def logout_view(request):
    logout(request)
    return redirect("dashboard:login")


# ── HOME ─────────────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def home(request):
    from orders.models import Order

    restaurants = _user_restaurants(request.user).prefetch_related("branches")

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start  = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    data = []
    for r in restaurants:
        branches = list(r.branches.filter(is_active=True).order_by("name_ru"))
        branch_ids = [b.id for b in branches]

        def _sum(qs):
            return qs.aggregate(s=Sum("total_amount"))["s"] or 0

        base = Order.objects.filter(branch_id__in=branch_ids).exclude(status=Order.Status.CANCELLED)
        rev = {
            "today":  _sum(base.filter(created_at__gte=today_start)),
            "week":   _sum(base.filter(created_at__gte=week_start)),
            "month":  _sum(base.filter(created_at__gte=month_start)),
            "today_cnt":  base.filter(created_at__gte=today_start).count(),
            "week_cnt":   base.filter(created_at__gte=week_start).count(),
            "month_cnt":  base.filter(created_at__gte=month_start).count(),
        }
        data.append({"restaurant": r, "branches": branches, "rev": rev})

    from karaoke.models import KaraokeVenue, KaraokeMembership
    user = request.user
    if user.is_staff or user.is_superuser:
        karaoke_venues = list(KaraokeVenue.objects.prefetch_related("rooms").all())
    else:
        ids = KaraokeMembership.objects.filter(user=user).values_list("venue_id", flat=True)
        karaoke_venues = list(KaraokeVenue.objects.filter(id__in=ids).prefetch_related("rooms"))

    return render(request, "dashboard/home.html", {"data": data, "karaoke_venues": karaoke_venues})


# ── RESTAURANT ───────────────────────────────────────────────────────────────

@require_POST
@login_required(login_url="dashboard:login")
def restaurant_create(request):
    if not request.user.is_superuser:
        messages.error(request, "Недостаточно прав для создания ресторана.")
        return redirect("dashboard:home")

    from django.utils.text import slugify
    import uuid
    from catalog.models import MenuSet, BranchMenuSet

    name = request.POST.get("name_ru", "").strip()
    if not name:
        messages.error(request, "Введите название")
        return redirect("dashboard:home")

    # Уникальный slug
    base_slug = slugify(name) or "restaurant"
    slug = base_slug
    if Restaurant.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

    restaurant = Restaurant.objects.create(name_ru=name, slug=slug, is_active=True)
    Membership.objects.create(user=request.user, restaurant=restaurant)

    branch = Branch.objects.create(restaurant=restaurant, name_ru=name, is_active=True)

    menu_set = MenuSet.objects.create(restaurant=restaurant, name="Основное меню", is_active=True)
    BranchMenuSet.objects.create(branch=branch, menu_set=menu_set)

    messages.success(request, f"Ресторан «{name}» создан")
    return redirect("dashboard:restaurant_edit", restaurant_id=restaurant.id)


@login_required(login_url="dashboard:login")
def restaurant_edit(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    if not Membership.objects.filter(user=request.user, restaurant=restaurant).exists():
        return redirect("dashboard:home")

    if request.method == "POST":
        name = request.POST.get("name_ru", "").strip()
        if name:
            restaurant.name_ru = name
        restaurant.about_ru     = request.POST.get("about_ru", "").strip()
        restaurant.external_url = request.POST.get("external_url", "").strip()
        restaurant.phone        = request.POST.get("phone", "").strip()
        restaurant.whatsapp     = request.POST.get("whatsapp", "").strip()
        restaurant.instagram    = request.POST.get("instagram", "").strip()
        restaurant.telegram     = request.POST.get("telegram", "").strip()
        restaurant.map_url      = request.POST.get("map_url", "").strip()
        restaurant.tiktok       = request.POST.get("tiktok", "").strip()

        logo = request.FILES.get("logo")
        if logo:
            restaurant.logo = logo

        restaurant.save()
        messages.success(request, "Данные ресторана сохранены")
        return redirect("dashboard:restaurant_edit", restaurant_id=restaurant.id)

    from printing.models import RestaurantPrintConfig, PrinterGroup
    print_cfg, _ = RestaurantPrintConfig.objects.get_or_create(restaurant=restaurant)
    printer_groups = PrinterGroup.objects.filter(restaurant=restaurant).prefetch_related("printers")

    return render(request, "dashboard/restaurant_edit.html", {
        "restaurant": restaurant,
        "print_cfg": print_cfg,
        "printer_groups": printer_groups,
    })


# ── PRINT CONFIG SAVE ─────────────────────────────────────────────────────────

@require_POST
@login_required(login_url="dashboard:login")
def restaurant_print_save(request, restaurant_id):
    from printing.models import RestaurantPrintConfig, PrinterGroup, Printer
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    if not Membership.objects.filter(user=request.user, restaurant=restaurant).exists():
        return redirect("dashboard:home")

    cfg, _ = RestaurantPrintConfig.objects.get_or_create(restaurant=restaurant)
    cfg.enabled = request.POST.get("printing_enabled") == "on"

    # Принтер итоговых чеков
    receipt_group_id = request.POST.get("receipt_printer_group_id") or None
    if receipt_group_id:
        try:
            cfg.receipt_printer_group = PrinterGroup.objects.get(
                id=int(receipt_group_id), restaurant=restaurant
            )
        except (PrinterGroup.DoesNotExist, ValueError):
            cfg.receipt_printer_group = None
    else:
        cfg.receipt_printer_group = None
    cfg.save()

    # Сохраняем группы принтеров
    group_codes = request.POST.getlist("group_code")
    group_names = request.POST.getlist("group_display")
    printer_names = request.POST.getlist("printer_windows_name")

    for code, display, win_name in zip(group_codes, group_names, printer_names):
        code = code.strip().lower()
        display = display.strip()
        win_name = win_name.strip()
        if not code or not display:
            continue
        group, _ = PrinterGroup.objects.get_or_create(
            restaurant=restaurant, name=code,
            defaults={"display_name": display},
        )
        group.display_name = display
        group.save(update_fields=["display_name"])
        if win_name:
            Printer.objects.update_or_create(
                restaurant=restaurant, group=group,
                defaults={"windows_name": win_name, "is_active": True},
            )

    messages.success(request, "Настройки печати сохранены")
    return redirect("dashboard:restaurant_edit", restaurant_id=restaurant.id)


# ── PRINT GROUP DELETE ────────────────────────────────────────────────────────

@require_POST
@login_required(login_url="dashboard:login")
def restaurant_print_group_delete(request, restaurant_id, group_id):
    from printing.models import PrinterGroup
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    if not Membership.objects.filter(user=request.user, restaurant=restaurant).exists():
        return redirect("dashboard:home")
    PrinterGroup.objects.filter(id=group_id, restaurant=restaurant).delete()
    return redirect("dashboard:restaurant_edit", restaurant_id=restaurant.id)


# ── DOWNLOAD PRINT CONFIG & AGENT ─────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def restaurant_print_download_config(request, restaurant_id):
    """Скачать готовый config.json для агента."""
    import json as _json
    from printing.models import RestaurantPrintConfig, PrinterGroup, Printer
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    if not Membership.objects.filter(user=request.user, restaurant=restaurant).exists():
        return redirect("dashboard:home")

    cfg, _ = RestaurantPrintConfig.objects.get_or_create(restaurant=restaurant)
    groups = PrinterGroup.objects.filter(restaurant=restaurant).prefetch_related("printers")

    printers = {}
    for g in groups:
        first = g.printers.filter(is_active=True).first()
        printers[g.name] = first.windows_name if first else "Имя принтера в Windows"

    server_url = request.build_absolute_uri("/").rstrip("/")

    data = {
        "server_url": server_url,
        "token": cfg.token,
        "poll_interval": 3,
        "heartbeat_interval": 30,
        "printers": printers if printers else {"kitchen": "XPrinter XP-80C"},
    }

    content = _json.dumps(data, ensure_ascii=False, indent=2)
    response = HttpResponse(content, content_type="application/json")
    response["Content-Disposition"] = 'attachment; filename="config.json"'
    return response


@login_required(login_url="dashboard:login")
def restaurant_print_download_agent(request, restaurant_id):
    """Генерирует и отдаёт agent.py с уже вписанным URL сервера."""
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    if not Membership.objects.filter(user=request.user, restaurant=restaurant).exists():
        return redirect("dashboard:home")

    server_url = request.build_absolute_uri("/").rstrip("/")

    content = f'''\
"""
WebOrdo Cloud Printer Agent
============================
Сервер: {server_url}

Установка:
    pip install requests pywin32

Запуск:
    python agent.py
"""

import json, logging, random, socket, struct, sys, time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Логирование ──────────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "agent.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("printer_agent")

CONFIG_PATH = Path(__file__).parent / "config.json"


# ── DNS fallback через Google 8.8.8.8 ────────────────────────────────────────
def _resolve_via_google(hostname):
    """Резолвит hostname через Google DNS 8.8.8.8 напрямую (UDP)."""
    try:
        tid = random.randint(0, 65535)
        header = struct.pack('>HHHHHH', tid, 0x0100, 1, 0, 0, 0)
        qname = b''.join(
            struct.pack('B', len(p)) + p.encode()
            for p in hostname.split('.')
        ) + b'\\x00'
        question = qname + struct.pack('>HH', 1, 1)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        try:
            sock.sendto(header + question, ('8.8.8.8', 53))
            data, _ = sock.recvfrom(512)
        finally:
            sock.close()
        pos = 12 + len(qname) + 4
        ancount = struct.unpack('>H', data[6:8])[0]
        for _ in range(ancount):
            if data[pos] & 0xC0 == 0xC0:
                pos += 2
            else:
                while data[pos]:
                    pos += data[pos] + 1
                pos += 1
            rtype, _, _, rdlen = struct.unpack('>HHIH', data[pos:pos + 10])
            pos += 10
            if rtype == 1 and rdlen == 4:
                return '.'.join(str(b) for b in data[pos:pos + 4])
            pos += rdlen
    except Exception:
        pass
    return None


_orig_getaddrinfo = socket.getaddrinfo


def _patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    try:
        return _orig_getaddrinfo(host, port, family, type, proto, flags)
    except socket.gaierror:
        ip = _resolve_via_google(host)
        if ip:
            log.info(f"DNS fallback: {{host}} → {{ip}} (8.8.8.8)")
            return _orig_getaddrinfo(ip, port, family, type, proto, flags)
        raise


socket.getaddrinfo = _patched_getaddrinfo


# ── Конфиг ───────────────────────────────────────────────────────────────────
def load_config():
    if not CONFIG_PATH.exists():
        log.error(f"ОШИБКА: config.json не найден: {{CONFIG_PATH}}")
        log.error("Скачайте config.json из личного кабинета ресторана.")
        input("Нажмите Enter для выхода...")
        sys.exit(1)
    try:
        with open(CONFIG_PATH, encoding="utf-8-sig") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        log.error(f"ОШИБКА: config.json повреждён: {{e}}")
        input("Нажмите Enter для выхода...")
        sys.exit(1)

    # Обязательные поля
    for key in ("server_url", "token"):
        if not cfg.get(key):
            log.error("ОШИБКА: в config.json отсутствует поле '" + key + "'. Скачайте config.json заново.")
            input("Нажмите Enter для выхода...")
            sys.exit(1)

    cfg["server_url"] = cfg["server_url"].rstrip("/")
    return cfg


# ── API клиент ───────────────────────────────────────────────────────────────
class ApiClient:
    def __init__(self, server_url, token):
        self.base = server_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers["X-Print-Token"] = token
        retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get_jobs(self):
        r = self.session.get(f"{{self.base}}/api/print/jobs/", timeout=15)
        r.raise_for_status()
        return r.json().get("jobs", [])

    def ack_job(self, job_id, status, error=""):
        payload = {{"status": status}}
        if error:
            payload["error"] = error[:300]
        self.session.post(
            f"{{self.base}}/api/print/jobs/{{job_id}}/ack/",
            json=payload, timeout=10,
        )

    def heartbeat(self):
        r = self.session.post(f"{{self.base}}/api/print/heartbeat/", timeout=10)
        r.raise_for_status()
        return r.json()

    def get_config(self):
        r = self.session.get(f"{{self.base}}/api/print/config/", timeout=10)
        r.raise_for_status()
        return r.json()


# ── Печать ───────────────────────────────────────────────────────────────────
def print_text_windows(printer_name, content):
    try:
        import win32print
    except ImportError:
        raise RuntimeError("pywin32 не установлен. Выполните: pip install pywin32")

    handle = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(handle, 1, ("Receipt", None, "RAW"))
        win32print.StartPagePrinter(handle)
        ESC      = b"\\x1b"
        init     = ESC + b"@"                   # ESC @ — сброс
        codepage = ESC + b"t\\x11"              # ESC t 17 — cp866 (кириллица)
        bold_on  = ESC + b"E\\x01"              # ESC E 1 — жирный вкл
        bold_off = ESC + b"E\\x00"              # ESC E 0 — жирный выкл
        feed     = ESC + b"d\\x04"              # отступ 4 строки
        cut      = b"\\x1d\\x56\\x00"           # GS V 0 — полный отрез
        beep     = b"\\x07\\x07\\x07"           # BEL x3 — звук после обрезки
        # Заменяем плейсхолдеры STX/ETX на реальные ESC/POS команды
        content = content.replace("\\x02", bold_on.decode("latin-1"))
        content = content.replace("\\x03", bold_off.decode("latin-1"))
        data = content.encode("cp866", errors="replace")
        win32print.WritePrinter(handle, init + codepage + data + feed + cut + beep)
        win32print.EndPagePrinter(handle)
    finally:
        win32print.EndDocPrinter(handle)
        win32print.ClosePrinter(handle)
    log.info(f"Напечатано на \'{{printer_name}}\'")


def print_job(job, printer_map):
    group        = job.get("group")
    content      = job.get("content", "")
    printer_name = printer_map.get(group) or next(iter(printer_map.values()), None)
    if not printer_name:
        raise RuntimeError(f"Нет принтера для группы \'{{group}}\'. Проверьте config.json")
    log.info(f"Печать job #{{job[\'id\']}} group={{group}} → \'{{printer_name}}\'")
    print_text_windows(printer_name, content)


# ── Основной цикл ────────────────────────────────────────────────────────────
def main():
    cfg = load_config()

    log.info("=" * 48)
    log.info("WebOrdo Printer Agent")
    log.info(f"Сервер:  {{cfg[\'server_url\']}}")
    log.info(f"Токен:   {{cfg[\'token\'][:8]}}...")
    log.info(f"Принтеры из конфига: {{cfg.get(\'printers\', {{}})}}")
    log.info("=" * 48)

    client = ApiClient(cfg["server_url"], cfg["token"])
    poll_interval      = cfg.get("poll_interval", 3)
    heartbeat_interval = cfg.get("heartbeat_interval", 30)
    printer_map        = dict(cfg.get("printers", {{}}))

    # Получаем актуальный список принтеров с сервера
    try:
        srv = client.get_config()
        printer_map.update(srv.get("printers", {{}}))
        log.info(f"Ресторан: {{srv.get(\'restaurant\')}}")
        log.info(f"Принтеры (с сервера): {{printer_map}}")
    except Exception as e:
        log.warning(f"Не удалось получить конфиг с сервера: {{e}}")
        log.warning(f"Используются принтеры из config.json: {{printer_map}}")

    if not printer_map:
        log.error("ОШИБКА: список принтеров пуст! Укажите принтер в config.json.")

    last_heartbeat = 0
    log.info("Агент запущен. Ожидание заданий...")

    while True:
        now = time.time()

        # Heartbeat
        if now - last_heartbeat >= heartbeat_interval:
            try:
                client.heartbeat()
                last_heartbeat = now
            except Exception as e:
                log.warning(f"Heartbeat: {{e}}")

        # Получаем задания
        try:
            jobs = client.get_jobs()
        except Exception as e:
            log.error(f"Ошибка получения заданий: {{e}}")
            time.sleep(poll_interval * 3)
            continue

        # Печатаем
        for job in jobs:
            jid = job["id"]
            try:
                print_job(job, printer_map)
                client.ack_job(jid, "printed")
                log.info(f"Job #{{jid}} — напечатано OK")
            except Exception as e:
                log.error(f"Job #{{jid}} — ОШИБКА ПЕЧАТИ: {{e}}")
                client.ack_job(jid, "error", str(e))

        time.sleep(poll_interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Агент остановлен")
    except Exception as e:
        log.error(f"Критическая ошибка: {{e}}")
        input("Нажмите Enter для выхода...")
'''

    response = HttpResponse(content.encode("utf-8"), content_type="text/x-python; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="agent.py"'
    return response


# ── CATEGORY PRINTER GROUP ────────────────────────────────────────────────────

@require_POST
@login_required(login_url="dashboard:login")
@require_POST
@login_required(login_url="dashboard:login")
def item_printer_group(request, bci_id):
    """AJAX: назначить группу принтера отдельному блюду (BranchCategoryItem)."""
    from printing.models import PrinterGroup
    bci = get_object_or_404(BranchCategoryItem, id=bci_id)
    if not _has_branch_access(request.user, bci.branch_category.branch):
        return JsonResponse({"ok": False}, status=403)

    group_id = request.POST.get("group_id") or None
    if group_id:
        try:
            group = PrinterGroup.objects.get(
                id=group_id, restaurant=bci.branch_category.branch.restaurant
            )
            bci.printer_group = group
        except PrinterGroup.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Группа не найдена"})
    else:
        bci.printer_group = None

    bci.save(update_fields=["printer_group"])
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url="dashboard:login")
def category_printer_group(request, bc_id):
    """AJAX: назначить группу принтера категории."""
    from printing.models import PrinterGroup
    bc = get_object_or_404(BranchCategory, id=bc_id)
    if not _has_branch_access(request.user, bc.branch):
        return JsonResponse({"ok": False}, status=403)

    group_id = request.POST.get("group_id") or None
    if group_id:
        try:
            group = PrinterGroup.objects.get(
                id=group_id, restaurant=bc.branch.restaurant
            )
            bc.printer_group = group
        except PrinterGroup.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Группа не найдена"})
    else:
        bc.printer_group = None

    bc.save(update_fields=["printer_group"])
    return JsonResponse({"ok": True})


# ── BRANCH SETTINGS ──────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def branch_edit(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:home")

    if request.method == "POST":
        def dec(key, default="0"):
            try:
                return Decimal(request.POST.get(key) or default)
            except InvalidOperation:
                return Decimal(default)

        branch.delivery_enabled          = request.POST.get("delivery_enabled") == "on"
        branch.min_order_amount          = dec("min_order_amount")
        branch.delivery_fee              = dec("delivery_fee")
        branch.pos_delivery_fee_enabled  = request.POST.get("pos_delivery_fee_enabled") == "on"
        branch.free_delivery_from        = dec("free_delivery_from")
        branch.is_open_24h         = request.POST.get("is_open_24h") == "on"
        branch.pay_cash_enabled    = request.POST.get("pay_cash_enabled") == "on"
        branch.pay_online_enabled  = request.POST.get("pay_online_enabled") == "on"

        ot = request.POST.get("open_time", "").strip()
        ct = request.POST.get("close_time", "").strip()
        branch.open_time  = ot or None
        branch.close_time = ct or None
        work_days_list = request.POST.getlist("work_days")
        branch.work_days = ",".join(work_days_list)

        branch.external_url = request.POST.get("external_url", "").strip()

        lat_raw = request.POST.get("lat", "").strip()
        lon_raw = request.POST.get("lon", "").strip()
        branch.lat = lat_raw if lat_raw else None
        branch.lon = lon_raw if lon_raw else None

        photo = request.FILES.get("promo_photo")
        if photo:
            branch.promo_photo = photo

        cover = request.FILES.get("cover_photo")
        if cover:
            branch.cover_photo = cover

        branch.save()

        c = getattr(branch, "photo_compression", None)
        if c:
            messages.success(
                request,
                f"Настройки сохранены | Фото акции: {c['before_kb']} KB → {c['after_kb']} KB "
                f"(−{c['saved_pct']}%, {c['orig_size']} → {c['new_size']})"
            )
        else:
            messages.success(request, "Настройки филиала сохранены")
        return redirect("dashboard:branch_edit", branch_id=branch.id)

    work_days_list = branch.work_days.split(",") if branch.work_days else ["0","1","2","3","4","5","6"]
    return render(request, "dashboard/branch_edit.html", {
        "branch": branch,
        "work_days_list": work_days_list,
    })


# ── BRANCH MENU (prices + list) ───────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def branch_items(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:home")

    categories = (
        BranchCategory.objects
        .filter(branch=branch, is_active=True)
        .select_related("category")
        .order_by("sort_order", "id")
    )

    from printing.models import PrinterGroup
    printer_groups = list(PrinterGroup.objects.filter(restaurant=branch.restaurant))

    menu = []
    for bc in categories:
        items = (
            BranchCategoryItem.objects
            .filter(branch_category=bc)
            .select_related("branch_item__item", "printer_group")
            .order_by("sort_order", "id")
        )
        menu.append({"category": bc, "items": list(items)})

    return render(request, "dashboard/branch_items.html", {
        "branch": branch,
        "menu": menu,
        "printer_groups": printer_groups,
    })


# ── ADD ITEM ─────────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def item_add(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:home")

    restaurant = branch.restaurant
    categories = (
        BranchCategory.objects
        .filter(branch=branch, is_active=True)
        .select_related("category")
        .order_by("sort_order", "id")
    )

    if request.method == "POST":
        name = request.POST.get("name_ru", "").strip()
        if not name:
            messages.error(request, "Укажите название блюда")
            return redirect("dashboard:item_add", branch_id=branch.id)

        try:
            price = Decimal(request.POST.get("price") or "0")
        except InvalidOperation:
            price = Decimal("0")

        description = request.POST.get("description_ru", "").strip()
        photo = request.FILES.get("photo")

        # создаём Item
        item = Item(
            restaurant=restaurant,
            name_ru=name,
            name_ky=request.POST.get("name_ky", "").strip(),
            name_en=request.POST.get("name_en", "").strip(),
            description_ru=description,
            description_ky=request.POST.get("description_ky", "").strip(),
            description_en=request.POST.get("description_en", "").strip(),
            base_price=price,
        )
        if photo:
            item.photo = photo
        item.save()

        # создаём BranchItem
        bi = BranchItem.objects.create(
            branch=branch,
            item=item,
            price=price,
            is_available=True,
        )

        # привязываем к категории если выбрана
        branch_cat_id = request.POST.get("branch_category_id")

        # создание новой категории inline
        if branch_cat_id == "__new__":
            new_cat_ru = request.POST.get("new_cat_ru", "").strip()
            if new_cat_ru:
                # Ищем или создаём глобальную Category в MenuSet ресторана
                menu_set = MenuSet.objects.filter(restaurant=restaurant).first()
                if not menu_set:
                    menu_set = MenuSet.objects.create(restaurant=restaurant, name="Меню")
                # Привязываем MenuSet к филиалу если ещё не привязан
                BranchMenuSet.objects.get_or_create(branch=branch, menu_set=menu_set)
                cat, _ = Category.objects.get_or_create(
                    menu_set=menu_set,
                    name_ru=new_cat_ru,
                    defaults={
                        "name_ky": request.POST.get("new_cat_ky", "").strip() or new_cat_ru,
                        "name_en": request.POST.get("new_cat_en", "").strip() or new_cat_ru,
                    },
                )
                max_order = BranchCategory.objects.filter(branch=branch).aggregate(m=Max("sort_order"))["m"] or 0
                bc, _ = BranchCategory.objects.get_or_create(
                    branch=branch,
                    category=cat,
                    defaults={"sort_order": max_order + 1, "is_active": True},
                )
                BranchCategoryItem.objects.get_or_create(
                    branch_category=bc, branch_item=bi, defaults={"sort_order": 0}
                )
                ItemCategory.objects.get_or_create(item=item, category=cat, defaults={"sort_order": 0})
            else:
                ensure_links_for_branch_item(bi)

        elif branch_cat_id:
            try:
                bc = BranchCategory.objects.get(id=branch_cat_id, branch=branch)
                ItemCategory.objects.get_or_create(
                    item=item, category=bc.category, defaults={"sort_order": 0}
                )
                BranchCategoryItem.objects.get_or_create(
                    branch_category=bc, branch_item=bi, defaults={"sort_order": 0}
                )
            except BranchCategory.DoesNotExist:
                pass
        else:
            ensure_links_for_branch_item(bi)

        messages.success(request, f"Блюдо «{name}» добавлено")
        return redirect("dashboard:branch_items", branch_id=branch.id)

    return render(request, "dashboard/item_add.html", {
        "branch": branch,
        "categories": categories,
    })


# ── EDIT ITEM ─────────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def item_edit(request, branch_item_id):
    bi = get_object_or_404(BranchItem, id=branch_item_id)
    if not _has_branch_access(request.user, bi.branch):
        return redirect("dashboard:home")

    item = bi.item
    branch = bi.branch

    branch_categories = (
        BranchCategory.objects
        .filter(branch=branch, is_active=True)
        .select_related("category")
        .order_by("sort_order", "id")
    )
    current_bci = bi.categories_in_branch.select_related("branch_category").first()
    current_cat_id = current_bci.branch_category_id if current_bci else None

    if request.method == "POST":
        name = request.POST.get("name_ru", "").strip()
        if name:
            item.name_ru = name
        item.name_ky = request.POST.get("name_ky", "").strip()
        item.name_en = request.POST.get("name_en", "").strip()
        item.description_ru = request.POST.get("description_ru", "").strip()
        item.description_ky = request.POST.get("description_ky", "").strip()
        item.description_en = request.POST.get("description_en", "").strip()

        try:
            bi.price = Decimal(request.POST.get("price") or "0")
        except InvalidOperation:
            pass
        bi.is_available = request.POST.get("is_available") == "on"

        photo = request.FILES.get("photo")
        if photo:
            item.photo = photo

        item.save()
        bi.save(update_fields=["price", "is_available", "updated_at"])

        # Update category assignment
        new_cat_id = request.POST.get("branch_category_id", "").strip()
        if new_cat_id:
            try:
                new_bc = BranchCategory.objects.get(id=int(new_cat_id), branch=branch)
                # Remove from all other categories in this branch, assign to new one
                bi.categories_in_branch.exclude(branch_category=new_bc).delete()
                BranchCategoryItem.objects.get_or_create(branch_category=new_bc, branch_item=bi)
            except (BranchCategory.DoesNotExist, ValueError):
                pass
        else:
            # "Без категории" — remove all category assignments
            bi.categories_in_branch.all().delete()

        messages.success(request, "Блюдо обновлено")
        return redirect("dashboard:branch_items", branch_id=bi.branch_id)

    return render(request, "dashboard/item_edit.html", {
        "bi": bi,
        "item": item,
        "branch_categories": branch_categories,
        "current_cat_id": current_cat_id,
    })


# ── AJAX: update price ────────────────────────────────────────────────────────

@require_POST
@login_required(login_url="dashboard:login")
def update_item_price(request, branch_item_id):
    bi = get_object_or_404(BranchItem, id=branch_item_id)
    if not _has_branch_access(request.user, bi.branch):
        return JsonResponse({"ok": False}, status=403)
    try:
        price = Decimal(request.POST.get("price", ""))
        if price < 0:
            raise ValueError
    except Exception:
        return JsonResponse({"ok": False, "error": "Некорректная цена"})

    bi.price = price
    bi.save(update_fields=["price", "updated_at"])
    return JsonResponse({"ok": True, "price": str(bi.price)})


# ── AJAX: toggle availability ─────────────────────────────────────────────────

@require_POST
@login_required(login_url="dashboard:login")
def toggle_item(request, branch_item_id):
    bi = get_object_or_404(BranchItem, id=branch_item_id)
    if not _has_branch_access(request.user, bi.branch):
        return JsonResponse({"ok": False}, status=403)

    bi.is_available = not bi.is_available
    bi.save(update_fields=["is_available", "updated_at"])
    return JsonResponse({"ok": True, "is_available": bi.is_available})


# ── PROMO CODES ───────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def promo_list(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:home")

    if request.method == "POST":
        code = request.POST.get("code", "").strip().upper()
        discount_type = request.POST.get("discount_type", "")
        discount_value = Decimal(request.POST.get("discount_value") or "0")
        valid_until = request.POST.get("valid_until") or None
        max_uses = int(request.POST.get("max_uses") or 0)

        if not code:
            messages.error(request, "Введите промокод")
        elif PromoCode.objects.filter(branch=branch, code=code).exists():
            messages.error(request, f"Промокод «{code}» уже существует")
        else:
            PromoCode.objects.create(
                branch=branch,
                code=code,
                discount_type=discount_type,
                discount_value=discount_value,
                valid_until=valid_until,
                max_uses=max_uses,
                is_active=True,
            )
            messages.success(request, f"Промокод «{code}» создан")
        return redirect("dashboard:promo_list", branch_id=branch.id)

    promos = PromoCode.objects.filter(branch=branch).order_by("-created_at")
    today = timezone.localdate()
    return render(request, "dashboard/promo_list.html", {
        "branch": branch,
        "promos": promos,
        "today": today,
        "discount_types": PromoCode.DiscountType.choices,
    })


@require_POST
@login_required(login_url="dashboard:login")
def promo_toggle(request, promo_id):
    promo = get_object_or_404(PromoCode, id=promo_id)
    if not _has_branch_access(request.user, promo.branch):
        return redirect("dashboard:home")
    promo.is_active = not promo.is_active
    promo.save(update_fields=["is_active", "updated_at"])
    return redirect("dashboard:promo_list", branch_id=promo.branch_id)


@require_POST
@login_required(login_url="dashboard:login")
def promo_delete(request, promo_id):
    promo = get_object_or_404(PromoCode, id=promo_id)
    if not _has_branch_access(request.user, promo.branch):
        return redirect("dashboard:home")
    promo.delete()
    messages.success(request, "Промокод удалён")
    return redirect("dashboard:promo_list", branch_id=promo.branch_id)



# ── ANALYTICS ────────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def analytics(request):
    from orders.models import Order
    from shops.models import StoreOrder, StoreMembership
    from pharmacy.models import PharmacyOrder, PharmacyMembership
    from hotels.models import HotelBooking, HotelMembership
    from django.db.models import Sum

    user     = request.user
    is_super = user.is_superuser

    now = timezone.now()
    period = request.GET.get("period", "30")
    try:
        days = int(period)
    except ValueError:
        days = 30
    days = max(1, min(days, 365))
    since = now - timedelta(days=days)

    # ── ID организаций пользователя ───────────────────────────────────────────
    if is_super:
        my_restaurant_ids = my_hotel_ids = my_store_ids = my_pharmacy_ids = None
    else:
        my_restaurant_ids = list(
            Membership.objects.filter(user=user).values_list("restaurant_id", flat=True)
        )
        my_hotel_ids = list(
            HotelMembership.objects.filter(user=user).values_list("hotel_id", flat=True)
        )
        my_store_ids = list(
            StoreMembership.objects.filter(user=user).values_list("store_id", flat=True)
        )
        my_pharmacy_ids = list(
            PharmacyMembership.objects.filter(user=user).values_list("pharmacy_id", flat=True)
        )

    # ── Посещаемость ──────────────────────────────────────────────────────────
    pv_qs = PageView.objects.filter(timestamp__gte=since)

    allowed_sections = None
    if not is_super:
        allowed_sections = set()
        if my_restaurant_ids: allowed_sections.add("restaurant")
        if my_hotel_ids:       allowed_sections.add("hotels")
        if my_store_ids:       allowed_sections.add("shops")
        if my_pharmacy_ids:    allowed_sections.add("pharmacy")
        if allowed_sections:
            pv_qs = pv_qs.filter(section__in=allowed_sections)

    by_section = (
        pv_qs.values("section")
             .annotate(total=Count("id"), unique=Count("ip_hash", distinct=True))
             .order_by("-total")
    )
    section_labels = dict(PageView.SECTION_CHOICES)
    sections_data = [
        {
            "section": row["section"],
            "label": section_labels.get(row["section"], row["section"]),
            "total": row["total"],
            "unique": row["unique"],
        }
        for row in by_section
    ]
    total_views  = pv_qs.count()
    total_unique = pv_qs.values("ip_hash").distinct().count()

    chart_days  = min(days, 60)
    chart_since = now - timedelta(days=chart_days)
    daily_qs = (
        PageView.objects
        .filter(timestamp__gte=chart_since)
        .extra(select={"day": "DATE(timestamp)"})
        .values("day")
        .annotate(cnt=Count("id"))
        .order_by("day")
    )
    if not is_super and allowed_sections:
        daily_qs = daily_qs.filter(section__in=allowed_sections)
    daily_labels = [str(r["day"]) for r in daily_qs]
    daily_values = [r["cnt"] for r in daily_qs]

    # ── Базовые queryset-ы заказов (уже отфильтрованы по доступу) ─────────────
    if is_super:
        rest_qs  = Order.objects.all()
        shop_qs  = StoreOrder.objects.all()
        ph_qs    = PharmacyOrder.objects.all()
        hotel_qs = HotelBooking.objects.all()
    else:
        rest_qs  = Order.objects.filter(branch__restaurant_id__in=my_restaurant_ids)
        shop_qs  = StoreOrder.objects.filter(branch__store_id__in=my_store_ids)
        ph_qs    = PharmacyOrder.objects.filter(branch__pharmacy_id__in=my_pharmacy_ids)
        hotel_qs = HotelBooking.objects.filter(branch__hotel_id__in=my_hotel_ids)

    def _agg(qs, name_field, revenue_field, period_since):
        rows_all = list(
            qs.values(name_field)
              .annotate(cnt=Count("id"), revenue=Sum(revenue_field))
              .order_by("-cnt")
        )
        total_all    = qs.count()
        total_period = qs.filter(created_at__gte=period_since).count()
        norm = [
            {"name": r[name_field] or "—", "cnt": r["cnt"], "revenue": r.get("revenue") or 0}
            for r in rows_all
        ]
        return norm, total_all, total_period

    rest_rows,  rest_total_all,  rest_total_period  = _agg(rest_qs,  "branch__restaurant__name_ru", "total_amount", since)
    shop_rows,  shop_total_all,  shop_total_period  = _agg(shop_qs,  "branch__store__name_ru",      "total",        since)
    ph_rows,    ph_total_all,    ph_total_period    = _agg(ph_qs,    "branch__pharmacy__name_ru",   "total_amount", since)
    hotel_rows, hotel_total_all, hotel_total_period = _agg(hotel_qs, "branch__hotel__name_ru",      "total",        since)

    grand_period = rest_total_period + shop_total_period + ph_total_period + hotel_total_period
    grand_all    = rest_total_all    + shop_total_all    + ph_total_all    + hotel_total_all

    all_order_sections = [
        {"icon": "🍽",  "label": "Рестораны", "total_period": rest_total_period,  "total_all": rest_total_all,  "rows_all": rest_rows},
        {"icon": "🏪",  "label": "Магазины",  "total_period": shop_total_period,  "total_all": shop_total_all,  "rows_all": shop_rows},
        {"icon": "💊",  "label": "Аптеки",    "total_period": ph_total_period,    "total_all": ph_total_all,    "rows_all": ph_rows},
        {"icon": "🏨",  "label": "Отели",     "total_period": hotel_total_period, "total_all": hotel_total_all, "rows_all": hotel_rows},
    ]

    # Обычный пользователь видит только разделы, к которым у него есть доступ и данные
    if not is_super:
        order_sections = [s for s in all_order_sections if s["total_all"] > 0]
    else:
        order_sections = all_order_sections

    return render(request, "dashboard/analytics.html", {
        "period": days,
        "is_super": is_super,
        "sections_data": sections_data,
        "total_views": total_views,
        "total_unique": total_unique,
        "daily_labels": daily_labels,
        "daily_values": daily_values,
        "order_sections": order_sections,
        "grand_period": grand_period,
        "grand_all": grand_all,
    })


# ── ORDERS ANALYTICS ─────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def orders_analytics(request):
    from orders.models import Order, OrderItem
    from django.db.models import Sum, Count
    from django.utils import timezone
    from datetime import timedelta, date

    user     = request.user
    is_super = user.is_superuser

    # ── фильтры ──────────────────────────────────────────────────────────────
    period = request.GET.get("period", "30")
    try:
        days = int(period)
    except ValueError:
        days = 30
    days = max(1, min(days, 365))

    now   = timezone.now()
    since = now - timedelta(days=days)

    # ── доступные рестораны ───────────────────────────────────────────────────
    if is_super:
        restaurants = Restaurant.objects.filter(branches__orders__isnull=False).distinct().order_by("name_ru")
        restaurant_id = request.GET.get("restaurant")
        if restaurant_id and restaurant_id.isdigit():
            order_qs = Order.objects.filter(branch__restaurant_id=int(restaurant_id))
        else:
            order_qs = Order.objects.all()
            restaurant_id = None
    else:
        my_ids = list(Membership.objects.filter(user=user).values_list("restaurant_id", flat=True))
        restaurants = Restaurant.objects.filter(id__in=my_ids).order_by("name_ru")
        order_qs    = Order.objects.filter(branch__restaurant_id__in=my_ids)
        restaurant_id = None

    # ── применяем фильтр по периоду ───────────────────────────────────────────
    order_qs_period = order_qs.filter(created_at__gte=since)

    # ── KPI ──────────────────────────────────────────────────────────────────
    total_orders  = order_qs_period.count()
    # Выручка — только стоимость блюд (без доставки)
    total_revenue = (
        OrderItem.objects
        .filter(order__in=order_qs_period)
        .aggregate(s=Sum("line_total"))["s"] or 0
    )
    total_items   = (
        OrderItem.objects
        .filter(order__in=order_qs_period)
        .aggregate(s=Sum("qty"))["s"] or 0
    )

    # ── топ блюд за период ────────────────────────────────────────────────────
    top_items = (
        OrderItem.objects
        .filter(order__in=order_qs_period)
        .values("item__name_ru")
        .annotate(qty_total=Sum("qty"), order_count=Count("order", distinct=True))
        .order_by("-qty_total")[:30]
    )

    # ── динамика по дням ──────────────────────────────────────────────────────
    chart_days  = min(days, 60)
    chart_since = now - timedelta(days=chart_days)
    daily_qs = (
        order_qs
        .filter(created_at__gte=chart_since)
        .extra(select={"day": 'DATE("orders_order"."created_at")'})
        .values("day")
        .annotate(cnt=Count("id", distinct=True), revenue=Sum("items__line_total"))
        .order_by("day")
    )
    chart_labels  = [str(r["day"]) for r in daily_qs]
    chart_orders  = [r["cnt"] for r in daily_qs]
    chart_revenue = [float(r["revenue"] or 0) for r in daily_qs]

    # ── список всех заказов (пагинация) ───────────────────────────────────────
    from django.core.paginator import Paginator

    orders_list = (
        order_qs_period
        .select_related("branch", "branch__restaurant")
        .prefetch_related("items__item")
        .annotate(items_total=Sum("items__line_total"))
        .order_by("-created_at")
    )
    paginator = Paginator(orders_list, 30)
    page_num  = request.GET.get("page", 1)
    page_obj  = paginator.get_page(page_num)

    return render(request, "dashboard/orders.html", {
        "period":        days,
        "is_super":      is_super,
        "restaurants":   restaurants,
        "restaurant_id": restaurant_id,
        "total_orders":  total_orders,
        "total_revenue": total_revenue,
        "total_items":   total_items,
        "top_items":     list(top_items),
        "chart_labels":  chart_labels,
        "chart_orders":  chart_orders,
        "chart_revenue": chart_revenue,
        "page_obj":      page_obj,
    })


# ── CATEGORIES ────────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def branch_categories(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:home")

    active_bcs = list(
        BranchCategory.objects
        .filter(branch=branch)
        .select_related("category__menu_set", "printer_group")
        .order_by("sort_order", "id")
    )
    added_cat_ids = {bc.category_id for bc in active_bcs}

    all_cats = (
        Category.objects
        .filter(menu_set__restaurant=branch.restaurant)
        .select_related("menu_set")
        .order_by("menu_set__name", "name_ru")
    )
    available_cats = [c for c in all_cats if c.id not in added_cat_ids]

    from printing.models import PrinterGroup
    printer_groups = list(PrinterGroup.objects.filter(restaurant=branch.restaurant))

    return render(request, "dashboard/branch_categories.html", {
        "branch": branch,
        "categories": active_bcs,
        "available_cats": available_cats,
        "printer_groups": printer_groups,
    })


@require_POST
@login_required(login_url="dashboard:login")
def category_add(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return JsonResponse({"ok": False}, status=403)

    category_id = request.POST.get("category_id")
    try:
        cat = Category.objects.select_related("menu_set").get(
            id=category_id, menu_set__restaurant=branch.restaurant
        )
        max_order = BranchCategory.objects.filter(branch=branch).aggregate(
            m=Max("sort_order")
        )["m"] or 0
        bc, created = BranchCategory.objects.get_or_create(
            branch=branch,
            category=cat,
            defaults={"sort_order": max_order + 10, "is_active": True},
        )
        return JsonResponse({
            "ok": True,
            "bc_id": bc.id,
            "cat_id": cat.id,
            "name": cat.name_ru,
            "menu_set": cat.menu_set.name,
            "sort_order": bc.sort_order,
            "is_active": bc.is_active,
        })
    except Category.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Категория не найдена"})


@require_POST
@login_required(login_url="dashboard:login")
def category_create(request, branch_id):
    """Create a brand-new Category for the restaurant and add it to the branch."""
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return JsonResponse({"ok": False}, status=403)

    name_ru = request.POST.get("name_ru", "").strip()
    if not name_ru:
        return JsonResponse({"ok": False, "error": "Введите название категории"})

    name_ky = request.POST.get("name_ky", "").strip()
    name_en = request.POST.get("name_en", "").strip()

    menu_set = (
        MenuSet.objects.filter(restaurant=branch.restaurant, is_active=True)
        .order_by("id")
        .first()
    )
    if not menu_set:
        return JsonResponse({"ok": False, "error": "У ресторана нет ни одного меню-сета"})

    cat = Category.objects.create(
        menu_set=menu_set,
        name_ru=name_ru,
        name_ky=name_ky,
        name_en=name_en,
    )

    max_order = BranchCategory.objects.filter(branch=branch).aggregate(m=Max("sort_order"))["m"] or 0
    bc = BranchCategory.objects.create(
        branch=branch,
        category=cat,
        sort_order=max_order + 10,
        is_active=True,
    )

    return JsonResponse({
        "ok": True,
        "bc_id": bc.id,
        "cat_id": cat.id,
        "name": cat.name_ru,
        "menu_set": menu_set.name,
        "sort_order": bc.sort_order,
    })


@require_POST
@login_required(login_url="dashboard:login")
def category_edit(request, cat_id):
    """Edit name fields of a Category (must belong to a restaurant the user can access)."""
    cat = get_object_or_404(Category, id=cat_id)
    if not Membership.objects.filter(user=request.user, restaurant=cat.menu_set.restaurant).exists():
        return JsonResponse({"ok": False}, status=403)

    name_ru = request.POST.get("name_ru", "").strip()
    if not name_ru:
        return JsonResponse({"ok": False, "error": "Название не может быть пустым"})

    cat.name_ru = name_ru
    cat.name_ky = request.POST.get("name_ky", "").strip()
    cat.name_en = request.POST.get("name_en", "").strip()
    cat.save(update_fields=["name_ru", "name_ky", "name_en", "updated_at"])

    return JsonResponse({"ok": True, "name_ru": cat.name_ru, "name_ky": cat.name_ky, "name_en": cat.name_en})


@require_POST
@login_required(login_url="dashboard:login")
def category_toggle(request, bc_id):
    bc = get_object_or_404(BranchCategory, id=bc_id)
    if not _has_branch_access(request.user, bc.branch):
        return JsonResponse({"ok": False}, status=403)
    bc.is_active = not bc.is_active
    bc.save(update_fields=["is_active", "updated_at"])
    return JsonResponse({"ok": True, "is_active": bc.is_active})


@require_POST
@login_required(login_url="dashboard:login")
def category_reorder(request, bc_id):
    bc = get_object_or_404(BranchCategory, id=bc_id)
    if not _has_branch_access(request.user, bc.branch):
        return JsonResponse({"ok": False}, status=403)
    try:
        sort_order = int(request.POST.get("sort_order", bc.sort_order))
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "invalid"})
    bc.sort_order = sort_order
    bc.save(update_fields=["sort_order", "updated_at"])
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url="dashboard:login")
def category_remove(request, bc_id):
    bc = get_object_or_404(BranchCategory, id=bc_id)
    if not _has_branch_access(request.user, bc.branch):
        return JsonResponse({"ok": False}, status=403)
    bc.delete()
    return JsonResponse({"ok": True})


# ── MENU SETS (сеты категорий) ────────────────────────────────────────────────

def _has_restaurant_access(user, restaurant):
    if user.is_superuser:
        return True
    return Membership.objects.filter(user=user, restaurant=restaurant).exists()


@login_required(login_url="dashboard:login")
def menu_sets(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    if not _has_restaurant_access(request.user, restaurant):
        return redirect("dashboard:home")
    sets = (
        MenuSet.objects
        .filter(restaurant=restaurant)
        .prefetch_related("categories")
        .order_by("id")
    )
    return render(request, "dashboard/menu_sets.html", {
        "restaurant": restaurant,
        "sets": sets,
    })


@require_POST
@login_required(login_url="dashboard:login")
def menu_set_add(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    if not _has_restaurant_access(request.user, restaurant):
        return JsonResponse({"ok": False}, status=403)
    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Укажите название сета"})
    ms = MenuSet.objects.create(restaurant=restaurant, name=name, is_active=True)
    return JsonResponse({"ok": True, "id": ms.id, "name": ms.name})


@require_POST
@login_required(login_url="dashboard:login")
def menu_set_rename(request, menu_set_id):
    ms = get_object_or_404(MenuSet, id=menu_set_id)
    if not _has_restaurant_access(request.user, ms.restaurant):
        return JsonResponse({"ok": False}, status=403)
    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Название не может быть пустым"})
    ms.name = name
    ms.save(update_fields=["name", "updated_at"])
    return JsonResponse({"ok": True, "name": ms.name})


@require_POST
@login_required(login_url="dashboard:login")
def menu_set_delete(request, menu_set_id):
    ms = get_object_or_404(MenuSet, id=menu_set_id)
    if not _has_restaurant_access(request.user, ms.restaurant):
        return JsonResponse({"ok": False}, status=403)
    ms.delete()
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url="dashboard:login")
def ms_category_add(request, menu_set_id):
    ms = get_object_or_404(MenuSet, id=menu_set_id)
    if not _has_restaurant_access(request.user, ms.restaurant):
        return JsonResponse({"ok": False}, status=403)
    name_ru = request.POST.get("name_ru", "").strip()
    if not name_ru:
        return JsonResponse({"ok": False, "error": "Укажите название категории"})
    cat = Category.objects.create(
        menu_set=ms,
        name_ru=name_ru,
        name_ky=request.POST.get("name_ky", "").strip(),
        name_en=request.POST.get("name_en", "").strip(),
    )
    return JsonResponse({"ok": True, "id": cat.id, "name_ru": cat.name_ru,
                         "name_ky": cat.name_ky, "name_en": cat.name_en})


@require_POST
@login_required(login_url="dashboard:login")
def ms_category_edit(request, category_id):
    cat = get_object_or_404(Category, id=category_id)
    if not _has_restaurant_access(request.user, cat.menu_set.restaurant):
        return JsonResponse({"ok": False}, status=403)
    name_ru = request.POST.get("name_ru", "").strip()
    if not name_ru:
        return JsonResponse({"ok": False, "error": "Название не может быть пустым"})
    cat.name_ru = name_ru
    cat.name_ky = request.POST.get("name_ky", "").strip()
    cat.name_en = request.POST.get("name_en", "").strip()
    cat.save(update_fields=["name_ru", "name_ky", "name_en", "updated_at"])
    return JsonResponse({"ok": True, "name_ru": cat.name_ru,
                         "name_ky": cat.name_ky, "name_en": cat.name_en})


@require_POST
@login_required(login_url="dashboard:login")
def ms_category_delete(request, category_id):
    cat = get_object_or_404(Category, id=category_id)
    if not _has_restaurant_access(request.user, cat.menu_set.restaurant):
        return JsonResponse({"ok": False}, status=403)
    cat.delete()
    return JsonResponse({"ok": True})


# ── TABLES (столики) ──────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def branch_tables(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:home")
    floors = branch.floors.prefetch_related("places").order_by("sort_order", "id")
    return render(request, "dashboard/tables.html", {"branch": branch, "floors": floors})


@require_POST
@login_required(login_url="dashboard:login")
def floor_add(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return JsonResponse({"ok": False}, status=403)
    name = request.POST.get("name", "").strip() or "Зал"
    floor = Floor.objects.create(branch=branch, name_ru=name)
    return JsonResponse({"ok": True, "id": floor.id, "name": floor.name_ru})


@require_POST
@login_required(login_url="dashboard:login")
def floor_delete(request, floor_id):
    floor = get_object_or_404(Floor, id=floor_id)
    if not _has_branch_access(request.user, floor.branch):
        return JsonResponse({"ok": False}, status=403)
    floor.delete()
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url="dashboard:login")
def table_add(request, floor_id):
    floor = get_object_or_404(Floor, id=floor_id)
    if not _has_branch_access(request.user, floor.branch):
        return JsonResponse({"ok": False}, status=403)

    seats = max(1, int(request.POST.get("seats") or 2))
    bulk = request.POST.get("bulk") == "1"
    created = []

    if bulk:
        prefix = request.POST.get("prefix", "Стол").strip() or "Стол"
        start  = max(1, int(request.POST.get("start") or 1))
        count  = min(50, max(1, int(request.POST.get("count") or 1)))
        for i in range(start, start + count):
            p = Place.objects.create(floor=floor, title=f"{prefix} {i}", seats=seats)
            created.append({"id": p.id, "title": p.title, "seats": p.seats, "token": p.token})
    else:
        title = request.POST.get("title", "").strip()
        if not title:
            return JsonResponse({"ok": False, "error": "Название обязательно"})
        p = Place.objects.create(floor=floor, title=title, seats=seats)
        created.append({"id": p.id, "title": p.title, "seats": p.seats, "token": p.token})

    return JsonResponse({"ok": True, "tables": created})


@require_POST
@login_required(login_url="dashboard:login")
def table_delete(request, table_id):
    place = get_object_or_404(Place, id=table_id)
    if not _has_branch_access(request.user, place.floor.branch):
        return JsonResponse({"ok": False}, status=403)
    place.delete()
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url="dashboard:login")
def table_regen_token(request, table_id):
    if not request.user.is_superuser:
        return JsonResponse({"ok": False, "error": "Только суперпользователь"}, status=403)
    place = get_object_or_404(Place, id=table_id)
    new_token = request.POST.get("token", "").strip()
    if new_token:
        if Place.objects.filter(token=new_token).exclude(id=table_id).exists():
            return JsonResponse({"ok": False, "error": "Этот токен уже занят другим столом"})
        place.token = new_token
    else:
        place.token = _secrets.token_urlsafe(10)[:20]
    place.save(update_fields=["token"])
    return JsonResponse({"ok": True, "token": place.token})


# ══════════════════════════════════════════════════════════════════════════════
# POS — КАССА
# ══════════════════════════════════════════════════════════════════════════════

import json as _json
from orders.models import Order, OrderItem
from django.db.models import Prefetch as _Prefetch


@login_required(login_url="dashboard:login")
def pos(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, branch)):
        return redirect("dashboard:home")

    categories = (
        BranchCategory.objects
        .filter(branch=branch, is_active=True)
        .select_related("category")
        .prefetch_related(
            _Prefetch(
                "items_in_category",
                queryset=(
                    BranchCategoryItem.objects
                    .select_related("branch_item__item")
                    .filter(branch_item__is_available=True)
                    .order_by("sort_order")
                ),
            )
        )
        .order_by("sort_order")
    )

    live_orders = (
        Order.objects
        .filter(branch=branch, status__in=[
            Order.Status.NEW, Order.Status.ACCEPTED,
            Order.Status.COOKING, Order.Status.READY,
        ])
        .prefetch_related("items__item")
        .order_by("-created_at")
    )

    # Столы и открытые заказы по столам
    try:
        from reservations.models import Place
        places_qs = list(
            Place.objects
            .filter(floor__branch=branch, is_active=True)
            .order_by("floor__name", "title")
        )
        open_table_order_map = {}
        for o in live_orders:
            tid = getattr(o, "table_place_id", None)
            if tid and tid not in open_table_order_map:
                open_table_order_map[tid] = o
        for place in places_qs:
            place.open_order = open_table_order_map.get(place.id)
    except Exception:
        places_qs = []

    return render(request, "dashboard/pos.html", {
        "branch": branch,
        "categories": categories,
        "live_orders": live_orders,
        "places": places_qs,
        "pos_delivery_fee": int(branch.delivery_fee) if branch.pos_delivery_fee_enabled else 0,
        "pos_delivery_fee_enabled": branch.pos_delivery_fee_enabled,
    })


@require_POST
@login_required(login_url="dashboard:login")
@transaction.atomic
def pos_order_create(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, branch)):
        return JsonResponse({"ok": False}, status=403)

    try:
        data = _json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "error": "bad json"}, status=400)

    items_data      = data.get("items", [])
    order_type      = data.get("type", Order.Type.DINE_IN)
    payment_method  = data.get("payment", Order.PaymentMethod.CASH)
    customer_name   = (data.get("name") or "").strip()
    comment         = (data.get("comment") or "").strip()
    table_place_id  = data.get("table_place_id") or None

    if not items_data:
        return JsonResponse({"ok": False, "error": "Нет позиций"}, status=400)

    # Стол: если выбран — привязываем к заказу
    table_place = None
    if table_place_id and order_type == Order.Type.DINE_IN:
        from reservations.models import Place
        try:
            table_place = Place.objects.get(id=int(table_place_id), floor__branch=branch)
        except (Place.DoesNotExist, ValueError):
            pass

    _OPEN = [Order.Status.NEW, Order.Status.ACCEPTED, Order.Status.COOKING, Order.Status.READY]

    # Delivery fee: добавляем если тип=доставка и включено в настройках филиала
    applied_delivery_fee = Decimal("0")
    if (order_type == Order.Type.DELIVERY
            and branch.pos_delivery_fee_enabled
            and branch.delivery_fee > 0):
        applied_delivery_fee = branch.delivery_fee

    # Pre-calculate items and total
    total = Decimal("0")
    prepared_items = []
    for it in items_data:
        try:
            bi  = BranchItem.objects.select_related("item").get(
                id=int(it["bi_id"]), branch=branch, is_available=True
            )
            qty = max(1, int(it.get("qty", 1)))
            line = bi.price * qty
            prepared_items.append({"bi": bi, "qty": qty, "line": line})
            total += line
        except (BranchItem.DoesNotExist, ValueError, KeyError):
            continue

    with transaction.atomic():
        # If a table is selected, try to add to existing open order
        existing_order = None
        if table_place:
            existing_order = (
                Order.objects
                .filter(branch=branch, table_place=table_place, status__in=_OPEN)
                .select_for_update()
                .order_by("-created_at")
                .first()
            )

        if existing_order:
            order = existing_order
            new_oi_ids = []
            for pit in prepared_items:
                oi = OrderItem.objects.create(
                    order=order, item=pit["bi"].item,
                    qty=pit["qty"], price_snapshot=pit["bi"].price, line_total=pit["line"],
                )
                new_oi_ids.append(oi.id)
                bi = pit["bi"]
                if bi.stock is not None:
                    bi.stock = max(0, bi.stock - pit["qty"])
                    if bi.stock == 0:
                        bi.is_available = False
                    bi.save(update_fields=["stock", "is_available"])
            order.total_amount = order.total_amount + total
            order.save(update_fields=["total_amount"])
            open_table = True
        else:
            order = Order.objects.create(
                branch=branch,
                type=order_type,
                status=Order.Status.NEW,
                payment_method=payment_method,
                customer_name=customer_name,
                comment=comment,
                table_place=table_place,
            )
            for pit in prepared_items:
                OrderItem.objects.create(
                    order=order, item=pit["bi"].item,
                    qty=pit["qty"], price_snapshot=pit["bi"].price, line_total=pit["line"],
                )
                bi = pit["bi"]
                if bi.stock is not None:
                    bi.stock = max(0, bi.stock - pit["qty"])
                    if bi.stock == 0:
                        bi.is_available = False
                    bi.save(update_fields=["stock", "is_available"])

            order.delivery_fee   = applied_delivery_fee
            order.total_amount   = total + applied_delivery_fee

            # Заказ в зале со столом → оставляем ОТКРЫТЫМ
            # Остальные типы → сразу закрываем
            if table_place:
                order.save(update_fields=["total_amount", "delivery_fee"])
                open_table = True
            else:
                order.status = Order.Status.CLOSED
                order.payment_status = Order.PaymentStatus.PAID
                order.save(update_fields=["total_amount", "delivery_fee", "status", "payment_status"])
                open_table = False

    # Облачная печать — запускаем ПОСЛЕ коммита транзакции
    _order_id   = order.id
    _ex_order   = bool(existing_order)
    _new_oi_ids = list(new_oi_ids) if existing_order else None

    def _do_print():
        try:
            from printing.jobs import create_print_jobs
            from orders.models import Order as _Order
            _order = (
                _Order.objects
                .select_related("table_place__floor", "branch__restaurant")
                .get(id=_order_id)
            )
            if _ex_order:
                create_print_jobs(_order, new_item_ids=_new_oi_ids, new_cx_ids=[])
            else:
                create_print_jobs(_order)
        except Exception as e:
            import traceback
            print("PRINT create_print_jobs ERROR (pos):", e)
            traceback.print_exc()

    transaction.on_commit(_do_print)

    # Telegram уведомление
    # Для нового заказа — сигнал integrations/signals.py отправляет уведомление автоматически.
    # Здесь отправляем только дозаказ на стол (signal не срабатывает, т.к. Order не создаётся).
    if existing_order and table_place:
        try:
            from integrations.tasks import notify_extra_order
            new_items_tg = [
                {"name": pit["bi"].item.name_ru, "qty": pit["qty"]}
                for pit in prepared_items
            ]
            if new_items_tg:
                notify_extra_order.delay(order.id, new_items_tg)
        except Exception as e:
            print("TG notify_extra_order ERROR:", e)

    return JsonResponse({
        "ok": True,
        "order_id": order.id,
        "total": str(total + applied_delivery_fee),
        "items_total": str(total),
        "delivery_fee": str(applied_delivery_fee),
        "open_table": open_table,
        "table_place_id": table_place.id if table_place else None,
    })


@require_POST
@login_required(login_url="dashboard:login")
def pos_table_close(request, order_id):
    """Закрыть счёт стола — принять оплату. Закрывает ВСЕ открытые заказы на столе."""
    order = get_object_or_404(Order, id=order_id)
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, order.branch)):
        return JsonResponse({"ok": False}, status=403)

    if order.status == Order.Status.CLOSED:
        return JsonResponse({"ok": False, "error": "Уже закрыт"})

    try:
        data = _json.loads(request.body)
    except Exception:
        data = {}

    payment_method = data.get("payment", order.payment_method)

    _OPEN = [Order.Status.NEW, Order.Status.ACCEPTED, Order.Status.COOKING, Order.Status.READY]

    with transaction.atomic():
        if order.table_place_id:
            all_open = list(
                Order.objects.select_for_update().filter(
                    branch=order.branch,
                    table_place_id=order.table_place_id,
                    status__in=_OPEN,
                )
            )
        else:
            all_open = [order]

        combined_total = Decimal("0")
        for o in all_open:
            o.payment_method = payment_method
            o.status = Order.Status.CLOSED
            o.payment_status = Order.PaymentStatus.PAID
            o.save(update_fields=["status", "payment_status", "payment_method"])
            combined_total += o.total_amount

        order.total_amount = combined_total
        order.save(update_fields=["total_amount"])

    # Печать чека покупателя
    try:
        from printing.jobs import create_receipt_job
        create_receipt_job(order)
    except Exception:
        pass

    return JsonResponse({
        "ok": True,
        "order_id": order.id,
        "total": str(combined_total),
    })


@login_required(login_url="dashboard:login")
def pos_table_order_json(request, place_id):
    """Получить открытый заказ по столу (для подгрузки в кассу)."""
    from reservations.models import Place
    place = get_object_or_404(Place, id=place_id)
    branch = place.floor.branch
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, branch)):
        return JsonResponse({"ok": False}, status=403)

    order = (
        Order.objects
        .filter(
            branch=branch,
            table_place=place,
            status__in=[Order.Status.NEW, Order.Status.ACCEPTED,
                        Order.Status.COOKING, Order.Status.READY],
        )
        .prefetch_related("items__item")
        .order_by("-created_at")
        .first()
    )

    if not order:
        return JsonResponse({"ok": True, "order": None})

    items = [
        {
            "name": oi.item.name_ru,
            "qty": oi.qty,
            "price": str(oi.price_snapshot),
            "line_total": str(oi.line_total),
        }
        for oi in order.items.all()
    ]
    return JsonResponse({
        "ok": True,
        "order": {
            "id": order.id,
            "total": str(order.total_amount),
            "comment": order.comment,
            "items": items,
            "created_at": order.created_at.strftime("%H:%M"),
        },
    })


@require_POST
@login_required(login_url="dashboard:login")
def pos_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, order.branch)):
        return JsonResponse({"ok": False}, status=403)

    prev_status = order.status
    new_status  = request.POST.get("status")
    new_payment = request.POST.get("payment_status")

    fields = []
    if new_status and new_status in Order.Status.values:
        # Restore stock when cancelling a closed POS order
        if new_status == Order.Status.CANCELLED and order.status == Order.Status.CLOSED:
            for oi in order.items.select_related("item").all():
                try:
                    bi = BranchItem.objects.get(branch=order.branch, item=oi.item)
                    if bi.stock is not None:
                        bi.stock += oi.qty
                        bi.is_available = True
                        bi.save(update_fields=["stock", "is_available"])
                except BranchItem.DoesNotExist:
                    pass
        order.status = new_status
        fields.append("status")
    if new_payment and new_payment in Order.PaymentStatus.values:
        order.payment_status = new_payment
        fields.append("payment_status")
    if fields:
        fields.append("updated_at")
        order.save(update_fields=fields)

    # При принятии входящего заказа (new → accepted) — отправить на кухонный принтер
    if prev_status == Order.Status.NEW and new_status == Order.Status.ACCEPTED:
        try:
            from printing.jobs import create_print_jobs
            create_print_jobs(order)
        except Exception as e:
            import traceback
            print("PRINT create_print_jobs ERROR (accept):", e)
            traceback.print_exc()

    # При закрытии онлайн-заказа → печать итогового чека на кассовый принтер
    if new_status == Order.Status.CLOSED and prev_status != Order.Status.CLOSED:
        try:
            from printing.jobs import create_receipt_job
            create_receipt_job(order)
        except Exception as e:
            print("PRINT create_receipt_job ERROR (close):", e)

    return JsonResponse({
        "ok": True,
        "status": order.status,
        "payment_status": order.payment_status,
    })


@login_required(login_url="dashboard:login")
def pos_live_orders(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, branch)):
        return JsonResponse({"ok": False}, status=403)

    orders = (
        Order.objects
        .filter(branch=branch, status__in=[
            Order.Status.NEW, Order.Status.ACCEPTED,
            Order.Status.COOKING, Order.Status.READY,
        ])
        .prefetch_related("items__item", "constructor_items")
        .order_by("-created_at")
    )

    result = []
    for o in orders:
        items = [
            {"name": oi.item.name_ru, "qty": oi.qty, "line": str(oi.line_total)}
            for oi in o.items.all()
        ]
        for ci in o.constructor_items.all():
            ing_parts = []
            for sel in (ci.ingredients_snapshot or []):
                ing_names = ", ".join(i["name"] for i in sel.get("ings", []))
                ing_parts.append(f"{sel['gname']}: {ing_names}")
            detail = " · ".join(ing_parts)
            items.append({
                "name": f"🧩 {ci.constructor_name_snapshot}" + (f" ({detail})" if detail else ""),
                "qty":  ci.qty,
                "line": str(ci.line_total),
            })
        result.append({
            "id":             o.id,
            "type":           o.type,
            "type_label":     o.get_type_display(),
            "status":         o.status,
            "status_label":   o.get_status_display(),
            "customer":       o.customer_name,
            "phone":          o.customer_phone,
            "address":        o.delivery_address,
            "total":          str(o.total_amount),
            "payment":        o.payment_method,
            "payment_status": o.payment_status,
            "comment":        o.comment,
            "created":        o.created_at.strftime("%H:%M"),
            "items": items,
        })

    return JsonResponse({"ok": True, "orders": result})


@login_required(login_url="dashboard:login")
def pos_receipt(request, order_id):
    order = get_object_or_404(
        Order.objects
        .prefetch_related("items__item", "constructor_items")
        .select_related("branch__restaurant", "table_place"),
        id=order_id,
    )
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, order.branch)):
        return redirect("dashboard:home")
    return render(request, "dashboard/receipt.html", {"order": order})


# ── POS Inventory ────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def pos_inventory(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, branch)):
        return redirect("dashboard:home")

    if request.method == "POST":
        # AJAX bulk update: [{bi_id, stock}, ...]
        import json as _json2
        try:
            updates = _json2.loads(request.body)
        except Exception:
            return JsonResponse({"ok": False, "error": "bad json"}, status=400)
        for u in updates:
            try:
                bi = BranchItem.objects.get(id=int(u["bi_id"]), branch=branch)
                raw = u.get("stock")
                if raw == "" or raw is None:
                    bi.stock = None         # unlimited
                    bi.is_available = True
                else:
                    val = int(raw)
                    bi.stock = max(0, val)
                    bi.is_available = (bi.stock > 0)
                bi.save(update_fields=["stock", "is_available"])
            except Exception:
                continue
        return JsonResponse({"ok": True})

    # GET — load all branch items grouped by category
    categories = (
        BranchCategory.objects
        .filter(branch=branch, is_active=True)
        .select_related("category")
        .prefetch_related(
            _Prefetch(
                "items_in_category",
                queryset=BranchCategoryItem.objects.select_related(
                    "branch_item__item"
                ).order_by("sort_order"),
            )
        )
        .order_by("sort_order")
    )
    return render(request, "dashboard/pos_inventory.html", {
        "branch": branch,
        "categories": categories,
    })


# ── POS Report ───────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def pos_report(request, branch_id):
    from datetime import date as _date, datetime as _dt
    from django.db.models import Sum as _Sum, Q as _Q
    from django.db.models.functions import TruncDate
    from orders.models import OrderItem as _OI, ConstructorOrderItem

    branch = get_object_or_404(Branch, id=branch_id)
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, branch)):
        return redirect("dashboard:home")

    today = _date.today()
    date_from_str = request.GET.get("from", str(today))
    date_to_str   = request.GET.get("to",   str(today))
    try:
        date_from = _dt.strptime(date_from_str, "%Y-%m-%d").date()
        date_to   = _dt.strptime(date_to_str,   "%Y-%m-%d").date()
    except ValueError:
        date_from = date_to = today
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    base_qs = Order.objects.filter(
        branch=branch,
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    )

    closed    = base_qs.filter(status=Order.Status.CLOSED)
    cancelled = base_qs.filter(status=Order.Status.CANCELLED)

    # ── Выручка = сумма позиций (line_total), без доставки ──
    # Используем сумму line_total из OrderItem + ConstructorOrderItem —
    # это единственный надёжный способ: delivery_fee в старых заказах мог
    # не сохраняться, но line_total всегда считается только по блюдам.
    def _revenue(order_qs):
        ids = order_qs.values_list("id", flat=True)
        item_rev = _OI.objects.filter(order_id__in=ids).aggregate(s=_Sum("line_total"))["s"] or Decimal("0")
        cx_rev   = ConstructorOrderItem.objects.filter(order_id__in=ids).aggregate(s=_Sum("line_total"))["s"] or Decimal("0")
        return item_rev + cx_rev

    total_revenue   = _revenue(closed)
    total_orders    = closed.count()
    cancelled_count = cancelled.count()
    cancelled_sum   = _revenue(cancelled)

    # Сумма доставки по закрытым доставочным заказам
    total_delivery_fees = (
        closed.filter(type=Order.Type.DELIVERY)
        .aggregate(s=_Sum("delivery_fee"))["s"] or Decimal("0")
    )

    # ── Онлайн vs Офлайн ──
    online_qs  = closed.filter(
        _Q(table_place__isnull=False) |
        _Q(type__in=[Order.Type.DELIVERY, Order.Type.PICKUP])
    )
    offline_qs = closed.filter(
        table_place__isnull=True,
        type=Order.Type.DINE_IN,
    )
    online_revenue  = _revenue(online_qs)
    offline_revenue = _revenue(offline_qs)
    online_count    = online_qs.count()
    offline_count   = offline_qs.count()

    # ── По способу оплаты ──
    pay_cash   = _revenue(closed.filter(payment_method="cash"))
    pay_online = _revenue(closed.filter(payment_method="online"))

    # ── Топ блюд ──
    regular_items = (
        _OI.objects
        .filter(order__in=closed)
        .values("item__name_ru")
        .annotate(total_qty=_Sum("qty"), total_rev=_Sum("line_total"))
    )
    cx_items_qs = (
        ConstructorOrderItem.objects
        .filter(order__in=closed)
        .values("constructor_name_snapshot")
        .annotate(total_qty=_Sum("qty"), total_rev=_Sum("line_total"))
    )
    top_items = []
    for r in regular_items:
        top_items.append({"name": r["item__name_ru"], "qty": r["total_qty"], "rev": r["total_rev"] or Decimal("0")})
    for r in cx_items_qs:
        name = (r["constructor_name_snapshot"] or "Собери сам") + " 🧩"
        top_items.append({"name": name, "qty": r["total_qty"], "rev": r["total_rev"] or Decimal("0")})
    top_items.sort(key=lambda x: x["rev"], reverse=True)
    top_items = top_items[:20]

    # ── Разбивка по дням (через item line_total) ──
    # Собираем line_total по order_id для закрытых заказов
    closed_ids = list(closed.values_list("id", flat=True))

    item_rev_map = {
        r["order_id"]: r["s"]
        for r in _OI.objects.filter(order_id__in=closed_ids)
            .values("order_id").annotate(s=_Sum("line_total"))
    }
    cx_rev_map = {
        r["order_id"]: r["s"]
        for r in ConstructorOrderItem.objects.filter(order_id__in=closed_ids)
            .values("order_id").annotate(s=_Sum("line_total"))
    }

    order_days = (
        closed
        .annotate(day=TruncDate("created_at"))
        .values("id", "day")
        .order_by("day")
    )

    daily_agg = {}
    for row in order_days:
        day = row["day"]
        rev = (item_rev_map.get(row["id"]) or Decimal("0")) + (cx_rev_map.get(row["id"]) or Decimal("0"))
        if day not in daily_agg:
            daily_agg[day] = {"cnt": 0, "rev": Decimal("0")}
        daily_agg[day]["cnt"] += 1
        daily_agg[day]["rev"] += rev

    cancelled_daily = {
        row["day"]: row["cnt"]
        for row in cancelled
            .annotate(day=TruncDate("created_at"))
            .values("day").annotate(cnt=Count("id"))
    }
    online_daily = {
        row["day"]: row["cnt"]
        for row in online_qs
            .annotate(day=TruncDate("created_at"))
            .values("day").annotate(cnt=Count("id"))
    }
    offline_daily = {
        row["day"]: row["cnt"]
        for row in offline_qs
            .annotate(day=TruncDate("created_at"))
            .values("day").annotate(cnt=Count("id"))
    }

    daily = [
        {
            "day":       day,
            "cnt":       vals["cnt"],
            "rev":       vals["rev"],
            "cancelled": cancelled_daily.get(day, 0),
            "online":    online_daily.get(day, 0),
            "offline":   offline_daily.get(day, 0),
        }
        for day, vals in sorted(daily_agg.items())
    ]

    return render(request, "dashboard/pos_report.html", {
        "branch":           branch,
        "date_from":        date_from,
        "date_to":          date_to,
        "total_revenue":    total_revenue,
        "total_orders":     total_orders,
        "cancelled_count":  cancelled_count,
        "cancelled_sum":    cancelled_sum,
        "online_revenue":   online_revenue,
        "offline_revenue":  offline_revenue,
        "online_count":     online_count,
        "offline_count":    offline_count,
        "pay_cash":              pay_cash,
        "pay_online_amt":        pay_online,
        "top_items":             top_items,
        "daily":                 daily,
        "total_delivery_fees":   total_delivery_fees,
    })


# ── POS History ───────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def pos_history(request, branch_id):
    from datetime import date as _date, datetime as _dt
    branch = get_object_or_404(Branch, id=branch_id)
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, branch)):
        return redirect("dashboard:home")

    today = _date.today()
    date_str = request.GET.get("date", str(today))
    try:
        sel_date = _dt.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        sel_date = today

    from django.db.models import ExpressionWrapper, F, DecimalField as _Dec
    orders = (
        Order.objects
        .filter(branch=branch, created_at__date=sel_date)
        .prefetch_related("items__item", "constructor_items")
        .annotate(net_total=ExpressionWrapper(
            F("total_amount") - F("delivery_fee"),
            output_field=_Dec(max_digits=10, decimal_places=2),
        ))
        .order_by("-created_at")
    )

    return render(request, "dashboard/pos_history.html", {
        "branch":    branch,
        "orders":    orders,
        "sel_date":  sel_date,
        "today":     today,
    })


@require_POST
@login_required(login_url="dashboard:login")
def pos_order_cancel(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if not (request.user.is_staff or request.user.is_superuser or _has_branch_access(request.user, order.branch)):
        return JsonResponse({"ok": False}, status=403)

    if order.status == Order.Status.CANCELLED:
        return JsonResponse({"ok": False, "error": "Уже отменён"})

    # Restore stock for closed POS orders
    if order.status == Order.Status.CLOSED:
        for oi in order.items.select_related("item").all():
            try:
                bi = BranchItem.objects.get(branch=order.branch, item=oi.item)
                if bi.stock is not None:
                    bi.stock += oi.qty
                    bi.is_available = True
                    bi.save(update_fields=["stock", "is_available"])
            except BranchItem.DoesNotExist:
                pass

    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])

    return JsonResponse({"ok": True})


# ── КОНСТРУКТОР БЛЮД ──────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def constructor_list(request, branch_id):
    from catalog.models import BranchItem
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:home")
    constructors = branch.dish_constructors.prefetch_related(
        "groups__ingredients__branch_item__item"
    ).order_by("sort_order", "id")
    branch_items = (
        BranchItem.objects.select_related("item")
        .filter(branch=branch, is_available=True)
        .order_by("item__name_ru")
    )
    return render(request, "dashboard/constructor.html", {
        "branch": branch,
        "constructors": constructors,
        "branch_items": branch_items,
    })


@require_POST
@login_required(login_url="dashboard:login")
def constructor_add(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return JsonResponse({"ok": False}, status=403)
    name       = request.POST.get("name", "").strip()
    base_price = request.POST.get("base_price", "0").strip() or "0"
    desc       = request.POST.get("description", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Введите название"})
    from decimal import InvalidOperation
    try:
        bp = Decimal(base_price)
    except InvalidOperation:
        bp = Decimal("0")
    cx = DishConstructor.objects.create(branch=branch, name=name, base_price=bp, description=desc)
    photo = request.FILES.get("photo")
    if photo:
        cx.photo = photo
        cx.save()
    return JsonResponse({"ok": True, "id": cx.id, "name": cx.name, "base_price": str(cx.base_price),
                         "photo_url": cx.photo.url if cx.photo else ""})


@require_POST
@login_required(login_url="dashboard:login")
def constructor_photo_update(request, cx_id):
    cx = get_object_or_404(DishConstructor, id=cx_id)
    if not _has_branch_access(request.user, cx.branch):
        return JsonResponse({"ok": False}, status=403)
    photo = request.FILES.get("photo")
    if not photo:
        return JsonResponse({"ok": False, "error": "Нет файла"})
    cx.photo = photo
    cx.save()
    return JsonResponse({"ok": True, "photo_url": cx.photo.url})


@require_POST
@login_required(login_url="dashboard:login")
def constructor_delete(request, cx_id):
    cx = get_object_or_404(DishConstructor, id=cx_id)
    if not _has_branch_access(request.user, cx.branch):
        return JsonResponse({"ok": False}, status=403)
    cx.delete()
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url="dashboard:login")
def constructor_toggle(request, cx_id):
    cx = get_object_or_404(DishConstructor, id=cx_id)
    if not _has_branch_access(request.user, cx.branch):
        return JsonResponse({"ok": False}, status=403)
    cx.is_active = not cx.is_active
    cx.save(update_fields=["is_active"])
    return JsonResponse({"ok": True, "is_active": cx.is_active})


@require_POST
@login_required(login_url="dashboard:login")
def constructor_group_add(request, cx_id):
    cx = get_object_or_404(DishConstructor, id=cx_id)
    if not _has_branch_access(request.user, cx.branch):
        return JsonResponse({"ok": False}, status=403)
    name       = request.POST.get("name", "").strip()
    min_select = int(request.POST.get("min_select", 1) or 1)
    max_select = int(request.POST.get("max_select", 1) or 1)
    if not name:
        return JsonResponse({"ok": False, "error": "Введите название группы"})
    g = ConstructorGroup.objects.create(constructor=cx, name=name, min_select=min_select, max_select=max_select)
    return JsonResponse({"ok": True, "id": g.id, "name": g.name, "min_select": g.min_select, "max_select": g.max_select})


@require_POST
@login_required(login_url="dashboard:login")
def constructor_group_delete(request, group_id):
    g = get_object_or_404(ConstructorGroup, id=group_id)
    if not _has_branch_access(request.user, g.constructor.branch):
        return JsonResponse({"ok": False}, status=403)
    g.delete()
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url="dashboard:login")
def constructor_ingredient_add(request, group_id):
    g = get_object_or_404(ConstructorGroup, id=group_id)
    if not _has_branch_access(request.user, g.constructor.branch):
        return JsonResponse({"ok": False}, status=403)
    name  = request.POST.get("name", "").strip()
    desc  = request.POST.get("description", "").strip()
    price_raw = request.POST.get("price", "0").strip() or "0"
    if not name:
        return JsonResponse({"ok": False, "error": "Введите название"})
    from decimal import InvalidOperation
    try:
        price = Decimal(price_raw)
    except InvalidOperation:
        price = Decimal("0")
    photo = request.FILES.get("photo")
    ing = ConstructorIngredient(group=g, name=name, description=desc, price=price)
    if photo:
        ing.photo = photo
    ing.save()
    return JsonResponse({"ok": True, "id": ing.id, "name": ing.name, "description": ing.description,
                         "price": str(ing.price), "photo_url": ing.photo.url if ing.photo else ""})


@require_POST
@login_required(login_url="dashboard:login")
def constructor_ingredient_from_menu(request, group_id):
    """Добавить позицию в категорию конструктора из существующего блюда меню."""
    from catalog.models import BranchItem
    g = get_object_or_404(ConstructorGroup, id=group_id)
    if not _has_branch_access(request.user, g.constructor.branch):
        return JsonResponse({"ok": False}, status=403)
    bi_id = request.POST.get("branch_item_id")
    bi = get_object_or_404(BranchItem, id=bi_id, branch=g.constructor.branch)
    # Не добавлять дублей
    if ConstructorIngredient.objects.filter(group=g, branch_item=bi).exists():
        return JsonResponse({"ok": False, "error": "Уже добавлено"})
    ing = ConstructorIngredient.objects.create(group=g, branch_item=bi)
    return JsonResponse({
        "ok": True,
        "id": ing.id,
        "name": ing.display_name,
        "description": ing.display_description,
        "price": str(ing.display_price),
        "photo_url": ing.display_photo_url,
    })


@require_POST
@login_required(login_url="dashboard:login")
def constructor_ingredient_delete(request, ing_id):
    ing = get_object_or_404(ConstructorIngredient, id=ing_id)
    if not _has_branch_access(request.user, ing.group.constructor.branch):
        return JsonResponse({"ok": False}, status=403)
    ing.delete()
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url="dashboard:login")
def constructor_ingredient_update(request, ing_id):
    """Обновить цену (и имя, если ручной) ингредиента."""
    ing = get_object_or_404(ConstructorIngredient, id=ing_id)
    if not _has_branch_access(request.user, ing.group.constructor.branch):
        return JsonResponse({"ok": False}, status=403)
    price_raw = request.POST.get("price", "").strip()
    if price_raw != "":
        try:
            ing.price = Decimal(price_raw)
        except Exception:
            return JsonResponse({"ok": False, "error": "Неверная цена"})
    if not ing.branch_item_id:
        name = request.POST.get("name", "").strip()
        if name:
            ing.name = name
    ing.save()
    return JsonResponse({"ok": True, "price": str(ing.display_price), "name": ing.display_name})


@require_POST
@login_required(login_url="dashboard:login")
def constructor_group_update(request, group_id):
    """Обновить min/max группы."""
    g = get_object_or_404(ConstructorGroup, id=group_id)
    if not _has_branch_access(request.user, g.constructor.branch):
        return JsonResponse({"ok": False}, status=403)
    try:
        min_s = int(request.POST.get("min_select", g.min_select))
        max_s = int(request.POST.get("max_select", g.max_select))
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "Неверные значения"})
    g.min_select = min_s
    g.max_select = max_s
    g.save()
    return JsonResponse({"ok": True, "min_select": g.min_select, "max_select": g.max_select})
