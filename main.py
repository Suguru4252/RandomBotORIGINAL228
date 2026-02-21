import telebot
import sqlite3
import random
import os
from datetime import datetime, timedelta
from telebot import types
import threading
import time

TOKEN = "7952669809:AAFzRKgUPcNYn9lkOC5EWdGLB7oEqyWeczY"
bot = telebot.TeleBot(TOKEN)
CURRENCY = "💰 SuguruCoins"

# ========== БАЗА ДАННЫХ ==========
DB_PATH = 'bot.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            custom_name TEXT UNIQUE,
            balance INTEGER DEFAULT 0,
            exp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            work_count INTEGER DEFAULT 0,
            total_earned INTEGER DEFAULT 0,
            last_daily TEXT,
            warns INTEGER DEFAULT 0,
            banned_until TEXT,
            equipped_clothes INTEGER DEFAULT NULL,
            current_city TEXT DEFAULT 'Москва',
            has_car INTEGER DEFAULT 0,
            has_plane INTEGER DEFAULT 0,
            has_house INTEGER DEFAULT 0,
            owned_house_id INTEGER DEFAULT NULL,
            house_purchase_price INTEGER DEFAULT 0,
            house_purchase_city TEXT DEFAULT NULL,
            closet_slots INTEGER DEFAULT 5,
            next_slot_price INTEGER DEFAULT 100000000,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name TEXT UNIQUE,
            min_exp INTEGER,
            min_reward INTEGER,
            max_reward INTEGER,
            exp_reward INTEGER,
            emoji TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS businesses (
            user_id INTEGER PRIMARY KEY,
            business_name TEXT,
            level INTEGER DEFAULT 1,
            raw_material INTEGER DEFAULT 0,
            raw_in_delivery INTEGER DEFAULT 0,
            raw_spent INTEGER DEFAULT 0,
            total_invested INTEGER DEFAULT 0,
            stored_profit INTEGER DEFAULT 0,
            last_update TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            end_time TEXT,
            delivered INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS business_data (
            name TEXT PRIMARY KEY,
            price INTEGER,
            emoji TEXT,
            raw_cost_per_unit INTEGER,
            profit_per_raw INTEGER,
            base_time INTEGER,
            photo_url TEXT,
            description TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_clothes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            photo_url TEXT NOT NULL,
            in_shop INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_clothes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            clothes_id INTEGER,
            equipped INTEGER DEFAULT 0,
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            photo_url TEXT NOT NULL,
            speed INTEGER DEFAULT 100,
            in_shop INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            car_id INTEGER,
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_planes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            photo_url TEXT NOT NULL,
            speed INTEGER DEFAULT 500,
            in_shop INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_planes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            plane_id INTEGER,
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_houses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            photo_url TEXT NOT NULL,
            comfort INTEGER DEFAULT 10,
            in_shop INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT,
            shop_type TEXT DEFAULT 'clothes',
            has_clothes_shop INTEGER DEFAULT 0,
            has_car_shop INTEGER DEFAULT 0,
            has_plane_shop INTEGER DEFAULT 0,
            has_house_shop INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS travels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            from_city TEXT,
            to_city TEXT,
            transport TEXT,
            end_time TEXT,
            completed INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            level INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bans (
            user_id INTEGER PRIMARY KEY,
            reason TEXT,
            until REAL,
            banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warns (
            user_id INTEGER PRIMARY KEY,
            count INTEGER DEFAULT 0,
            last_warn TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roulette_stats (
            user_id INTEGER PRIMARY KEY,
            games_played INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            total_bet INTEGER DEFAULT 0,
            total_win INTEGER DEFAULT 0,
            total_lose INTEGER DEFAULT 0,
            biggest_win INTEGER DEFAULT 0,
            biggest_lose INTEGER DEFAULT 0,
            last_game TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS work_stats (
            user_id INTEGER,
            job_type TEXT,
            games_played INTEGER DEFAULT 0,
            perfect_games INTEGER DEFAULT 0,
            best_time REAL,
            total_earned INTEGER DEFAULT 0,
            avg_score INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, job_type)
        )
    ''')
    
    cursor.execute('INSERT OR IGNORE INTO admins (user_id, level) VALUES (?, ?)', (5596589260, 4))
    
    cursor.execute('SELECT COUNT(*) FROM cities')
    if cursor.fetchone()[0] == 0:
        cities_data = [
            ("Москва", "Столица! Отличное место для старта", 'clothes', 1, 0, 0, 0),
            ("Село Молочное", "Уютное село, тут продают машины", 'cars', 0, 1, 0, 0),
            ("Кропоткин", "Промышленный город, здесь можно купить самолет", 'planes', 0, 0, 1, 0),
            ("Мурино", "Молодежный район, много новых домов", 'houses', 0, 0, 0, 1)
        ]
        cursor.executemany('''
            INSERT INTO cities (name, description, shop_type, has_clothes_shop, has_car_shop, has_plane_shop, has_house_shop)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', cities_data)
    
    cursor.execute('SELECT COUNT(*) FROM shop_clothes')
    if cursor.fetchone()[0] == 0:
        clothes_data = [
            ("Любит_поспать", 160000000, "https://iimg.su/i/DeILfi"),
            ("БоссFKC", 700000000, "https://iimg.su/i/mZUtyC"),
            ("Фермер", 400000000, "https://iimg.su/i/1ChPnG"),
            ("Крутой", 100000000, "https://iimg.su/i/RqexQt"),
            ("Шалун", 150000000, "https://iimg.su/i/He6eQH"),
            ("Пепе", 350000000, "https://iimg.su/i/eQKrdn"),
            ("С_улицы", 70000000, "https://iimg.su/i/Jn88sT"),
            ("Спринг_бонни", 700000000, "https://iimg.su/i/wOy6tw"),
            ("Качок", 400000000, "https://iimg.su/i/XI1uhf"),
            ("Платье", 80000000, "https://iimg.su/i/UBQvJy"),
            ("Скелет", 666666666666, "https://iimg.su/i/RnLRY8"),
            ("Гангстер", 250000000, "https://iimg.su/i/dk8sE2"),
            ("Тяги", 67000000, "https://iimg.su/i/sQ6ns5"),
            ("Модный", 20000000, "https://iimg.su/i/8UkPmY"),
            ("Романтик2.0", 100000000, "https://iimg.su/i/qryc9I"),
            ("Романтик", 50000000, "https://iimg.su/i/8l70sn")
        ]
        cursor.executemany('''
            INSERT INTO shop_clothes (name, price, photo_url)
            VALUES (?, ?, ?)
        ''', clothes_data)
    
    cursor.execute('SELECT COUNT(*) FROM shop_cars')
    if cursor.fetchone()[0] == 0:
        cars_data = [
            ("Развалюха", 10000000, "https://iimg.su/i/kqaEfh", 30),
            ("Жигули", 50000000, "https://iimg.su/i/C53UkD", 50),
            ("Ауди", 50000000, "https://iimg.su/i/v5CjqO", 55),
            ("Хендай", 300000000, "https://iimg.su/i/ajQsBS", 80),
            ("Крузак-300", 600000000, "https://iimg.su/i/gwyWEO", 100),
            ("Мерседес-Акула", 777777777, "https://iimg.su/i/CSVixs", 120),
            ("БЭМЭВЭ", 1000000000, "https://iimg.su/i/F2Jfb4", 150),
            ("Мерседес-ГелентВаген", 1000000000, "https://iimg.su/i/Lsmr1y", 140),
            ("РолсРойс", 7777777777, "https://iimg.su/i/T8Uji6", 200)
        ]
        cursor.executemany('''
            INSERT INTO shop_cars (name, price, photo_url, speed)
            VALUES (?, ?, ?, ?)
        ''', cars_data)
    
    cursor.execute('SELECT COUNT(*) FROM shop_planes')
    if cursor.fetchone()[0] == 0:
        planes_data = [
            ("Свалка", 50000000, "https://iimg.su/i/EjWevF", 200),
            ("Как у бабушки", 100000000, "https://iimg.su/i/AfRIlY", 250),
            ("Тестная халупа", 200000000, "https://iimg.su/i/icWz0I", 300),
            ("Домик", 500000000, "https://iimg.su/i/YiNOvU", 400),
            ("Красивый дом", 1000000000, "https://iimg.su/i/UtiAP3", 500),
            ("Дом2", 2000000000, "https://iimg.su/i/yxkgAD", 600),
            ("Замок", 5000000000, "https://iimg.su/i/3V4lup", 700),
            ("Особняк", 10000000000, "https://iimg.su/i/jthfeq", 800),
            ("Мэрия", 20000000000, "https://iimg.su/i/xVVHLe", 900)
        ]
        cursor.executemany('''
            INSERT INTO shop_planes (name, price, photo_url, speed)
            VALUES (?, ?, ?, ?)
        ''', planes_data)
    
    cursor.execute('SELECT COUNT(*) FROM shop_houses')
    if cursor.fetchone()[0] == 0:
        houses_data = [
            ("Свалка", 50000000, "https://iimg.su/i/EjWevF", 10),
            ("Как у бабушки", 100000000, "https://iimg.su/i/AfRIlY", 20),
            ("Тестная халупа", 200000000, "https://iimg.su/i/icWz0I", 30),
            ("Домик", 500000000, "https://iimg.su/i/YiNOvU", 40),
            ("Красивый дом", 1000000000, "https://iimg.su/i/UtiAP3", 50),
            ("Дом2", 2000000000, "https://iimg.su/i/yxkgAD", 60),
            ("Замок", 5000000000, "https://iimg.su/i/3V4lup", 70),
            ("Особняк", 10000000000, "https://iimg.su/i/jthfeq", 80),
            ("Мэрия", 20000000000, "https://iimg.su/i/xVVHLe", 90)
        ]
        cursor.executemany('''
            INSERT INTO shop_houses (name, price, photo_url, comfort)
            VALUES (?, ?, ?, ?)
        ''', houses_data)
    
    businesses_data = [
        ("🥤 Киоск", 500000, "🥤", 1000, 2000, 60, "https://example.com/kiosk.jpg", "Маленький киоск"),
        ("🍔 Фастфуд", 5000000, "🍔", 2500, 5000, 60, "https://example.com/fastfood.jpg", "Бургерная"),
        ("🏪 Минимаркет", 15000000, "🏪", 30000, 60000, 60, "https://example.com/market.jpg", "Магазин"),
        ("⛽ Заправка", 50000000, "⛽", 200000, 400000, 60, "https://example.com/gas.jpg", "АЗС"),
        ("🏨 Отель", 1000000000, "🏨", 1000000, 2000000, 120, "https://example.com/hotel.jpg", "Отель")
    ]
    
    for bd in businesses_data:
        cursor.execute('''
            INSERT OR REPLACE INTO business_data (name, price, emoji, raw_cost_per_unit, profit_per_raw, base_time, photo_url, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', bd)
    
    jobs_data = [
        ("🚚 Грузчик", 0, 5000, 15000, 20, "🚚"),
        ("🧹 Уборщик", 50, 7000, 17000, 25, "🧹"),
        ("📦 Курьер", 150, 10000, 20000, 30, "📦"),
        ("🔧 Механик", 300, 20000, 50000, 35, "🔧"),
        ("💻 Программист", 500, 50000, 100000, 40, "💻"),
        ("🕵️ Детектив", 800, 70000, 120000, 45, "🕵️"),
        ("👨‍🔧 Инженер", 1200, 100000, 150000, 50, "👨‍🔧"),
        ("👨‍⚕️ Врач", 1700, 200000, 350000, 60, "👨‍⚕️"),
        ("👨‍🎤 Артист", 2300, 250000, 370000, 65, "👨‍🎤"),
        ("👨‍🚀 Космонавт", 3000, 500000, 1000000, 80, "👨‍🚀")
    ]
    
    for job in jobs_data:
        cursor.execute('''
            INSERT OR REPLACE INTO jobs (job_name, min_exp, min_reward, max_reward, exp_reward, emoji)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', job)
    
    conn.commit()
    conn.close()
    print("✅ База данных создана!")

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
ADMINS = {}
BANS = {}
WARNS = {}
MAX_WARNS = 3
job_cooldowns = {}
loader_games = {}
cleaner_games = {}
courier_games = {}
mechanic_games = {}
programmer_games = {}
detective_games = {}
engineer_games = {}
doctor_games = {}
artist_games = {}
cosmonaut_games = {}

# ========== ФУНКЦИИ ==========
def add_balance(user_id, amount):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?', 
                      (amount, max(0, amount), user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка add_balance: {e}")
        return False

def get_balance(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else 0
    except:
        return 0

def add_exp(user_id, amount):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT exp, level FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        current_exp = result[0] if result else 0
        current_level = result[1] if result else 1
        
        new_exp = current_exp + amount
        new_level = new_exp // 100 + 1
        
        cursor.execute('UPDATE users SET exp = ?, level = ? WHERE user_id = ?', (new_exp, new_level, user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка add_exp: {e}")
        return False

def get_user_stats(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT exp, level, work_count, total_earned FROM users WHERE user_id = ?', (user_id,))
        res = cursor.fetchone()
        conn.close()
        return res if res else (0, 1, 0, 0)
    except:
        return (0, 1, 0, 0)

def get_user_profile(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    except:
        return None

def get_user_city(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT current_city FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else "Москва"
    except:
        return "Москва"

def get_city_info(city_name):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM cities WHERE name = ?', (city_name,))
        city = cursor.fetchone()
        conn.close()
        return city
    except:
        return None

def get_user_car(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        car = cursor.execute('''
            SELECT sc.* FROM shop_cars sc
            JOIN user_cars uc ON sc.id = uc.car_id
            WHERE uc.user_id = ?
        ''', (user_id,)).fetchone()
        conn.close()
        return car
    except:
        return None

def get_user_plane(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        plane = cursor.execute('''
            SELECT sp.* FROM shop_planes sp
            JOIN user_planes up ON sp.id = up.plane_id
            WHERE up.user_id = ?
        ''', (user_id,)).fetchone()
        conn.close()
        return plane
    except:
        return None

def get_user_house(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        user = cursor.execute('SELECT owned_house_id, house_purchase_price, house_purchase_city FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if not user or not user['owned_house_id']:
            conn.close()
            return None
        
        house = cursor.execute('SELECT * FROM shop_houses WHERE id = ?', (user['owned_house_id'],)).fetchone()
        conn.close()
        return {'house': house, 'price': user['house_purchase_price'], 'city': user['house_purchase_city']}
    except:
        return None

def get_user_equipped_clothes(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT sc.* FROM shop_clothes sc
            JOIN user_clothes uc ON sc.id = uc.clothes_id
            WHERE uc.user_id = ? AND uc.equipped = 1
        ''', (user_id,))
        clothes = cursor.fetchone()
        conn.close()
        return clothes
    except:
        return None

def get_user_profile_photo(user_id):
    equipped = get_user_equipped_clothes(user_id)
    if equipped and equipped['photo_url']:
        return equipped['photo_url']
    return "https://iimg.su/i/waxabI"

def main_keyboard_for_city(user_id):
    current_city = get_user_city(user_id)
    city_info = get_city_info(current_city)
    shop_type = city_info['shop_type'] if city_info else 'clothes'
    
    shop_buttons = {
        'clothes': "👕 Магазин одежды",
        'cars': "🚗 Магазин машин", 
        'planes': "✈️ Магазин самолетов",
        'houses': "🏠 Магазин домов"
    }
    shop_button = shop_buttons.get(shop_type, "🛍️ Магазин")
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(
        types.KeyboardButton("💼 Работы"),
        types.KeyboardButton("🏭 Бизнесы")
    )
    markup.row(
        types.KeyboardButton(shop_button),
        types.KeyboardButton("🎁 Ежедневно")
    )
    markup.row(
        types.KeyboardButton("🗺️ Карта"),
        types.KeyboardButton("🏠 Мой дом")
    )
    markup.row(
        types.KeyboardButton("⚙️ Настройки"),
        types.KeyboardButton("🔄")
    )
    return markup

def send_main_menu_with_profile(user_id, chat_id=None):
    if not chat_id:
        chat_id = user_id
    
    user_data = get_user_profile(user_id)
    if not user_data:
        return
    
    balance = get_balance(user_id)
    display_name = user_data[3] if user_data[3] else (user_data[2] if user_data[2] else "Игрок")
    current_city = get_user_city(user_id)
    
    caption = f"👤 *{display_name}*\n\n💰 Баланс: {balance:,} {CURRENCY}\n📍 Город: {current_city}"
    
    photo_url = get_user_profile_photo(user_id)
    
    bot.send_photo(
        chat_id,
        photo_url,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=main_keyboard_for_city(user_id)
    )

def set_custom_name(user_id, name):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET custom_name = ? WHERE user_id = ?', (name, user_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def get_user_business(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM businesses WHERE user_id = ?', (user_id,))
        business = cursor.fetchone()
        conn.close()
        return business
    except:
        return None

def get_business_data(business_name):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM business_data WHERE name = ?', (business_name,))
        data = cursor.fetchone()
        conn.close()
        return data
    except:
        return None

def check_cooldown(user_id, job_name):
    key = f"{user_id}_{job_name}"
    if key in job_cooldowns:
        last_time = job_cooldowns[key]
        if time.time() - last_time < 7:
            remaining = 7 - (time.time() - last_time)
            return False, round(remaining, 1)
    return True, 0

def set_cooldown(user_id, job_name):
    key = f"{user_id}_{job_name}"
    job_cooldowns[key] = time.time()

# ========== КЛАВИАТУРЫ ==========
def jobs_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    jobs = ["🚚 Грузчик", "🧹 Уборщик", "📦 Курьер", "🔧 Механик", "💻 Программист", 
            "🕵️ Детектив", "👨‍🔧 Инженер", "👨‍⚕️ Врач", "👨‍🎤 Артист", "👨‍🚀 Космонавт"]
    for job in jobs:
        markup.add(types.KeyboardButton(job))
    markup.row(types.KeyboardButton("🔙 Назад"))
    return markup

def businesses_main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(
        types.KeyboardButton("📊 Мой бизнес"),
        types.KeyboardButton("💰 Собрать прибыль")
    )
    markup.row(
        types.KeyboardButton("📦 Закупить на всё"),
        types.KeyboardButton("🏪 Купить бизнес")
    )
    markup.row(types.KeyboardButton("🔙 Назад"))
    return markup

def cities_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(
        types.KeyboardButton("🏙️ Москва"),
        types.KeyboardButton("🏙️ Село Молочное")
    )
    markup.row(
        types.KeyboardButton("🏙️ Кропоткин"),
        types.KeyboardButton("🏙️ Мурино")
    )
    markup.row(types.KeyboardButton("🔙 Назад"))
    return markup

def settings_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(types.KeyboardButton("✏️ Сменить никнейм"))
    markup.row(types.KeyboardButton("🔙 Назад"))
    return markup

# ========== СТАРТ ==========
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    first_name = message.from_user.first_name
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, balance, exp, level, work_count, total_earned, current_city)
            VALUES (?, ?, ?, 0, 0, 1, 0, 0, 'Москва')
        ''', (user_id, username, first_name))
        conn.commit()
        conn.close()
        
        welcome_text = f"🌟 **ДОБРО ПОЖАЛОВАТЬ!** 🌟\n\n👋 {first_name}, выбирай никнейм!"
        bot.send_message(user_id, welcome_text, parse_mode="Markdown")
        
        markup = types.ForceReply(selective=True)
        msg = bot.send_message(user_id, "🔤 **Напиши никнейм:**", parse_mode="Markdown", reply_markup=markup)
        bot.register_next_step_handler(msg, process_name_step)
    else:
        conn.close()
        bot.send_message(user_id, f"👋 С возвращением, {first_name}!")
        send_main_menu_with_profile(user_id)

def process_name_step(message):
    user_id = message.from_user.id
    custom_name = message.text.strip()
    
    if set_custom_name(user_id, custom_name):
        bot.send_message(user_id, f"✅ Никнейм `{custom_name}` сохранен!", parse_mode="Markdown")
        send_main_menu_with_profile(user_id)
    else:
        bot.send_message(user_id, "❌ Ошибка. Попробуй /start")

# ========== ОСНОВНОЙ ОБРАБОТЧИК ==========
@bot.message_handler(func=lambda message: True)
def handle(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "💼 Работы":
        bot.send_message(user_id, "🔨 Выбери работу:", reply_markup=jobs_keyboard(user_id))
    
    elif text == "🏭 Бизнесы":
        bot.send_message(user_id, "🏪 Управление бизнесом:", reply_markup=businesses_main_keyboard())
    
    elif text in ["👕 Магазин одежды", "🚗 Магазин машин", "✈️ Магазин самолетов", "🏠 Магазин домов"]:
        current_city = get_user_city(user_id)
        city_info = get_city_info(current_city)
        
        if not city_info:
            bot.send_message(user_id, "❌ Ошибка")
            return
        
        shop_type = city_info['shop_type']
        
        if shop_type == 'clothes':
            bot.send_message(user_id, "👕 Магазин одежды (в разработке)")
        elif shop_type == 'cars':
            bot.send_message(user_id, "🚗 Магазин машин (в разработке)")
        elif shop_type == 'planes':
            bot.send_message(user_id, "✈️ Магазин самолетов (в разработке)")
        elif shop_type == 'houses':
            bot.send_message(user_id, "🏠 Магазин домов (в разработке)")
    
    elif text == "🎁 Ежедневно":
        bonus = random.randint(500, 2000)
        bonus_exp = random.randint(50, 200)
        add_balance(user_id, bonus)
        add_exp(user_id, bonus_exp)
        bot.send_message(user_id, f"🎁 Бонус: +{bonus} {CURRENCY} и +{bonus_exp}⭐!")
    
    elif text == "🗺️ Карта":
        bot.send_message(user_id, "🗺️ **КАРТА**\n\n🏙️ Москва - 👕 Одежда\n🏙️ Село Молочное - 🚗 Машины\n🏙️ Кропоткин - ✈️ Самолеты\n🏙️ Мурино - 🏠 Дома", 
                        parse_mode="Markdown", reply_markup=cities_keyboard())
    
    elif text == "🏠 Мой дом":
        house_data = get_user_house(user_id)
        if not house_data:
            bot.send_message(user_id, "🏠 У тебя нет дома! Купи в Мурино.")
        else:
            house = house_data['house']
            msg = f"🏠 **{house['name']}**\n\n💰 Куплен за: {house_data['price']:,} {CURRENCY}\n📍 Город: {house_data['city']}"
            bot.send_message(user_id, msg, parse_mode="Markdown")
    
    elif text == "⚙️ Настройки":
        bot.send_message(user_id, "⚙️ Настройки", reply_markup=settings_keyboard())
    
    elif text == "🔄":
        send_main_menu_with_profile(user_id)
    
    elif text == "🔙 Назад":
        send_main_menu_with_profile(user_id)
    
    elif text in ["🏙️ Москва", "🏙️ Село Молочное", "🏙️ Кропоткин", "🏙️ Мурино"]:
        city_name = text.replace("🏙️ ", "")
        current_city = get_user_city(user_id)
        
        if city_name == current_city:
            bot.send_message(user_id, f"🏙️ Ты уже в {city_name}")
        else:
            bot.send_message(user_id, f"🚀 Путешествие в {city_name}... (в разработке)")
    
    elif any(job in text for job in ["🚚 Грузчик", "🧹 Уборщик", "📦 Курьер", "🔧 Механик", "💻 Программист", "🕵️ Детектив", "👨‍🔧 Инженер", "👨‍⚕️ Врач", "👨‍🎤 Артист", "👨‍🚀 Космонавт"]):
        ok, rem = check_cooldown(user_id, text)
        if not ok:
            bot.send_message(user_id, f"⏳ Подожди еще {rem} сек!")
            return
        
        earn = random.randint(5000, 15000)
        exp_gain = 20
        add_balance(user_id, earn)
        add_exp(user_id, exp_gain)
        set_cooldown(user_id, text)
        bot.send_message(user_id, f"✅ {text}\n💰 +{earn} {CURRENCY}\n⭐ +{exp_exp}")
    
    elif text == "📊 Мой бизнес":
        business = get_user_business(user_id)
        if not business:
            bot.send_message(user_id, "📭 У тебя нет бизнеса!")
        else:
            msg = f"{business['business_name']}\nУровень: {business['level']}\nСырье: {business['raw_material']}"
            bot.send_message(user_id, msg)
    
    elif text == "💰 Собрать прибыль":
        business = get_user_business(user_id)
        if not business:
            bot.send_message(user_id, "📭 У тебя нет бизнеса!")
        elif business['stored_profit'] <= 0:
            bot.send_message(user_id, "❌ Нет прибыли!")
        else:
            profit = business['stored_profit']
            add_balance(user_id, profit)
            bot.send_message(user_id, f"✅ Собрано {profit:,} {CURRENCY}!")
    
    elif text == "📦 Закупить на всё":
        bot.send_message(user_id, "📦 Закупка сырья (в разработке)")
    
    elif text == "🏪 Купить бизнес":
        bot.send_message(user_id, "🏪 Выбор бизнеса (в разработке)")
    
    elif text == "✏️ Сменить никнейм":
        bot.send_message(user_id, "✏️ Введи новый никнейм:")
        bot.register_next_step_handler(message, process_name_step)

# ========== ЗАПУСК ==========
init_db()
print("✅ Бот запущен!")
print("🎮 SuguruCoins Bot готов к работе!")
bot.infinity_polling()
