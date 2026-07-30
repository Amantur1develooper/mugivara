"""
WebOrdo Cloud Printer Agent
============================
Сервер: https://webordo.kg

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
        ) + b'\x00'
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
            log.info(f"DNS fallback: {host} → {ip} (8.8.8.8)")
            return _orig_getaddrinfo(ip, port, family, type, proto, flags)
        raise


socket.getaddrinfo = _patched_getaddrinfo


# ── Конфиг ───────────────────────────────────────────────────────────────────
def load_config():
    if not CONFIG_PATH.exists():
        log.error(f"ОШИБКА: config.json не найден: {CONFIG_PATH}")
        log.error("Скачайте config.json из личного кабинета ресторана.")
        input("Нажмите Enter для выхода...")
        sys.exit(1)
    try:
        with open(CONFIG_PATH, encoding="utf-8-sig") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        log.error(f"ОШИБКА: config.json повреждён: {e}")
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
        r = self.session.get(f"{self.base}/api/print/jobs/", timeout=15)
        r.raise_for_status()
        return r.json().get("jobs", [])

    def ack_job(self, job_id, status, error=""):
        payload = {"status": status}
        if error:
            payload["error"] = error[:300]
        self.session.post(
            f"{self.base}/api/print/jobs/{job_id}/ack/",
            json=payload, timeout=10,
        )

    def heartbeat(self):
        r = self.session.post(f"{self.base}/api/print/heartbeat/", timeout=10)
        r.raise_for_status()
        return r.json()

    def get_config(self):
        r = self.session.get(f"{self.base}/api/print/config/", timeout=10)
        r.raise_for_status()
        return r.json()


# ── Печать ───────────────────────────────────────────────────────────────────
# Таблицы кодировок ESC/POS для кириллицы.
# Формат: имя → (байт для команды "ESC t n", имя кодировки Python)
# Если печатает кракозябры — поменяйте "codepage" в config.json на другое значение.
CODEPAGE_TABLE = {
    "cp866":  (b"\x11", "cp866"),    # ESC t 17 — PC866 (кириллица), по умолчанию
    "cp1251": (b"\x2e", "cp1251"),   # ESC t 46 — WPC1251 (Windows-кириллица)
    "cp1251_alt": (b"\x49", "cp1251"),  # ESC t 73 — WPC1251 на части принтеров
    "cp866_alt":  (b"\x07", "cp866"),   # ESC t 7  — PC866 на части принтеров
}


def print_text_windows(printer_name, content, codepage="cp866"):
    try:
        import win32print
    except ImportError:
        raise RuntimeError("pywin32 не установлен. Выполните: pip install pywin32")

    table_byte, py_encoding = CODEPAGE_TABLE.get(codepage, CODEPAGE_TABLE["cp866"])

    handle = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(handle, 1, ("Receipt", None, "RAW"))
        win32print.StartPagePrinter(handle)
        ESC          = b"\x1b"
        init         = ESC + b"@"               # ESC @ — сброс
        kanji_off    = b"\x1c\x2e"              # FS . — выключить китайский (Kanji) режим
        codepage_cmd = ESC + b"t" + table_byte  # ESC t n — выбор таблицы символов
        bold_on      = ESC + b"E\x01"           # ESC E 1 — жирный вкл
        bold_off     = ESC + b"E\x00"           # ESC E 0 — жирный выкл
        feed         = ESC + b"d\x04"           # отступ 4 строки
        cut          = b"\x1d\x56\x00"          # GS V 0 — полный отрез
        beep         = b"\x07\x07\x07"          # BEL x3 — звук после обрезки
        # Заменяем плейсхолдеры STX/ETX на реальные ESC/POS команды
        content = content.replace("\x02", bold_on.decode("latin-1"))
        content = content.replace("\x03", bold_off.decode("latin-1"))
        data = content.encode(py_encoding, errors="replace")
        win32print.WritePrinter(handle, init + kanji_off + codepage_cmd + data + feed + cut + beep)
        win32print.EndPagePrinter(handle)
    finally:
        win32print.EndDocPrinter(handle)
        win32print.ClosePrinter(handle)
    log.info(f"Напечатано на '{printer_name}' (кодировка {codepage})")


# ── Печать картинкой (растром) — работает на принтерах без кирилл. шрифта ──────
FONT_SIZE    = 26   # размер шрифта в точках
LINE_SPACING = 4    # межстрочный интервал, точек


def _load_mono_font(bold):
    """Грузит моноширинный TTF-шрифт с поддержкой кириллицы (Windows)."""
    from PIL import ImageFont
    names = (["consolab.ttf", "courbd.ttf", "DejaVuSansMono-Bold.ttf"] if bold
             else ["consola.ttf", "cour.ttf", "DejaVuSansMono.ttf"])
    for n in names:
        try:
            return ImageFont.truetype(n, FONT_SIZE)
        except OSError:
            continue
    return ImageFont.load_default()


def print_image_windows(printer_name, content, width_dots=384):
    """Рендерит чек в монохромную картинку и печатает её как ESC/POS растр.
    Кириллица гарантированно печатается, даже если в принтере нет рус. шрифта."""
    try:
        import win32print
    except ImportError:
        raise RuntimeError("pywin32 не установлен. Выполните: pip install pywin32")
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise RuntimeError("Pillow не установлен. Выполните: pip install pillow")

    font   = _load_mono_font(False)
    font_b = _load_mono_font(True)

    # ширина символа моноширинного шрифта
    try:
        char_w = max(1, round(font.getlength("0")))
    except AttributeError:
        char_w = font.getbbox("0")[2] or 13
    ascent, descent = font.getmetrics()
    line_h    = ascent + descent + LINE_SPACING
    max_chars = max(1, width_dots // char_w)

    # Разбор текста на строки с учётом жирного (\x02 вкл / \x03 выкл) и переноса
    rendered = []  # список строк; каждая строка — список (символ, bold)
    bold = False
    for raw_line in content.split("\n"):
        chars = []
        for ch in raw_line:
            if ch == "\x02":
                bold = True
            elif ch == "\x03":
                bold = False
            else:
                chars.append((ch, bold))
        if not chars:
            rendered.append([])
            continue
        for i in range(0, len(chars), max_chars):
            rendered.append(chars[i:i + max_chars])

    img_h = max(line_h, len(rendered) * line_h + 8)
    img   = Image.new("1", (width_dots, img_h), 1)  # 1 = белый фон
    draw  = ImageDraw.Draw(img)
    y = 4
    for line in rendered:
        x = 0
        for ch, b in line:
            draw.text((x, y), ch, font=(font_b if b else font), fill=0)  # 0 = чёрный
            x += char_w
        y += line_h

    # Конвертация в ESC/POS растр (GS v 0)
    w, h = img.size
    bytes_per_row = (w + 7) // 8
    px = img.load()
    raster = bytearray()
    for yy in range(h):
        for xb in range(bytes_per_row):
            byte = 0
            for bit in range(8):
                xx = xb * 8 + bit
                if xx < w and px[xx, yy] == 0:  # чёрный пиксель → печатать
                    byte |= (0x80 >> bit)
            raster.append(byte)

    init   = b"\x1b\x40"                                    # ESC @ — сброс
    header = b"\x1d\x76\x30\x00" + struct.pack("<HH", bytes_per_row, h)  # GS v 0
    feed   = b"\x1bd\x04"
    cut    = b"\x1d\x56\x00"
    beep   = b"\x07\x07\x07"
    payload = init + header + bytes(raster) + feed + cut + beep

    handle = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(handle, 1, ("Receipt", None, "RAW"))
        win32print.StartPagePrinter(handle)
        win32print.WritePrinter(handle, payload)
        win32print.EndPagePrinter(handle)
    finally:
        win32print.EndDocPrinter(handle)
        win32print.ClosePrinter(handle)
    log.info(f"Напечатано картинкой на '{printer_name}' ({w}x{h})")


def print_job(job, printer_map, codepage="cp866", print_mode="text", width_dots=384):
    group        = job.get("group")
    content      = job.get("content", "")
    printer_name = printer_map.get(group) or next(iter(printer_map.values()), None)
    if not printer_name:
        raise RuntimeError(f"Нет принтера для группы '{group}'. Проверьте config.json")
    log.info(f"Печать job #{job['id']} group={group} → '{printer_name}' (режим: {print_mode})")
    if print_mode == "image":
        print_image_windows(printer_name, content, width_dots)
    else:
        print_text_windows(printer_name, content, codepage)


# ── Основной цикл ────────────────────────────────────────────────────────────
def main():
    cfg = load_config()

    log.info("=" * 48)
    log.info("WebOrdo Printer Agent")
    log.info(f"Сервер:  {cfg['server_url']}")
    log.info(f"Токен:   {cfg['token'][:8]}...")
    log.info(f"Принтеры из конфига: {cfg.get('printers', {})}")
    log.info("=" * 48)

    client = ApiClient(cfg["server_url"], cfg["token"])
    poll_interval      = cfg.get("poll_interval", 3)
    heartbeat_interval = cfg.get("heartbeat_interval", 30)
    printer_map        = dict(cfg.get("printers", {}))
    codepage           = cfg.get("codepage", "cp866")
    if codepage not in CODEPAGE_TABLE:
        log.warning(f"Неизвестная codepage '{codepage}' в config.json — использую cp866")
        codepage = "cp866"
    print_mode         = cfg.get("print_mode", "image")  # ПО УМОЛЧАНИЮ — картинка
    width_dots         = int(cfg.get("print_width", 384))  # 58 мм = 384 точки

    log.info("─" * 48)
    if print_mode == "image":
        log.info(">>> РЕЖИМ ПЕЧАТИ: КАРТИНКА (растр) — кириллица гарантирована")
        # Проверяем, что Pillow установлен — иначе картинку не нарисовать
        try:
            import PIL  # noqa: F401
        except ImportError:
            log.error(">>> ВНИМАНИЕ: Pillow НЕ установлен! Выполните: pip install pillow")
            log.error(">>> Без него режим 'image' работать НЕ будет.")
    else:
        log.info(f">>> РЕЖИМ ПЕЧАТИ: ТЕКСТ (codepage={codepage})")
        log.info(">>> Если выходят иероглифы — поставьте в config.json: \"print_mode\": \"image\"")
    log.info(f">>> Ширина печати: {width_dots} точек")
    log.info("─" * 48)

    # Получаем актуальный список принтеров с сервера
    try:
        srv = client.get_config()
        printer_map.update(srv.get("printers", {}))
        log.info(f"Ресторан: {srv.get('restaurant')}")
        log.info(f"Принтеры (с сервера): {printer_map}")
    except Exception as e:
        log.warning(f"Не удалось получить конфиг с сервера: {e}")
        log.warning(f"Используются принтеры из config.json: {printer_map}")

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
                log.warning(f"Heartbeat: {e}")

        # Получаем задания
        try:
            jobs = client.get_jobs()
        except Exception as e:
            log.error(f"Ошибка получения заданий: {e}")
            time.sleep(poll_interval * 3)
            continue

        # Печатаем
        for job in jobs:
            jid = job["id"]
            try:
                print_job(job, printer_map, codepage, print_mode, width_dots)
                client.ack_job(jid, "printed")
                log.info(f"Job #{jid} — напечатано OK")
            except Exception as e:
                log.error(f"Job #{jid} — ОШИБКА ПЕЧАТИ: {e}")
                client.ack_job(jid, "error", str(e))

        time.sleep(poll_interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Агент остановлен")
    except Exception as e:
        log.error(f"Критическая ошибка: {e}")
        input("Нажмите Enter для выхода...")
