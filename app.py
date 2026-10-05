import os
import threading
from flask import Flask, request
import requests

app = Flask(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = 5604526307

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Кому администратор собирается ответить
reply_to_user = {}

# ID сообщения "✍️ Напиши ответ следующим сообщением."
reply_prompt_message = {}
# Здесь храним исходное сообщение пользователя,
# чтобы показать его при ответе администратора
original_messages = {}

def send_message(chat_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }

    if reply_markup:
        data["reply_markup"] = reply_markup

    return requests.post(
        f"{TG_API}/sendMessage",
        json=data,
        timeout=15,
    ).json()


def delete_message(chat_id, message_id):
    try:
        requests.post(
            f"{TG_API}/deleteMessage",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
            },
            timeout=15,
        )
    except Exception:
        pass


def delete_later(chat_id, message_id, seconds=3):
    timer = threading.Timer(
        seconds,
        delete_message,
        args=(chat_id, message_id)
    )
    timer.daemon = True
    timer.start()


@app.get("/")
def home():
    return "Bot is running", 200


@app.post("/webhook")
def webhook():
    update = request.get_json(silent=True) or {}

    # ==========================================
    # НАЖАТИЕ КНОПКИ "ОТВЕТИТЬ"
    # ==========================================

    callback = update.get("callback_query")

    if callback:
        admin = callback.get("from", {})
        data = callback.get("data", "")

        # Кнопка работает только у администратора
        if admin.get("id") != ADMIN_ID:
            return "OK", 200

        if data.startswith("reply:"):
            user_id = int(data.split(":")[1])

            reply_to_user[ADMIN_ID] = user_id

            # Удаляем старую подсказку, если она осталась
            old_prompt_id = reply_prompt_message.pop(
                ADMIN_ID,
                None
            )

            if old_prompt_id:
                delete_message(
                    ADMIN_ID,
                    old_prompt_id
                )

            result = send_message(
                ADMIN_ID,
                "✍️ Напиши ответ следующим сообщением."
            )

            if result.get("ok"):
                reply_prompt_message[ADMIN_ID] = (
                    result["result"]["message_id"]
                )

        # Убираем загрузку с кнопки Telegram
        requests.post(
            f"{TG_API}/answerCallbackQuery",
            json={
                "callback_query_id": callback["id"]
            },
            timeout=15,
        )

        return "OK", 200

    # ==========================================
    # ОБЫЧНОЕ СООБЩЕНИЕ
    # ==========================================

    message = update.get("message")

    if not message:
        return "OK", 200

    user = message.get("from", {})
    chat_id = message.get("chat", {}).get("id")

    if not chat_id:
        return "OK", 200

    text = message.get("text", "")

    # ==========================================
    # /START
    # ==========================================

    if text.startswith("/start"):

        send_message(
            chat_id,
            "🖤 Анонимные сообщения\n\n"
            "Здесь ты можешь отправить мне сообщение "
            "полностью анонимно.\n\n"
            "Просто напиши текст или отправь фото, "
            "видео, голосовое сообщение — "
            "я получу его и смогу ответить тебе через бота.\n\n"
            "🔒 Твоё сообщение будет доставлено."
        )

        return "OK", 200

    # ==========================================
    # /CANCEL ДЛЯ АДМИНИСТРАТОРА
    # ==========================================

    if (
        user.get("id") == ADMIN_ID
        and text.startswith("/cancel")
    ):

        reply_to_user.pop(
            ADMIN_ID,
            None
        )

        prompt_id = reply_prompt_message.pop(
            ADMIN_ID,
            None
        )

        if prompt_id:
            delete_message(
                ADMIN_ID,
                prompt_id
            )

        result = send_message(
            ADMIN_ID,
            "❌ Ответ отменён."
        )

        if result.get("ok"):
            delete_later(
                ADMIN_ID,
                result["result"]["message_id"],
                3
            )

        return "OK", 200

    # ==========================================
    # ОТВЕТ АДМИНИСТРАТОРА
    # ==========================================

    if user.get("id") == ADMIN_ID:

        if ADMIN_ID in reply_to_user:

            target_user = reply_to_user.pop(
                ADMIN_ID
            )

            # Копируем ответ пользователю
            requests.post(
                f"{TG_API}/copyMessage",
                json={
                    "chat_id": target_user,
                    "from_chat_id": chat_id,
                    "message_id": message["message_id"],
                },
                timeout=15,
            )

            # Удаляем подсказку
            prompt_id = reply_prompt_message.pop(
                ADMIN_ID,
                None
            )

            if prompt_id:
                delete_message(
                    ADMIN_ID,
                    prompt_id
                )

            # Подтверждаем отправку
            result = send_message(
                ADMIN_ID,
                "✅ Ответ отправлен."
            )

            if result.get("ok"):
                delete_later(
                    ADMIN_ID,
                    result["result"]["message_id"],
                    3
                )

        return "OK", 200

    # ==========================================
    # АНОНИМНОЕ СООБЩЕНИЕ
    # ==========================================

    user_id = user.get("id")
    username = user.get("username")
    first_name = user.get(
        "first_name",
        ""
    )
    last_name = user.get(
        "last_name",
        ""
    )

    username_text = (
        f"@{username}"
        if username
        else "не установлен"
    )

    full_name = (
        f"{first_name} {last_name}".strip()
        or "не указано"
    )

    info = (
        "🔐 Новое сообщение\n\n"
        f"👤 Имя: {full_name}\n"
        f"🔗 Username: {username_text}\n"
        f"🆔 Telegram ID: {user_id}"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "↩️ Ответить",
                    "callback_data": f"reply:{user_id}"
                }
            ]
        ]
    }

    # Информация об отправителе только администратору
    send_message(
        ADMIN_ID,
        info,
        reply_markup=keyboard
    )

    # Копируем само сообщение администратору
    requests.post(
        f"{TG_API}/copyMessage",
        json={
            "chat_id": ADMIN_ID,
            "from_chat_id": chat_id,
            "message_id": message["message_id"],
        },
        timeout=15,
    )

    # Временное подтверждение отправителю
    result = send_message(
        chat_id,
        "✅ Сообщение отправлено анонимно."
    )

    # Удаляем подтверждение через 3 секунды
    if result.get("ok"):
        delete_later(
            chat_id,
            result["result"]["message_id"],
            3
        )

    return "OK", 200
