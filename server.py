"""
Сайт + API + Telegram-бот (webhook) в одном процессе.
Работает 24/7 на хостинге, ПК не нужен.

Env на хостинге:
  BOT_TOKEN  - токен от @BotFather
  AUTH_TOKEN - любой секрет, например сгенерируй 32 символа
  PUBLIC_URL - https://твой-домен-от-render (без слэша в конце)
  DATA_DIR   - /data (для Render Disk, чтобы songs.json не стирался)
  PORT       - ставит сам хостинг

После деплоя открой 1 раз: https://твой-домен/setup
Это поставит webhook Telegram -> твой сайт.
"""
import json
import os
import re
import time
import requests
from flask import Flask, request, jsonify, Response

BASE_DIR = os.path.dirname(os.path.abspath(__name__))
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "songs.json")

AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "CHANGE_ME_SECRET_123")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")

app = Flask(__name__)

# ---------- DB ----------
def load_songs():
    if not os.path.exists(DB_PATH):
        return []
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def save_songs(songs):
    tmp = DB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(songs, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DB_PATH)

# ---------- Roblox check ----------
def check_roblox_audio(song_id: str):
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
        return True, j.get("Name", song_id), bool(j.get("IsPublicDomain"))
    except Exception as e:
        return False, f"Roblox API недоступен: {e}", False

def extract_id(text: str):
    if not text:
        return None
    m = re.findall(r"\d{5,12}", text)
    return max(m, key=len) if m else None

# ---------- Telegram ----------
def tg_send(chat_id, text):
    if not BOT_TOKEN:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception as e:
        print("tg_send error:", e)

def handle_telegram_text(chat_id, user_id, text):
    song_id = extract_id(text)
    if text.startswith("/start"):
        tg_send(chat_id, "Кинь ID музыки (цифры / ссылку / rbxassetid://...). Проверю дубль и работоспособность, добавлю на сайт.\n/list — показать базу.")
        return
    if text.startswith("/list"):
        songs = load_songs()
        if not songs:
            tg_send(chat_id, "Пока пусто.")
        else:
            txt = "\n".join(f"{s['id']} — {s.get('name','?')}" for s in songs[-20:])
            tg_send(chat_id, f"База ({len(songs)}):\n{txt}")
        return
    if not song_id:
        tg_send(chat_id, "Не вижу ID. Пример: 1837879082")
        return
    # дубль
    songs = load_songs()
    if any(str(s["id"]) == song_id for s in songs):
        tg_send(chat_id, f"⛔ {song_id} уже есть в базе.")
        return
    # работоспособность
    ok, name_or_err, is_public = check_roblox_audio(song_id)
    if not ok:
        tg_send(chat_id, f"❌ {song_id}: {name_or_err}")
        return
    songs.append({"id": int(song_id), "name": name_or_err, "added_by": str(user_id), "added_at": int(time.time())})
    save_songs(songs)
    warn = "" if is_public else "\n⚠️ НЕ public — в чужой игре может не играть."
    tg_send(chat_id, f"✅ Добавлено: {song_id} — {name_or_err}{warn}")

@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    update = request.get_json(force=True, silent=True) or {}
    msg = update.get("message") or update.get("edited_message") or {}
    text = msg.get("text", "")
    chat = msg.get("chat", {}).get("id")
    user = msg.get("from", {}).get("id", "")
    if chat and text:
        handle_telegram_text(chat, user, text)
    return jsonify({"ok": True})

@app.route("/setup")
def setup():
    """Открыть 1 раз после деплоя чтобы привязать бота к сайту."""
    if not BOT_TOKEN or not PUBLIC_URL:
        return "Задай BOT_TOKEN и PUBLIC_URL в env хостинга", 500
    r = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
        params={"url": f"{PUBLIC_URL}/telegram"},
        timeout=10,
    )
    return r.text, r.status_code

# ---------- Site / API for Roblox ----------
@app.route("/")
def index():
    songs = load_songs()
    items = "".join(
        f"<li><b>{s.get('id')}</b> — {s.get('name','?')}</li>" for s in songs
    ) or "<li>пока пусто — кинь ID в Telegram-бота</li>"
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>Roblox Music DB</title></head><body style="font-family:sans-serif;max-width:700px;margin:40px auto">
<h1>🎵 Roblox Music DB ({len(songs)})</h1><ul>{items}</ul>
<p>Roblox: <code>game:HttpGet("{PUBLIC_URL or 'https://ВАШ-ДОМЕН'}/api/songs")</code></p>
</body></html>"""

@app.route("/api/songs")
def api_songs():
    return jsonify({"songs": load_songs()})

@app.route("/raw")
def raw():
    return Response("\n".join(str(s["id"]) for s in load_songs()), mimetype="text/plain")

@app.route("/api/add", methods=["POST"])
def api_add():
    # оставил для совместимости с bot.py (polling-режим)
    if request.headers.get("X-Auth") != AUTH_TOKEN:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(force=True, silent=True) or {}
    try:
        song_id = int(str(data.get("id", "")).strip())
    except Exception:
        return jsonify({"ok": False, "error": "bad id"}), 400
    songs = load_songs()
    if any(int(s["id"]) == song_id for s in songs):
        return jsonify({"ok": False, "error": "duplicate"}), 409
    songs.append({"id": song_id, "name": str(data.get("name",""))[:120] or str(song_id),
                  "added_by": str(data.get("added_by",""))[:64], "added_at": int(time.time())})
    save_songs(songs)
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
