import os
import json
import logging
import asyncio
import nest_asyncio
from datetime import date, timedelta
from telegram import Update
from telegram.ext import (
    Application, MessageHandler, CommandHandler,
    ContextTypes, filters
)
from flask import Flask, request

nest_asyncio.apply()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

DATA_FILE = "message_data.json"
flask_app = Flask(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")

application = Application.builder().token(TOKEN).build()

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

async def record_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    user = update.effective_user
    user_id = str(user.id)
    username = user.full_name or user.username or f"User_{user_id}"
    today = str(date.today())
    data = load_data()
    if user_id not in data:
        data[user_id] = {"name": username, "daily": {}, "total": 0}
    data[user_id]["name"] = username
    if today not in data[user_id]["daily"]:
        data[user_id]["daily"][today] = 0
    data[user_id]["daily"][today] += 1
    data[user_id]["total"] += 1
    save_data(data)

def build_leaderboard(scores: dict, title: str) -> str:
    if not scores:
        return f"*{title}*\n\nKoi data nahi mila 😕"
    sorted_users = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"*{title}*\n"]
    for i, (name, count) in enumerate(sorted_users):
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{medal} {name} — *{count}* msgs")
    return "\n".join(lines)

async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    today = str(date.today())
    scores = {info["name"]: info["daily"].get(today, 0)
              for uid, info in data.items() if info["daily"].get(today, 0) > 0}
    await update.message.reply_text(
        build_leaderboard(scores, f"📊 Aaj Ki Ranking ({today})"),
        parse_mode="Markdown"
    )

async def cmd_yesterday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    yesterday = str(date.today() - timedelta(days=1))
    scores = {info["name"]: info["daily"].get(yesterday, 0)
              for uid, info in data.items() if info["daily"].get(yesterday, 0) > 0}
    await update.message.reply_text(
        build_leaderboard(scores, f"📅 Kal Ki Ranking ({yesterday})"),
        parse_mode="Markdown"
    )

async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    today = date.today()
    week_dates = [str(today - timedelta(days=i)) for i in range(7)]
    scores = {}
    for uid, info in data.items():
        count = sum(info["daily"].get(d, 0) for d in week_dates)
        if count > 0:
            scores[info["name"]] = count
    await update.message.reply_text(
        build_leaderboard(scores, "📆 Is Hafte Ki Ranking (Last 7 Days)"),
        parse_mode="Markdown"
    )

async def cmd_overall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    scores = {info["name"]: info["total"]
              for uid, info in data.items() if info["total"] > 0}
    await update.message.reply_text(
        build_leaderboard(scores, "🏆 Overall Ranking (All Time)"),
        parse_mode="Markdown"
    )

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 *Ranking Bot Active Hai!*\n\n"
        "Commands:\n"
        "📊 /today — Aaj ki ranking\n"
        "📅 /yesterday — Kal ki ranking\n"
        "📆 /week — Is hafte ki ranking\n"
        "🏆 /overall — Sab ka total\n\n"
        "Bas group mein baat karo, sab track hoga! 🔥"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

application.add_handler(CommandHandler("start", cmd_start))
application.add_handler(CommandHandler("today", cmd_today))
application.add_handler(CommandHandler("yesterday", cmd_yesterday))
application.add_handler(CommandHandler("week", cmd_week))
application.add_handler(CommandHandler("overall", cmd_overall))
application.add_handler(MessageHandler(
    filters.TEXT & ~filters.COMMAND, record_message
))

@flask_app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    asyncio.get_event_loop().run_until_complete(
        application.process_update(update)
    )
    return "OK"

@flask_app.route("/")
def home():
    return "Bot is running!"

@flask_app.route("/set_webhook")
def set_webhook_route():
    async def _set():
        await application.bot.set_webhook(
            url=f"{WEBHOOK_URL}/webhook",
            drop_pending_updates=True
        )
    asyncio.get_event_loop().run_until_complete(_set())
    return f"Webhook set to {WEBHOOK_URL}/webhook"

@flask_app.route("/init")
def init():
    asyncio.get_event_loop().run_until_complete(application.initialize())
    return "Initialized!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
