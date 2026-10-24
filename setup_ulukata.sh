#!/bin/bash
# Разворачивает ресторан «Улук-Ата» НА СЕРВЕРЕ: меню на трёх языках,
# 218 блюд с фото, обложка филиала, кыргызские строки интерфейса.
#
# Запускать на сервере из /var/www/mugivara:
#     bash setup_ulukata.sh
#
# Безопасно запускать повторно: импорт идемпотентный, блюда не дублируются,
# уже загруженные фото не перезаписываются.

set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/bin/python"
[ -x "$PY" ] || PY="venv/bin/python"
[ -x "$PY" ] || { echo "Не нашёл виртуальное окружение (.venv или venv)"; exit 1; }

echo "── 1/4 Переводы интерфейса ────────────────────────────────"
# в locale/ky добавлено 108 строк: «Ачык», «Себетке кошуу», «Бизнести кошуу» и др.
if command -v msgfmt >/dev/null 2>&1; then
  $PY manage.py compilemessages -l ky -l en 2>&1 | grep -iE "error|fatal" || true
  echo "  переводы пересобраны"
else
  echo "  msgfmt не установлен — используем готовые .mo"
fi

echo
echo "── 2/4 Меню и фото ────────────────────────────────────────"
$PY import_restaurant.py --data ulukata_menu_data --photos ulukata_photos

echo
echo "── 3/4 Обложка филиала ────────────────────────────────────"
$PY - <<'PYEOF'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
from core.models import Branch
import ulukata_menu_data as d

b = Branch.objects.filter(restaurant__slug="ulukata").order_by("pk").first()
if not b:
    raise SystemExit("филиал Улук-Ата не найден")
if b.cover_photo:
    print("  обложка уже стоит:", b.cover_photo.url)
    raise SystemExit(0)

photos = {i["ru"]: i["photo"] for c in d.CATEGORIES for i in c["items"]}
im = Image.open(os.path.join("ulukata_photos", photos["Тандыр ассорти XXL"])).convert("RGB")
W, H = im.size
target = 16 / 6
if W / H > target:
    nw = int(H * target); im = im.crop(((W - nw) // 2, 0, (W + nw) // 2, H))
else:
    nh = int(W / target); im = im.crop((0, (H - nh) // 2, W, (H + nh) // 2))
im = im.resize((1600, 600), Image.LANCZOS)
buf = BytesIO(); im.save(buf, "JPEG", quality=88)
b.cover_photo.save("ulukata-cover.jpg", ContentFile(buf.getvalue()), save=True)
print("  обложка загружена:", b.cover_photo.url)
PYEOF

echo
echo "── 4/4 Перезапуск ─────────────────────────────────────────"
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet mugivara_gunicorn; then
  systemctl restart mugivara_gunicorn && echo "  gunicorn перезапущен"
else
  echo "  служба mugivara_gunicorn не найдена —"
  echo "  перезапустите вручную: systemctl restart mugivara_gunicorn"
fi

echo
echo "Готово. Проверьте меню на трёх языках: /ru/<id>/menu/, /ky/<id>/menu/, /en/<id>/menu/"
echo "Адрес, телефон и карту Улук-Аты добавьте в кабинете — их не было на сайте заведения."
