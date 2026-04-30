import os
import logging
import requests
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    ContextTypes, filters, ConversationHandler
)

BOT_TOKEN = "8365752689:AAGlvlW03sNQHPVK-Ewm8DHOslz4Hhm1t3Q"

# Flask app to keep alive
keep_alive = Flask(__name__)

@keep_alive.route('/')
def home():
    return "Bot is Running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    keep_alive.run(host="0.0.0.0", port=port)

# Conversation states
ASK_APIKEY, ASK_CHANNEL, ASK_AMOUNT = range(3)

# User data storage
user_configs = {}
used_posts = set()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─── /start ───────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("👋 স্বাগতম!\n\nআপনার *API Key* দিন:", parse_mode="Markdown")
    return ASK_APIKEY


# ─── API Key সেভ ──────────────────────────────────────────
async def save_apikey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    apikey = update.message.text.strip()
    user_configs[user_id] = {"apikey": apikey}
    await update.message.reply_text("✅ API Key সেভ!\n\n*চ্যানেল লিংক* দিন:", parse_mode="Markdown")
    return ASK_CHANNEL


# ─── Channel সেভ ──────────────────────────────────────────
async def save_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    channel = update.message.text.strip()
    user_configs[user_id]["channel"] = channel
    await update.message.reply_text("✅ চ্যানেল সেভ!\n\n*Amount* দিন:", parse_mode="Markdown")
    return ASK_AMOUNT


# ─── Amount সেভ ───────────────────────────────────────────
async def save_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    amount = update.message.text.strip()

    if not amount.isdigit():
        await update.message.reply_text("❌ সংখ্যা দিন!")
        return ASK_AMOUNT

    user_configs[user_id]["amount"] = amount
    cfg = user_configs[user_id]

    await update.message.reply_text(
        f"🎉 *সেটআপ সম্পন্ন!*\n"
        f"🔑 API: `{cfg['apikey']}`\n"
        f"📢 চ্যানেল: {cfg['channel']}\n"
        f"📊 Amount: {cfg['amount']}\n\n"
        f"⚠️ বটকে চ্যানেলে Admin বানান!\n"
        f"🔄 /start দিয়ে পরিবর্তন করুন।",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ─── Cancel ───────────────────────────────────────────────
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ বাতিল। /start দিন")
    return ConversationHandler.END


# ─── Channel Post Handler ─────────────────────────────────
async def handle_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.channel_post
        if not message:
            return

        chat = message.chat
        if not chat.username:
            return

        post_link = f"https://t.me/{chat.username}/{message.message_id}"

        if post_link in used_posts:
            return
        used_posts.add(post_link)

        # Match channel
        matched_config = None
        for cfg in user_configs.values():
            if chat.username in cfg.get("channel", ""):
                matched_config = cfg
                break

        if not matched_config and user_configs:
            matched_config = list(user_configs.values())[-1]

        if not matched_config:
            return

        apikey = matched_config["apikey"]
        amount = matched_config.get("amount", "20")

        api_url = (
            f"https://smmgem.bdusp.xyz/?api=1"
            f"&key={apikey}"
            f"&action=add"
            f"&service=SVC8B26298D"
            f"&link={post_link}"
            f"&quantity={amount}"
        )

        response = requests.get(api_url, timeout=10)
        logger.info(f"✅ Post: {post_link}")
        logger.info(f"✅ Response: {response.text}")

    except Exception as e:
        logger.error(f"Error: {e}")


# ─── Main ─────────────────────────────────────────────────
def main():
    # Flask সার্ভার থ্রেডে চালু
    Thread(target=run_flask, daemon=True).start()

    # Bot start
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_APIKEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_apikey)],
            ASK_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_channel)],
            ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_post))

    logger.info("🤖 Bot Started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
