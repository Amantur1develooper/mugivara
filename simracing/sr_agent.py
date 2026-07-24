"""
WebOrdo Симрейсинг — Агент печати чеков
=========================================
Отдельный агент для печати чеков симрейсинга. Работает независимо от ресторанного агента.

Установка:
    pip install requests pywin32 pillow

Запуск:
    python sr_agent.py

Файлы:
    sr_agent.py   — этот файл
    sr_config.json — скачайте из личного кабинета → Настройки площадки → Принтер
"""

import json
import logging
import random
import socket
import struct
import sys
import time
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
        logging.FileHandler(LOG_DIR / "sr_agent.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("sr_agent")

CONFIG_PATH = Path(__file__).parent / "sr_config.json"


# ── DNS fallback через Google 8.8.8.8 ────────────────────────────────────────
def _resolve_via_google(hostname):
    try:
        tid = random.randint(0, 65535)
        header = struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 0)
        qname = b"".join(
            struct.pack("B", len(p)) + p.encode() for p in hostname.split(".")
        ) + b"\x00"
        question = qname + struct.pack(">HH", 1, 1)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        try:
            sock.sendto(header + question, ("8.8.8.8", 53))
            data, _ = sock.recvfrom(512)
        finally:
            sock.close()
        pos = 12 + len(qname) + 4
        ancount = struct.unpack(">H", data[6:8])[0]
        for _ in range(ancount):
            if data[pos] & 0xC0 == 0xC0:
                pos += 2
            else:
                while data[pos]:
                    pos += data[pos] + 1
                pos += 1
            rtype, _, _, rdlen = struct.unpack(">HHIH", data[pos:pos + 10])
            pos += 10
            if rtype == 1 and rdlen == 4:
                return ".".join(str(b) for b in data[pos:pos + 4])
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
            log.info(f"DNS fallback: {host} → {ip}")
            return _orig_getaddrinfo(ip, port, family, type, proto, flags)
        raise


socket.getaddrinfo = _patched_getaddrinfo


# ── Конфиг ───────────────────────────────────────────────────────────────────
def load_config():
    if not CONFIG_PATH.exists():
        log.error(f"ОШИБКА: sr_config.json не найден: {CONFIG_PATH}")
        log.error("Скачайте sr_config.json из личного кабинета → Настройки → Принтер чеков.")
        input("Нажмите Enter для выхода...")
        sys.exit(1)
    try:
        with open(CONFIG_PATH, encoding="utf-8-sig") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        log.error(f"ОШИБКА: sr_config.json повреждён: {e}")
        input("Нажмите Enter для выхода...")
        sys.exit(1)
    for key in ("server_url", "token"):
        if not cfg.get(key):
            log.error(f"ОШИБКА: в sr_config.json отсутствует поле '{key}'.")
            input("Нажмите Enter для выхода...")
            sys.exit(1)
    cfg["server_url"] = cfg["server_url"].rstrip("/")
    return cfg


# ── API клиент ───────────────────────────────────────────────────────────────
class ApiClient:
    def __init__(self, server_url, token):
        self.base = server_url
        self.session = requests.Session()
        self.session.headers["X-Print-Token"] = token
        retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get_jobs(self):
        r = self.session.get(f"{self.base}/api/sr-print/jobs/", timeout=15)
        r.raise_for_status()
        return r.json().get("jobs", [])

    def ack_job(self, job_id, status, error=""):
        payload = {"status": status}
        if error:
            payload["error"] = error[:300]
        self.session.post(
            f"{self.base}/api/sr-print/jobs/{job_id}/ack/",
            json=payload, timeout=10,
        )

    def heartbeat(self):
        r = self.session.post(f"{self.base}/api/sr-print/heartbeat/", timeout=10)
        r.raise_for_status()
        return r.json()

    def get_config(self):
        r = self.session.get(f"{self.base}/api/sr-print/config/", timeout=10)
        r.raise_for_status()
        return r.json()


# ── Таблицы кодировок ────────────────────────────────────────────────────────
CODEPAGE_TABLE = {
    "cp866":      (b"\x11", "cp866"),
    "cp1251":     (b"\x2e", "cp1251"),
    "cp1251_alt": (b"\x49", "cp1251"),
    "cp866_alt":  (b"\x07", "cp866"),
}


# ── Печать текстом (ESC/POS) ─────────────────────────────────────────────────
def print_text_windows(printer_name, content, codepage="cp866"):
    try:
        import win32print
    except ImportError:
        raise RuntimeError("pywin32 не установлен. Выполните: pip install pywin32")

    table_byte, py_encoding = CODEPAGE_TABLE.get(codepage, CODEPAGE_TABLE["cp866"])
    ESC = b"\x1b"
    content = content.replace("\x02", (ESC + b"E\x01").decode("latin-1"))
    content = content.replace("\x03", (ESC + b"E\x00").decode("latin-1"))
    data = content.encode(py_encoding, errors="replace")

    handle = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(handle, 1, ("Receipt", None, "RAW"))
        win32print.StartPagePrinter(handle)
        init = ESC + b"@"
        codepage_cmd = ESC + b"t" + table_byte
        feed = ESC + b"d\x04"
        cut  = b"\x1d\x56\x00"
        beep = b"\x07\x07\x07"
        win32print.WritePrinter(handle, init + codepage_cmd + data + feed + cut + beep)
        win32print.EndPagePrinter(handle)
    finally:
        win32print.EndDocPrinter(handle)
        win32print.ClosePrinter(handle)
    log.info(f"Напечатано на '{printer_name}' (текст, {codepage})")


# ── Печать картинкой (растр) ─────────────────────────────────────────────────
FONT_SIZE    = 26
LINE_SPACING = 4


def _load_mono_font(bold):
    from PIL import ImageFont
    import os
    mono = (["consolab.ttf", "courbd.ttf", "DejaVuSansMono-Bold.ttf", "arialbd.ttf", "tahomabd.ttf"] if bold
            else ["consola.ttf", "cour.ttf", "DejaVuSansMono.ttf", "arial.ttf", "tahoma.ttf"])
    cyrillic_fallback = ["arial.ttf", "tahoma.ttf", "verdana.ttf", "times.ttf"]
    win_fonts = r"C:\Windows\Fonts"
    candidates = mono + cyrillic_fallback
    for n in candidates:
        for path in [n, os.path.join(win_fonts, n)]:
            try:
                return ImageFont.truetype(path, FONT_SIZE)
            except OSError:
                continue
    log.warning("Шрифт не найден — кириллица может не отображаться. Установите Consolas или Arial.")
    try:
        return ImageFont.load_default(size=FONT_SIZE)
    except TypeError:
        return ImageFont.load_default()


def print_image_windows(printer_name, content, width_dots=384):
    try:
        import win32print
    except ImportError:
        raise RuntimeError("pywin32 не установлен. Выполните: pip install pywin32")
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise RuntimeError("Pillow не установлен. Выполните: pip install pillow")

    import struct

    font   = _load_mono_font(False)
    font_b = _load_mono_font(True)
    try:
        char_w = max(1, round(font.getlength("0")))
    except AttributeError:
        char_w = font.getbbox("0")[2] or 13
    ascent, descent = font.getmetrics()
    line_h    = ascent + descent + LINE_SPACING
    max_chars = max(1, width_dots // char_w)

    rendered = []
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
    img   = Image.new("1", (width_dots, img_h), 1)
    draw  = ImageDraw.Draw(img)
    y = 4
    for line in rendered:
        x = 0
        for ch, b in line:
            draw.text((x, y), ch, font=(font_b if b else font), fill=0)
            x += char_w
        y += line_h

    w, h = img.size
    bytes_per_row = (w + 7) // 8
    px = img.load()
    raster = bytearray()
    for yy in range(h):
        for xb in range(bytes_per_row):
            byte = 0
            for bit in range(8):
                xx = xb * 8 + bit
                if xx < w and px[xx, yy] == 0:
                    byte |= (0x80 >> bit)
            raster.append(byte)

    init    = b"\x1b\x40"
    header  = b"\x1d\x76\x30\x00" + struct.pack("<HH", bytes_per_row, h)
    feed    = b"\x1bd\x04"
    cut     = b"\x1d\x56\x00"
    beep    = b"\x07\x07\x07"
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


def print_job(job, printer_name, codepage="cp866", print_mode="image", width_dots=384):
    content = job.get("content", "")
    log.info(f"Печать job #{job['id']} → '{printer_name}' (режим: {print_mode})")
    if print_mode == "image":
        print_image_windows(printer_name, content, width_dots)
    else:
        print_text_windows(printer_name, content, codepage)


# ── Основной цикл ────────────────────────────────────────────────────────────
def main():
    cfg = load_config()

    log.info("=" * 48)
    log.info("WebOrdo Симрейсинг — Агент печати")
    log.info(f"Сервер:   {cfg['server_url']}")
    log.info(f"Токен:    {cfg['token'][:8]}...")
    log.info(f"Принтер:  {cfg.get('printer', 'не задан')}")
    log.info("=" * 48)

    client             = ApiClient(cfg["server_url"], cfg["token"])
    poll_interval      = cfg.get("poll_interval", 3)
    heartbeat_interval = cfg.get("heartbeat_interval", 30)
    printer_name       = cfg.get("printer", "")
    codepage           = cfg.get("codepage", "cp866")
    print_mode         = cfg.get("print_mode", "image")
    width_dots         = int(cfg.get("print_width", 384))

    # Получаем актуальный конфиг с сервера
    try:
        srv = client.get_config()
        if srv.get("printer"):
            printer_name = srv["printer"]
        if srv.get("print_mode"):
            print_mode = srv["print_mode"]
        if srv.get("codepage"):
            codepage = srv["codepage"]
        log.info(f"Площадка: {srv.get('venue')}")
        log.info(f"Принтер (сервер): {printer_name}")
    except Exception as e:
        log.warning(f"Не удалось получить конфиг с сервера: {e}")
        log.warning(f"Используется принтер из sr_config.json: {printer_name}")

    if not printer_name:
        log.error("ОШИБКА: имя принтера не задано! Укажите 'printer' в sr_config.json.")

    if print_mode == "image":
        log.info(">>> РЕЖИМ ПЕЧАТИ: КАРТИНКА (растр) — кириллица гарантирована")
    else:
        log.info(f">>> РЕЖИМ ПЕЧАТИ: ТЕКСТ (codepage={codepage})")
    log.info(f">>> Ширина: {width_dots} точек")
    log.info("─" * 48)
    log.info("Агент запущен. Ожидание чеков...")

    last_heartbeat = 0

    while True:
        now = time.time()

        if now - last_heartbeat >= heartbeat_interval:
            try:
                result = client.heartbeat()
                last_heartbeat = now
                pending = result.get("pending_jobs", 0)
                if pending:
                    log.info(f"Heartbeat OK, ожидает {pending} чеков")
            except Exception as e:
                log.warning(f"Heartbeat: {e}")

        try:
            jobs = client.get_jobs()
        except Exception as e:
            log.error(f"Ошибка получения заданий: {e}")
            time.sleep(poll_interval * 3)
            continue

        for job in jobs:
            jid = job["id"]
            try:
                print_job(job, printer_name, codepage, print_mode, width_dots)
                client.ack_job(jid, "printed")
                log.info(f"Job #{jid} — OK")
            except Exception as e:
                log.error(f"Job #{jid} — ОШИБКА: {e}")
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
