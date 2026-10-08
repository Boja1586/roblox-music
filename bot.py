"""
Telegram-бот: приём ID -> проверка на дубль + работоспособность -> отправка на сайт.
Запуск: python bot.py
Нужно: BOT_TOKEN от @BotFather, API_URL твоего сайта, AUTH_TOKEN как в server.py
"""
import os
import re
import requests
import telebot

BOT_TOKEN = os.environ.get("BOT_TOKEN", "ВСТАВЬ_ТОКЕН_СЮДА")
API_URL = os.environ.get("API_URL", "http://127.0.0.1:5000").rstrip("/")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "CHANGE_ME_SECRET_123")

bot = telebot.TeleBot(BOT_TOKEN)

def extract_id(text: str):
    """Вытаскивает ID из: 1837879082, rbxassetid://1837879082, https://www.roblox.com/library/1837879082/..."""
    if not text:
        return None
    m = re.findall(r"\d{5,12}", text)
    if not m:
        return None
    # берём самое длинное число (ID обычно 9-11 цифр)
    return max(m, key=len)

def get_existing_ids():
    try:
        r = requests.get(f"{API_URL}/api/songs", timeout=10)
        r.raise_for_status()
        return {str(s["id"]) for s in r.json().get("songs", [])}
    except Exception:
        return None  # сайт недоступен

def check_roblox_audio(song_id: str):
    """
    Проверка работоспособности через официальный Roblox API.
    Возвращает (ok: bool, name_or_error: str, is_public: bool)
    """
    try:
        r = requests.get(
            f"https://economy.roblox.com/v2/assets/{song_id}/details",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        if r.status_code == 404:
            return False, "ассет не найден (удалён или ID неверный)", False
        r.raise_for_status()
        j = r.json()
        if j.get("AssetTypeId") != 3:
            return False, f"это не аудио (AssetTypeId={j.get('AssetTypeId')})", False
        name = j.get("Name", song_id)
        is_public = bool(j.get("IsPublicDomain"))
        return True, name, is_public
    except Exception as e:
        return False, f"Roblox API недоступен: {e}", False

@bot.message_handler(commands=["start"])
def start(m):
    bot.reply_to(m, "Кинь ID музыки (цифры, ссылку на library или rbxassetid://...).\nПроверю на дубль и работоспособность, потом добавлю на сайт.\n/list — показать добавленные.")

@bot.message_handler(commands=["list"])
def list_cmd(m):
    try:
        r = requests.get(f"{API_URL}/api/songs", timeout=10).json()
        songs = r.get("songs", [])
        if not songs:
            bot.reply_to(m, "Пока пусто.")
            return
        txt = "\n".join(f"{s['id']} — {s.get('name','?')}" for s in songs[-20:])
        bot.reply_to(m, f"Последние:\n{txt}")
    except Exception as e:
        bot.reply_to(m, f"Сайт недоступен: {e}")

@bot.message_handler(func=lambda m: True)
def handle_id(m):
    song_id = extract_id(m.text)
    if not song_id:
        bot.reply_to(m, "Не вижу ID. Пришли цифры, например: 1837879082")
        return

    # 1. дубль
    existing = get_existing_ids()
    if existing is None:
        bot.reply_to(m, "⚠️ Сайт недоступен, не могу проверить дубль. Попробуй позже.")
        return
    if song_id in existing:
        bot.reply_to(m, f"⛔ {song_id} уже есть в базе.")
        return

    # 2. работоспособность
    msg = bot.reply_to(m, f"⏳ Проверяю {song_id} в Roblox...")
    ok, name_or_err, is_public = check_roblox_audio(song_id)
    if not ok:
        bot.edit_message_text(f"❌ {song_id}: {name_or_err}", msg.chat.id, msg.message_id)
        return

    warn = "" if is_public else "\n⚠️ Аудио НЕ public — в чужой игре может не играть (Audio Privacy). Лучше public."

    # 3. добавление на сайт
    try:
        r = requests.post(
            f"{API_URL}/api/add",
            json={"id": int(song_id), "name": name_or_err, "added_by": str(m.from_user.id)},
            headers={"X-Auth": AUTH_TOKEN},
            timeout=10,
        )
        if r.status_code == 409:
            bot.edit_message_text(f"⛔ {song_id} уже есть в базе.", msg.chat.id, msg.message_id)
            return
        r.raise_for_status()
        bot.edit_message_text(f"✅ Добавлено: {song_id} — {name_or_err}{warn}\nУже на сайте: {API_URL}/api/songs", msg.chat.id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Не смог сохранить на сайт: {e}", msg.chat.id, msg.message_id)

print("bot polling...")
bot.infinity_polling()
