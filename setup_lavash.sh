#!/bin/bash
# Разворачивает Lavash Center (Ош) НА СЕРВЕРЕ: меню на трёх языках,
# 93 блюда с фото, 4 филиала с адресами и телефонами, обложка.
#
# Запускать на сервере из /var/www/mugivara:
#     bash setup_lavash.sh
#
# Безопасно запускать повторно: импорт идемпотентный, блюда и филиалы
# не дублируются, уже загруженные фото не перезаписываются.

set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/bin/python"
[ -x "$PY" ] || PY="venv/bin/python"
[ -x "$PY" ] || { echo "Не нашёл виртуальное окружение (.venv или venv)"; exit 1; }

echo "── 1/3 Меню, фото и филиалы ───────────────────────────────"
$PY import_restaurant.py --data lavash_menu_data --photos lavash_photos

echo
echo "── 2/3 Обложка филиалов ───────────────────────────────────"
$PY - <<'PYEOF'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
from core.models import Branch
import lavash_menu_data as d

branches = list(Branch.objects.filter(restaurant__slug="lavash-center").order_by("pk"))
if not branches:
    raise SystemExit("филиалы Lavash Center не найдены")
if all(b.cover_photo for b in branches):
    print("  обложки уже стоят")
    raise SystemExit(0)

photos = {i["ru"]: i["photo"] for c in d.CATEGORIES for i in c["items"]}
src = os.path.join("lavash_photos", photos["Сет «Джек-Пот»"])
im = Image.open(src).convert("RGB")
W, H = im.size
nh = int(W / (16 / 6))
top = max(0, (H - nh) // 2)
im = im.crop((0, top, W, min(H, top + nh))).resize((1600, 600), Image.LANCZOS)
buf = BytesIO(); im.save(buf, "WEBP", quality=82, method=6)
data = buf.getvalue()
for b in branches:
    if b.cover_photo:
        continue
    b.cover_photo.save("lavash-cover.webp", ContentFile(data), save=True)
    print("  обложка:", b.name_ru)
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

Готово. Скрипт напечатал id всех четырёх филиалов — откройте каждый
на трёх языках: /ru/<id>/menu/, /ky/<id>/menu/, /en/<id>/menu/

Адреса и телефоны филиалов уже проставлены из буклета.
Часы работы стоят 10:00–23:00 — если другие, поправьте в кабинете.

TXT
