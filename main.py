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

# ================= TikTok =================
async def download_tiktok(update, url):
    status = await update.message.reply_text("⏳ Скачиваю TikTok...")

    try:
        api_url = f"https://www.tikwm.com/api/?url={url}"
        data = requests.get(api_url, timeout=15).json()
        await status.delete()

        if data.get("code") != 0:
            await update.message.reply_text("❌ TikTok контент не найден")
            return

        content = data.get("data", {})

        if content.get("play"):
            await update.message.reply_video(content["play"])
            return

        if content.get("images"):
            await update.message.reply_text("❌ Скачивание фото из TikTok невозможно")
            return

        await update.message.reply_text("❌ Неподдерживаемый тип TikTok контента")

    except Exception:
        await status.delete()
        await update.message.reply_text("⚠️ Ошибка TikTok")

# ================= Instagram =================
async def download_instagram(update, url):
    if not os.path.exists(COOKIES_FILE):
        await update.message.reply_text("❌ cookies.txt не найден")
        return

    if "/reel/" not in url:
        await update.message.reply_text("❌ Скачивание фото из Instagram запрещено")
        return

    status = await update.message.reply_text("⏳ Скачиваю Instagram Reel...")

    if "?" in url:
        url = url.split("?")[0]

    output = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")

    command = [
        "yt-dlp",
        "--cookies", COOKIES_FILE,
        "--no-check-certificate",
        "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]",
        "-o", output,
        url
    ]

    try:
        subprocess.run(command, check=True)

        files = sorted(
            os.listdir(DOWNLOAD_DIR),
            key=lambda x: os.path.getctime(os.path.join(DOWNLOAD_DIR, x)),
            reverse=True
        )

        await status.delete()

        if not files:
            await update.message.reply_text("❌ Видео не найдено")
            return

        path = os.path.join(DOWNLOAD_DIR, files[0])
        await update.message.reply_video(open(path, "rb"))
        os.remove(path)

    except subprocess.CalledProcessError:
        await status.delete()
        await update.message.reply_text("❌ Не удалось скачать Instagram Reel")

# ================= Pinterest =================
async def download_pinterest(update, url):
    status = await update.message.reply_text("⏳ Скачиваю Pinterest...")

    output = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")

    command = [
        "yt-dlp",
        "-f", "bv*+ba/b",
        "-o", output,
        url
    ]

    try:
        subprocess.run(command, check=True)

        files = sorted(
            os.listdir(DOWNLOAD_DIR),
            key=lambda x: os.path.getctime(os.path.join(DOWNLOAD_DIR, x)),
            reverse=True
        )

        await status.delete()

        if not files:
            await update.message.reply_text("❌ Контент не найден")
            return

        path = os.path.join(DOWNLOAD_DIR, files[0])

        if not path.endswith(".mp4"):
            await update.message.reply_text("❌ Скачивание фото из Pinterest запрещено")
            os.remove(path)
            return

        await update.message.reply_video(open(path, "rb"))
        os.remove(path)

    except subprocess.CalledProcessError:
        await status.delete()
        await update.message.reply_text("❌ Не удалось скачать Pinterest")

# ================= YouTube Shorts =================
async def download_youtube_shorts(update, url):
    if not os.path.exists(COOKIES_FILE):
        await update.message.reply_text("❌ cookies.txt не найден")
        return

    status = await update.message.reply_text("⏳ Скачиваю YouTube Shorts...")

    output = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")

    command = [
        "yt-dlp",
        "--cookies", COOKIES_FILE,
        "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]",
        "-o", output,
        url
    ]

    try:
        subprocess.run(command, check=True)

        files = sorted(
            os.listdir(DOWNLOAD_DIR),
            key=lambda x: os.path.getctime(os.path.join(DOWNLOAD_DIR, x)),
            reverse=True
        )

        await status.delete()

        if not files:
            await update.message.reply_text("❌ Shorts не найден")
            return

        path = os.path.join(DOWNLOAD_DIR, files[0])
        await update.message.reply_video(open(path, "rb"))
        os.remove(path)

    except subprocess.CalledProcessError:
        await status.delete()
        await update.message.reply_text(
            "❌ Не удалось скачать YouTube Shorts\n"
        )


# ================= MAIN HANDLER =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    urls = extract_urls(update.message.text)

    if not urls:
        await update.message.reply_text("❌ Я не нашёл ссылок в сообщении")
        return

    url = await get_full_url(urls[0])

    if "tiktok.com" in url:
        await download_tiktok(update, url)
    elif "instagram.com" in url:
        await download_instagram(update, url)
    elif "pinterest.com" in url or "pin.it" in url:
        await download_pinterest(update, url)
    elif "youtube.com/shorts" in url or "youtu.be" in url:
        await download_youtube_shorts(update, url)
    else:
        await update.message.reply_text("❌ Ссылка не поддерживается")

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
