import telebot
import os
import requests
from bs4 import BeautifulSoup
import instaloader
import re
import shutil
import http.cookiejar
from flask import Flask
from threading import Thread

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
COOKIE_FILE = 'cookies.txt'

bot = telebot.TeleBot(BOT_TOKEN)
L = instaloader.Instaloader(user_agent=USER_AGENT)

# --- FLASK СЕРВЕР ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running with cookies.txt!", 200

@app.route("/health")
def health():
    return {"status": "healthy"}, 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- НАСТРОЙКА INSTAGRAM ЧЕРЕЗ COOKIES.TXT ---
if os.path.exists(COOKIE_FILE):
    try:
        print(f"Загружаем сессию из {COOKIE_FILE}...")
        cj = http.cookiejar.MozillaCookieJar(COOKIE_FILE)
        cj.load(ignore_discard=True, ignore_expires=True)
        L.context._session.cookies.update(cj)
        L.context._session.headers.update({'User-Agent': USER_AGENT})
        
        # Проверка логина (может кинуть ошибку, если куки протухли)
        username = L.test_login()
        if username:
            print(f"Успешная авторизация: {username}")
        else:
            print("Предупреждение: L.test_login() не вернул имя пользователя.")
    except Exception as e:
        print(f"Ошибка при чтении cookies.txt: {e}")
else:
    print(f"ВНИМАНИЕ: Файл {COOKIE_FILE} не найден в репозитории!")

DOWNLOAD_FOLDER = "downloads"
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# --- ЛОГИКА ЗАГРУЗКИ ---
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

def download_instagram(url, chat_id):
    try:
        # Извлекаем шорткод из ссылки
        shortcode_match = re.search(r'/(p|reel|tv)/([^/?#&]+)', url) 
        if not shortcode_match: return None
        shortcode = shortcode_match.group(2)
        
        # Получаем данные поста без скачивания файлов на диск
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        # Если это видео, можно взять post.video_url, но для фото берем post.url
        return post.url
    except Exception as e:
        print(f"Instagram Error: {e}")
        return None

# --- ОБРАБОТЧИК СООБЩЕНИЙ ---
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
        bot.send_message(chat_id, "Instagram: обрабатываю ссылку...")
        insta_url = download_instagram(url, chat_id)
        if insta_url:
            try:
                # Отправляем фото напрямую по URL, Telegram сам его загрузит
                bot.send_photo(chat_id, insta_url)
            except Exception as e:
                bot.send_message(chat_id, f"Ошибка при отправке фото: {e}")
        else:
            bot.send_message(chat_id, "Не удалось получить контент. Возможно, куки устарели.")
    else:
        bot.send_message(chat_id, "Отправьте ссылку на Instagram или Pinterest.")

# --- ЗАПУСК ---
if __name__ == '__main__':
    Thread(target=run_flask, daemon=True).start()
    print("Бот запущен с использованием cookies.txt...")
    bot.infinity_polling()
