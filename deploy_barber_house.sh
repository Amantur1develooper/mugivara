#!/bin/bash
# Выкатывает на прод барбершоп «Barber House» (Ош) и правки записи/витрины.
#
# Запускать НА СЕРВЕРЕ из /var/www/mugivara, после git pull:
#     cd /var/www/mugivara && git pull && bash deploy_barber_house.sh
#
# Безопасно запускать повторно: импорт прайса идемпотентный, дубли услуг
# не плодятся. Миграций в этой выкатке нет.

set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/bin/python"
[ -x "$PY" ] || PY="venv/bin/python"
[ -x "$PY" ] || { echo "Не нашёл виртуальное окружение (.venv или venv)"; exit 1; }

SLUG="barber-house-osh"

echo "── 1/4 Проверка проекта ───────────────────────────────────"
$PY manage.py check --deploy 2>&1 | tail -3 || true

echo
echo "── 2/4 Непрогнанные миграции (должно быть пусто) ──────────"
$PY manage.py showmigrations --plan 2>/dev/null | grep -v '^\[X\]' | head -5 || true
echo "  (если выше ничего нет — всё прогнано)"

echo
echo "── 3/4 Барбершоп «Barber House» ───────────────────────────"
$PY manage.py import_barber_house

echo
echo "── 4/4 Перезапуск ─────────────────────────────────────────"
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet mugivara_gunicorn; then
  systemctl restart mugivara_gunicorn && echo "  gunicorn перезапущен"
else
  echo "  сервис mugivara_gunicorn не активен — перезапустите вручную:"
  echo "    systemctl restart mugivara_gunicorn"
fi

echo
sleep 3   # дать gunicorn подняться, иначе проверка ниже увидит 502
echo "── Проверка страниц ───────────────────────────────────────"
for url in "https://webordo.kg/ru/barbershop/$SLUG/" \
           "https://webordo.kg/ru/barbershop/$SLUG/book/" \
           "https://webordo.kg/en/barbershop/$SLUG/"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 20 "$url" || echo "---")
  echo "  $code  $url"
done

echo
echo "Готово. Витрина: https://webordo.kg/ru/barbershop/$SLUG/"
echo
echo "Что ещё нужно от владельца (заполняется в кабинете):"
echo "  • точный адрес и часы работы"
echo "  • реальные мастера вместо «Свободный мастер»"
echo "  • логотип и обложка"
echo "  • логин владельца → $PY manage.py import_barber_house --owner ЛОГИН"
