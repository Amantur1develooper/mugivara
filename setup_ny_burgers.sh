#!/bin/bash
# Разворачивает NY Burgers НА СЕРВЕРЕ: миграции, статика, два филиала, рестарт.
# Запускать на сервере из /var/www/mugivara:
#     bash setup_ny_burgers.sh
#     bash setup_ny_burgers.sh --branches "Ош — Центр|Ош — Кулатова"
#
# Безопасно запускать повторно: импорт идемпотентный, филиалы не дублируются.

set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/bin/python"
[ -x "$PY" ] || PY="venv/bin/python"
[ -x "$PY" ] || { echo "Не нашёл виртуальное окружение (.venv или venv)"; exit 1; }

echo "── 1/5 Миграции ───────────────────────────────────────────"
if ! $PY manage.py migrate --noinput; then
  cat <<'HINT'

Миграции не применились.

Если ошибка про «Conflicting migrations detected» — на сервере уже есть
миграция с таким же номером. Это чинится так:

    .venv/bin/python manage.py makemigrations --merge
    .venv/bin/python manage.py migrate

После этого запустите setup_ny_burgers.sh заново — он продолжит с места,
где остановился, ничего не продублировав.

Ничего из меню и заказов при этой ошибке не пострадало.
HINT
  exit 1
fi

echo
echo "── 2/5 Переводы ───────────────────────────────────────────"
# .mo приехали собранные; если на сервере есть gettext — пересоберём на всякий
if command -v msgfmt >/dev/null 2>&1; then
  $PY manage.py compilemessages -l ky -l en 2>&1 | grep -iE "error|fatal" || true
  echo "  переводы пересобраны"
else
  echo "  msgfmt не установлен — используем готовые .mo"
fi

echo
echo "── 3/5 Статика ────────────────────────────────────────────"
$PY manage.py collectstatic --noinput | tail -2

echo
echo "── 4/5 Меню и филиалы ─────────────────────────────────────"
$PY import_ny_burgers.py "$@"

echo
echo "── 5/5 Перезапуск ─────────────────────────────────────────"
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet mugivara_gunicorn; then
  systemctl restart mugivara_gunicorn && echo "  gunicorn перезапущен"
else
  echo "  служба mugivara_gunicorn не найдена или не запущена —"
  echo "  перезапустите вручную: systemctl restart mugivara_gunicorn"
fi

echo
echo "Готово. Откройте каталог и проверьте оба филиала."
