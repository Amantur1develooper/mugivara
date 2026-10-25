#!/bin/bash
# Разворачивает кафе «Семейный» (Ош) НА СЕРВЕРЕ: меню на трёх языках,
# 134 блюда, 106 фото, обложка филиала.
#
# Запускать на сервере из /var/www/mugivara:
#     bash setup_semeyniy.sh
#
# Безопасно запускать повторно: импорт идемпотентный, блюда не дублируются.

set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/bin/python"
[ -x "$PY" ] || PY="venv/bin/python"
[ -x "$PY" ] || { echo "Не нашёл виртуальное окружение (.venv или venv)"; exit 1; }

echo "── 1/3 Меню и фото ────────────────────────────────────────"
$PY import_restaurant.py --data semeyniy_menu_data --photos semeyniy_photos

echo
echo "── 2/3 Обложка филиала ────────────────────────────────────"
$PY - <<'PYEOF'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
from core.models import Branch
import semeyniy_menu_data as d

b = Branch.objects.filter(restaurant__slug="semeyniy").order_by("pk").first()
if not b:
    raise SystemExit("филиал «Семейный» не найден")
if b.cover_photo:
    print("  обложка уже стоит:", b.cover_photo.url)
    raise SystemExit(0)

photos = {i["ru"]: i["photo"] for c in d.CATEGORIES for i in c["items"]}
im = Image.open(os.path.join("semeyniy_photos", photos["Шашлык ассорти"])).convert("RGB")
W, H = im.size
nh = int(W / (16 / 6))
top = max(0, min(H - nh, int(H * 0.45)))   # еда на доске — в нижней части кадра
im = im.crop((0, top, W, top + nh)).resize((1600, 600), Image.LANCZOS)
buf = BytesIO(); im.save(buf, "WEBP", quality=80, method=6)
b.cover_photo.save("semeyniy-cover.webp", ContentFile(buf.getvalue()), save=True)
print("  обложка загружена:", b.cover_photo.url)
PYEOF

echo
echo "── 3/3 Перезапуск ─────────────────────────────────────────"
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet mugivara_gunicorn; then
  systemctl restart mugivara_gunicorn && echo "  gunicorn перезапущен"
else
  echo "  служба mugivara_gunicorn не найдена —"
  echo "  перезапустите вручную: systemctl restart mugivara_gunicorn"
fi

cat <<'TXT'

Готово. Проверьте меню на трёх языках: /ru/<id>/menu/, /ky/<id>/menu/, /en/<id>/menu/

Адрес, телефон и карту «Семейного» добавьте в кабинете — на сайте заведения их нет.
Часы работы поставлены 09:00–01:00 (на сайте расписание хранится в UTC).

НЕОБЯЗАТЕЛЬНО — пережать фото всех остальных заведений (экономит ~40% веса,
страницы грузятся заметно быстрее). Сначала бэкап и проверка вхолостую:

    tar czf ~/media-backup-$(date +%F).tar.gz media/
    .venv/bin/python recompress_photos.py --dry-run
    .venv/bin/python recompress_photos.py

TXT
