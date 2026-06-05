import os
import json
import requests
from datetime import date, timedelta
from flask import Flask, request

app = Flask(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
DATA_FILE = "message_data.json"

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    })

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def record_message(user_id, username, today):
    data = load_data()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"name": username, "daily": {}, "total": 0}
    data[uid]["name"] = username
    if today not in data[uid]["daily"]:
        data[uid]["daily"][today] = 0
    data[uid]["daily"][today] += 1
    data[uid]["total"] += 1
    save_data(data)

def build_leaderboard(scores, title):
    if not scores:
        return f"*{title}*\n\nKoi data nahi mila 😕"
    sorted_users = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"*{title}*\n"]
    for i, (name, count) in enumerate(sorted_users):
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{medal} {name} — *{count}* msgs")
    return "\n".join(lines)

def handle_update(update):
    message = update.get("message", {})
    if not message:
        return

    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")
    user = message.get("from", {})
    user_id = user.get("id")
    first = user.get("first_name", "")
    last = user.get("last_name", "")
    username = f"{first} {last}".strip() or user.get("username") or f"User_{user_id}"
    today = str(date.today())

    if text.startswith("/start"):
        send_message(chat_id,
            "👋 *Ranking Bot Active Hai!*\n\n"
            "Commands:\n"
            "📊 /today — Aaj ki ranking\n"
            "📅 /yesterday — Kal ki ranking\n"
            "📆 /week — Is hafte ki ranking\n"
            "🏆 /overall — Sab ka total\n\n"
            "Bas group mein baat karo, sab track hoga! 🔥"
        )

    elif text.startswith("/today"):
        data = load_data()
        scores = {v["name"]: v["daily"].get(today, 0)
                  for v in data.values() if v["daily"].get(today, 0) > 0}
        send_message(chat_id, build_leaderboard(scores, f"📊 Aaj Ki Ranking ({today})"))

    elif text.startswith("/yesterday"):
        data = load_data()
        yesterday = str(date.today() - timedelta(days=1))
        scores = {v["name"]: v["daily"].get(yesterday, 0)
                  for v in data.values() if v["daily"].get(yesterday, 0) > 0}
        send_message(chat_id, build_leaderboard(scores, f"📅 Kal Ki Ranking ({yesterday})"))

    elif text.startswith("/week"):
        data = load_data()
        week_dates = [str(date.today() - timedelta(days=i)) for i in range(7)]
        scores = {}
        for v in data.values():
            count = sum(v["daily"].get(d, 0) for d in week_dates)
            if count > 0:
                scores[v["name"]] = count
        send_message(chat_id, build_leaderboard(scores, "📆 Is Hafte Ki Ranking (Last 7 Days)"))

    elif text.startswith("/overall"):
        data = load_data()
        scores = {v["name"]: v["total"] for v in data.values() if v["total"] > 0}
        send_message(chat_id, build_leaderboard(scores, "🏆 Overall Ranking (All Time)"))

    else:
        if user_id:
            record_message(user_id, username, today)

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(force=True)
    handle_update(update)
    return "OK"

@app.route("/")
def home():
    return "Bot is running!"

@app.route("/set_webhook")
def set_webhook():
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
    res = requests.post(url, json={
        "url": f"{WEBHOOK_URL}/webhook",
        "drop_pending_updates": True
    })
    return f"Webhook set: {res.json()}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
