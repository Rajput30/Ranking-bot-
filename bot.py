import os
import requests
import psycopg2
from datetime import date, timedelta
from flask import Flask, request

app = Flask(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            chat_id TEXT,
            user_id TEXT,
            username TEXT,
            tg_username TEXT,
            msg_date TEXT,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, user_id, msg_date)
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    })

def record_message(chat_id, user_id, username, tg_username, today):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO messages (chat_id, user_id, username, tg_username, msg_date, count)
        VALUES (%s, %s, %s, %s, %s, 1)
        ON CONFLICT (chat_id, user_id, msg_date)
        DO UPDATE SET count = messages.count + 1,
                      username = EXCLUDED.username,
                      tg_username = EXCLUDED.tg_username
    """, (str(chat_id), str(user_id), username, tg_username, today))
    conn.commit()
    cur.close()
    conn.close()

def get_scores_for_dates(chat_id, dates):
    conn = get_conn()
    cur = conn.cursor()
    placeholders = ','.join(['%s'] * len(dates))
    cur.execute(f"""
        SELECT username, tg_username, SUM(count) as total
        FROM messages
        WHERE chat_id = %s AND msg_date IN ({placeholders})
        GROUP BY username, tg_username
        ORDER BY total DESC
    """, [str(chat_id)] + dates)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_overall_scores(chat_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT username, tg_username, SUM(count) as total
        FROM messages
        WHERE chat_id = %s
        GROUP BY username, tg_username
        ORDER BY total DESC
    """, (str(chat_id),))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def build_leaderboard(rows, title):
    if not rows:
        return f"*{title}*\n\nKoi data nahi mila 😕"
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"*{title}*\n"]
    for i, (name, tg_username, count) in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{medal} {name} — *{count}* msgs")
    return "\n".join(lines)

def build_congrats(rows):
    if not rows:
        return None
    congrats_templates = [
        "🎉 Congratulations {tag}! Aap is baar ke *Chat King* hain! 👑🔥",
        "🥈 Shabash {tag}! Aap doosre number pe hain! 💪 Keep it up!",
        "🥉 Wah {tag}! Teesre number pe ho, mazboot raho! 🔥"
    ]
    lines = ["🏅 *Top Chatters Ko Badhai!*\n"]
    for i, template in enumerate(congrats_templates):
        if i < len(rows):
            name, tg_username, count = rows[i]
            tag = f"@{tg_username}" if tg_username else f"*{name}*"
            lines.append(template.format(tag=tag))
    return "\n".join(lines)

def handle_update(update):
    message = update.get("message", {})
    if not message:
        return

    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "") or ""
    user = message.get("from", {})
    user_id = user.get("id")
    first = user.get("first_name", "")
    last = user.get("last_name", "")
    tg_username = user.get("username", "")
    username = f"{first} {last}".strip() or tg_username or f"User_{user_id}"
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
        rows = get_scores_for_dates(chat_id, [today])
        send_message(chat_id, build_leaderboard(rows, f"📊 Aaj Ki Ranking ({today})"))
        congrats = build_congrats(rows)
        if congrats:
            send_message(chat_id, congrats)

    elif text.startswith("/yesterday"):
        yesterday = str(date.today() - timedelta(days=1))
        rows = get_scores_for_dates(chat_id, [yesterday])
        send_message(chat_id, build_leaderboard(rows, f"📅 Kal Ki Ranking ({yesterday})"))
        congrats = build_congrats(rows)
        if congrats:
            send_message(chat_id, congrats)

    elif text.startswith("/week"):
        week_dates = [str(date.today() - timedelta(days=i)) for i in range(7)]
        rows = get_scores_for_dates(chat_id, week_dates)
        send_message(chat_id, build_leaderboard(rows, "📆 Is Hafte Ki Ranking (Last 7 Days)"))
        congrats = build_congrats(rows)
        if congrats:
            send_message(chat_id, congrats)

    elif text.startswith("/overall"):
        rows = get_overall_scores(chat_id)
        send_message(chat_id, build_leaderboard(rows, "🏆 Overall Ranking (All Time)"))
        congrats = build_congrats(rows)
        if congrats:
            send_message(chat_id, congrats)

    else:
        if user_id:
            record_message(chat_id, user_id, username, tg_username, today)

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(force=True)
    handle_update(update)
    return "OK"

@app.route("/")
def home():
    init_db()
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
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
