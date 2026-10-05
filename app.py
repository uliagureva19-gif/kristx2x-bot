import os
from flask import Flask, request
import requests

app = Flask(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = 5604526307

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id, text):
    requests.post(
        f"{TG_API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=15,
    )


@app.get("/")
def home():
    return "Bot is running", 200


@app.post("/webhook")
def webhook():
    update = request.get_json(silent=True) or {}
    message = update.get("message")

    if not message:
        return "OK", 200

    user = message.get("from", {})
    chat_id = message.get("chat", {}).get("id")

    # Не пересылаем администратору его собственные сообщения
    if not chat_id or user.get("id") == ADMIN_ID:
        return "OK", 200

    user_id = user.get("id")
    username = user.get("username")
    first_name = user.get("first_name", "")
    last_name = user.get("last_name", "")

    username_text = f"@{username}" if username else "не установлен"
    full_name = f"{first_name} {last_name}".strip() or "не указано"

    info = (
        "🔐 Новое сообщение\n\n"
        f"👤 Имя: {full_name}\n"
        f"🔗 Username: {username_text}\n"
        f"🆔 Telegram ID: {user_id}"
    )

    send_message(ADMIN_ID, info)

    # Копируем само сообщение администратору:
    # текст, фото, видео, голосовое и т. д.
    requests.post(
        f"{TG_API}/copyMessage",
        json={
            "chat_id": ADMIN_ID,
            "from_chat_id": chat_id,
            "message_id": message["message_id"],
        },
        timeout=15,
    )

    send_message(
        chat_id,
        "✅ Сообщение отправлено анонимно."
    )

    return "OK", 200
