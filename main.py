import os
import re
import subprocess
import requests
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters
)

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DOWNLOAD_DIR = "downloads"
COOKIES_FILE = "cookies.txt"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ================= FLASK =================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running", 200

@app.route("/health")
def health():
    return {"status": "healthy"}, 200

# ================= UTILS =================
def extract_urls(text: str):
    return re.findall(r'(https?://[^\s]+)', text)

async def get_full_url(url):
    try:
        r = requests.head(url, allow_redirects=True, timeout=5)
        return r.url
    except:
        return url

# ================= COMMANDS =================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
🤖 *Multi Downloader Bot*

Поддержка:
• TikTok (только видео)
• Instagram Reels (без фото)
• Pinterest (только видео)
• YouTube Shorts

📌 Просто отправь ссылку
    """
    await update.message.reply_text(text, parse_mode="Markdown")
# ================= загруз =================
async def download_any(update, url):
    status = await update.message.reply_text("⏳ Скачиваю контент...")

    output = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")

    command = [
        "yt-dlp",
        "--no-check-certificate",
        "--cookies", COOKIES_FILE if os.path.exists(COOKIES_FILE) else "",
        "--merge-output-format", "mp4",
        "-o", output,
        url
    ]

    # убираем пустой аргумент cookies
    command = [c for c in command if c != ""]

    try:
        subprocess.run(command, check=True)

        files = sorted(
            os.listdir(DOWNLOAD_DIR),
            key=lambda x: os.path.getctime(os.path.join(DOWNLOAD_DIR, x))
        )

        await status.delete()

        if not files:
            await update.message.reply_text("❌ Контент не найден")
            return

        for file in files:
            path = os.path.join(DOWNLOAD_DIR, file)

            if file.lower().endswith((".mp4", ".mov", ".webm")):
                await update.message.reply_video(
                    open(path, "rb"),
                    caption="скачано с помощью @instbotsavebot"
                )
            elif file.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                await update.message.reply_photo(open(path, "rb"))
            else:
                await update.message.reply_document(open(path, "rb"))

            os.remove(path)

    except subprocess.CalledProcessError:
        await status.delete()
        await update.message.reply_text("❌ Ошибка при скачивании")

# ================= MAIN HANDLER =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    urls = extract_urls(update.message.text)

    if not urls:
        await update.message.reply_text("❌ Я не нашёл ссылок в сообщении")
        return

    url = await get_full_url(urls[0])

    await download_any(update, url)

# ================= START =================
def run_flask():
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не задан")
        return

    Thread(target=run_flask, daemon=True).start()

    bot = ApplicationBuilder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start_command))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    bot.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
