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

# ================= CORE DOWNLOAD =================
async def download_any(update, url):
    status = await update.message.reply_text("⏳ Скачиваю контент...")

    # YouTube Shorts → watch
    if "youtube.com/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0]
        url = f"https://www.youtube.com/watch?v={vid}"

    # Pinterest sent/invite → clean pin URL
    if "pinterest.com" in url and "/pin/" in url:
        m = re.search(r"/pin/(\d+)", url)
        if m:
            url = f"https://www.pinterest.com/pin/{m.group(1)}/"

    clean_downloads()

    output = os.path.join(DOWNLOAD_DIR, "%(id)s_%(title).80s.%(ext)s")

    base_cmd = [
        "yt-dlp",
        "--no-check-certificate",
        "--yes-playlist",
        "-o", output,
        url
    ]

    if os.path.exists(COOKIES_FILE):
        base_cmd.insert(1, "--cookies")
        base_cmd.insert(2, COOKIES_FILE)

    # === TRY VIDEO FIRST ===
    result = subprocess.run(
        base_cmd + ["-f", "bv*+ba/best", "--merge-output-format", "mp4"],
        stderr=subprocess.PIPE
    )

    # === IF NO VIDEO → IMAGES ===
    if result.returncode != 0 and b"No video formats found" in result.stderr:
        subprocess.run(
            base_cmd + [
                "--no-video",
                "--extractor-args", "pinterest:download_images=true",
                "--convert-thumbnails", "jpg"
            ],
            check=False
        )

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
        ext = file.lower()

        if ext.endswith((".mp4", ".webm", ".mov")):
            await update.message.reply_video(
                open(path, "rb"),
                caption="скачано с помощью @instbotsavebot"
            )
        elif ext.endswith((".jpg", ".jpeg", ".png")):
            await update.message.reply_photo(open(path, "rb"))
        else:
            await update.message.reply_document(open(path, "rb"))

        os.remove(path)

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
