import telebot
import os
import requests
from bs4 import BeautifulSoup
import instaloader
import re
import shutil 
from flask import Flask
from threading import Thread

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Вместо логина/пароля берем Session ID из переменных окружения
INSTA_SESSION_ID = os.environ.get('INSTA_SESSION_ID') 
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

bot = telebot.TeleBot(BOT_TOKEN)
L = instaloader.Instaloader(user_agent=USER_AGENT)

# --- ФЕЙКОВЫЙ СЕРВЕР (Для Render) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running via Cookies!"

def run_http():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_http)
    t.start()

# --- НАСТРОЙКА INSTAGRAM (ЧЕРЕЗ COOKIES) ---
if INSTA_SESSION_ID:
    try:
        print("Настраиваем сессию через Cookie...")
        # Подменяем сессию вручную
        L.context._session.cookies.set('sessionid', INSTA_SESSION_ID)
        L.context._session.headers.update({'User-Agent': USER_AGENT})
        
        # Проверка статуса (не обязательна, но полезна для логов)
        username = L.test_login()
        print(f"Успешно авторизованы как: {username}")
    except Exception as e:
        print(f"Ошибка cookie-авторизации: {e}")
else:
    print("ВНИМАНИЕ: Cookie не найдены! Бот работает в ограниченном режиме.")

DOWNLOAD_FOLDER = "downloads"
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# --- ЛОГИКА PINTEREST ---
def download_pinterest(url, chat_id):
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(url, headers=headers)
        if response.status_code != 200: return None
        soup = BeautifulSoup(response.content, 'html.parser')
        image_tag = soup.find('meta', property='og:image')
        if image_tag:
            img_data = requests.get(image_tag['content']).content
            filename = f"{DOWNLOAD_FOLDER}/pin_{chat_id}.jpg"
            with open(filename, 'wb') as handler: handler.write(img_data)
            return filename
        return None
    except Exception as e:
        print(f"Pinterest Error: {e}")
        return None

# --- ЛОГИКА INSTAGRAM ---
def download_instagram(url, chat_id):
    try:
        shortcode_match = re.search(r'/(p|reel)/([^/?#&]+)', url) 
        if not shortcode_match: return None
        shortcode = shortcode_match.group(2)
        
        # Загружаем пост
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        target_dir = f"{DOWNLOAD_FOLDER}/{chat_id}_insta"
        L.download_post(post, target=target_dir)
        
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                if file.endswith(".jpg"):
                    return os.path.join(root, file)
        return None
    except Exception as e:
        print(f"Instagram Error: {e}")
        # Если ошибка 401/Redirect, значит куки протухли
        return None

# --- ОБРАБОТЧИК ---
@bot.message_handler(content_types=['text'])
def handle_message(message):
    url = message.text
    chat_id = message.chat.id
    
    if "pinterest.com" in url or "pin.it" in url:
        bot.send_message(chat_id, "Pinterest: качаю...")
        path = download_pinterest(url, chat_id)
        if path:
            with open(path, 'rb') as f: bot.send_photo(chat_id, f)
            os.remove(path)
        else:
            bot.send_message(chat_id, "Ошибка Pinterest.")

    elif "instagram.com" in url:
        bot.send_message(chat_id, "Instagram: качаю...")
        path = download_instagram(url, chat_id)
        if path:
            with open(path, 'rb') as f: bot.send_photo(chat_id, f)
            shutil.rmtree(os.path.dirname(path))
        else:
            bot.send_message(chat_id, "Не удалось скачать. Проверьте ссылку или куки бота.")
    else:
        bot.send_message(chat_id, "Жду ссылку...")

if __name__ == '__main__':
    keep_alive()
    bot.infinity_polling()
