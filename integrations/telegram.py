import requests

def send_message(bot_token: str, chat_id: str, text: str, parse_mode: str | None = None, message_thread_id: int | None = None):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": str(chat_id),
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    # 1) пробуем с thread_id (если задан)
    if message_thread_id:
        payload_with_thread = {**payload, "message_thread_id": int(message_thread_id)}
        r = requests.post(url, json=payload_with_thread, timeout=15)
        if r.status_code == 200:
            return r.json()

        # если thread не найден — повторяем без темы
        if r.status_code == 400 and "message thread not found" in r.text:
            r2 = requests.post(url, json=payload, timeout=15)
            if r2.status_code != 200:
                raise Exception(f"Telegram error {r2.status_code}: {r2.text}")
            return r2.json()

        raise Exception(f"Telegram error {r.status_code}: {r.text}")

    # 2) если thread_id нет — обычная отправка
    r = requests.post(url, json=payload, timeout=15)
    if r.status_code != 200:
        raise Exception(f"Telegram error {r.status_code}: {r.text}")
    return r.json()
