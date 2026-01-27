import os
import re
import requests
import subprocess
from urllib.parse import urlparse
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import instaloader
import telebot
import os
import requests
from bs4 import BeautifulSoup
import instaloader
import re
import shutil
# ================= CONFIG =================
#BOT_TOKEN = os.getenv("BOT_TOKEN")
#DOWNLOAD_DIR = "downloads"
#COOKIES_FILE = "cookies.txt"

#os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ================= FLASK =================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running", 200

@app.route("/health")
def health():
    return {"status": "healthy"}, 200



# Вставьте сюда ваш токен
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)
L = instaloader.Instaloader()

# Папка для временного хранения медиа
DOWNLOAD_FOLDER = "downloads"
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# --- Логика для Pinterest ---
def download_pinterest(url, chat_id):
    try:
        # Используем заголовки, чтобы притвориться обычным браузером
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Ищем мета-тег с изображением высокого качества
        image_tag = soup.find('meta', property='og:image')
        
        if image_tag:
            image_url = image_tag['content']
            img_data = requests.get(image_url).content
            filename = f"{DOWNLOAD_FOLDER}/pin_{chat_id}.jpg"
            
            with open(filename, 'wb') as handler:
                handler.write(img_data)
            
            return filename
        else:
            return None
    except Exception as e:
        print(f"Ошибка Pinterest: {e}")
        return None

# --- Логика для Instagram ---
def download_instagram(url, chat_id):
    try:
        # Извлекаем shortcode из ссылки (например, из https://www.instagram.com/p/CODE123/)
        shortcode_match = re.search(r'/(p|reel)/([^/?#&]+)', url) 
        if not shortcode_match:
            return None
        
        shortcode = shortcode_match.group(2)
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        # Скачиваем пост
        target_dir = f"{DOWNLOAD_FOLDER}/{chat_id}_insta"
        L.download_post(post, target=target_dir)
        
        # Находим скачанный jpg файл
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                if file.endswith(".jpg"):
                    return os.path.join(root, file)
        return None
    except Exception as e:
        print(f"Ошибка Instagram: {e}")
        return None

# --- Обработчик сообщений ---
@bot.message_handler(content_types=['text'])
def handle_message(message):
    url = message.text
    chat_id = message.chat.id
    
    # Проверка на Pinterest
    if "pinterest.com" in url or "pin.it" in url:
        bot.send_message(chat_id, "Скачиваю фото с Pinterest...")
        file_path = download_pinterest(url, chat_id)
        
        if file_path:
            with open(file_path, 'rb') as photo:
                bot.send_photo(chat_id, photo)
            os.remove(file_path) # Удаляем файл после отправки
        else:
            bot.send_message(chat_id, "Не удалось найти изображение.")

    # Проверка на Instagram
    elif "instagram.com" in url:
        bot.send_message(chat_id, "Скачиваю фото с Instagram (это может занять время)...")
        file_path = download_instagram(url, chat_id)
        
        if file_path:
            with open(file_path, 'rb') as photo:
                bot.send_photo(chat_id, photo)
            # Удаляем папку с загрузкой Instagram
            shutil.rmtree(os.path.dirname(file_path))
        else:
            bot.send_message(chat_id, "Не удалось скачать. Возможно, профиль закрыт или Instagram заблокировал запрос.")
            
    else:
        bot.send_message(chat_id, "Отправьте мне ссылку на пост в Instagram или Pinterest.")

# Запуск бота
if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()
