#!/bin/bash
# Включает кнопки под записями барбершопа в Telegram и мини-приложение.
#
# Запускать на сервере из /var/www/mugivara, после git pull:
#     cd /var/www/mugivara && git pull && bash deploy_tg_buttons.sh
#
# Скрипт сам дописывает в .env SITE_URL и TG_WEBHOOK_SECRET, если их там нет.
# Повторный запуск безопасен: секрет не перегенерируется.

set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/bin/python"
[ -x "$PY" ] || PY="venv/bin/python"
[ -x "$PY" ] || { echo "Не нашёл виртуальное окружение (.venv или venv)"; exit 1; }

echo "── 1/4 Настройки в .env ───────────────────────────────────"
touch .env
# Если файл не кончается переводом строки, дописанное прилипнет к последней
# строке и испортит её — добавляем перевод строки заранее.
[ -s .env ] && [ "$(tail -c1 .env | wc -l)" -eq 0 ] && echo >> .env

if ! grep -q "^SITE_URL=" .env; then
  echo "SITE_URL=https://webordo.kg" >> .env
  echo "  добавлен SITE_URL"
else
  echo "  SITE_URL уже задан: $(grep '^SITE_URL=' .env | cut -d= -f2-)"
fi
if ! grep -q "^TG_WEBHOOK_SECRET=" .env; then
  SECRET=$($PY -c "import secrets; print(secrets.token_urlsafe(24))")
  echo "TG_WEBHOOK_SECRET=$SECRET" >> .env
  echo "  сгенерирован TG_WEBHOOK_SECRET"
else
  echo "  TG_WEBHOOK_SECRET уже задан"
fi

echo
echo "── 2/4 Миграция ───────────────────────────────────────────"
# добавляет записи поле tg_message_id: по нему бот правит своё же сообщение
$PY manage.py migrate barbershop

echo
echo "── 3/4 Перезапуск ─────────────────────────────────────────"
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet mugivara_gunicorn; then
  systemctl restart mugivara_gunicorn && echo "  gunicorn перезапущен"
else
  echo "  сервис mugivara_gunicorn не активен — перезапустите вручную:"
  echo "    systemctl restart mugivara_gunicorn"
fi
sleep 3   # новый адрес вебхука должен отвечать до того, как мы его зарегистрируем

echo
echo "── 4/4 Вебхук Telegram ────────────────────────────────────"
$PY manage.py tg_webhook --set

echo
echo "Готово. Как проверить:"
echo "  1) в кабинете барбершопа должен быть заполнен TG Chat ID;"
echo "  2) $PY manage.py tg_webhook --send <номер записи> — пришлёт карточку в чат;"
echo "  3) нажмите «Подтвердить» — статус поменяется прямо в сообщении."
echo
echo "Состояние вебхука в любой момент: $PY manage.py tg_webhook --info"
