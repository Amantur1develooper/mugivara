#!/bin/bash
# Разворачивает кафе «Ош Табит» (Ош) НА СЕРВЕРЕ: меню на трёх языках,
# 73 позиции, 67 фото, обложка и логотип заведения.
#
# Запускать на сервере из /var/www/mugivara, после git pull:
#     cd /var/www/mugivara && git pull && bash deploy_osh_tabit.sh
#
# Безопасно запускать повторно: импорт идемпотентный, блюда не дублируются,
# уже загруженные фото не перезаписываются. Миграций в этой выкатке нет.

set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/bin/python"
[ -x "$PY" ] || PY="venv/bin/python"
[ -x "$PY" ] || { echo "Не нашёл виртуальное окружение (.venv или venv)"; exit 1; }

echo "── 1/3 Проверка данных меню ───────────────────────────────"
$PY import_restaurant.py --data osh_tabit_menu_data --photos osh_tabit_photos --dry-run \
  | sed -n '1,4p'

echo
echo "── 2/3 Меню и фото ────────────────────────────────────────"
$PY import_restaurant.py --data osh_tabit_menu_data --photos osh_tabit_photos

echo
echo "── 3/3 Перезапуск ─────────────────────────────────────────"
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet mugivara_gunicorn; then
  systemctl restart mugivara_gunicorn && echo "  gunicorn перезапущен"
else
  echo "  сервис mugivara_gunicorn не активен — перезапустите вручную:"
  echo "    systemctl restart mugivara_gunicorn"
fi

sleep 3   # дать gunicorn подняться, иначе проверка ниже увидит 502

BRANCH=$($PY - <<'PYEOF'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from core.models import Branch
b = Branch.objects.filter(restaurant__slug="osh-tabit").order_by("id").first()
print(b.id if b else "")
PYEOF
)

echo
echo "── Проверка страниц ───────────────────────────────────────"
for lang in ru ky en; do
  url="https://webordo.kg/$lang/$BRANCH/menu/"
  echo "  $(curl -s -o /dev/null -w '%{http_code}' -m 20 "$url")  $url"
done

echo
echo "Готово. Меню: https://webordo.kg/ru/$BRANCH/menu/"
echo "Филиал #$BRANCH — адрес, телефон и часы работы заполняются в кабинете."
