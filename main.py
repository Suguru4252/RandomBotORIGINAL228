import telebot
import sqlite3
import random
import os
from datetime import datetime, timedelta
from telebot import types
import threading
import time
import re

TOKEN = os.environ['TOKEN']
bot = telebot.TeleBot(TOKEN)
CURRENCY = "💰 SuguruCoins"

# ========== ПУТЬ К БАЗЕ ДАННЫХ ==========
POSSIBLE_PATHS = [
    '/data/bot.db',
    '/storage/bot.db',
    '/opt/render/project/src/data/bot.db',
    './bot.db'
]

DB_PATH = None
for path in POSSIBLE_PATHS:
    try:
        dir_path = os.path.dirname(path)
        if os.path.exists(dir_path) and os.access(dir_path, os.W_OK):
            DB_PATH = path
            print(f"✅ База будет храниться в: {DB_PATH}")
            break
    except:
        continue

if DB_PATH is None:
    DB_PATH = 'bot.db'
    print("⚠️ Постоянное хранилище не найдено, использую локальную БД")

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
ADMINS = {}
BANS = {}
WARNS = {}
MAX_WARNS = 3

# Хранилища для игр
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
job_cooldowns = {}

# ========== БАЗА ДАННЫХ ==========
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
    
    # ========== ТАБЛИЦЫ ДЛЯ МАГАЗИНА ОДЕЖДЫ ==========
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
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (clothes_id) REFERENCES shop_clothes(id)
        )
    ''')
    
    # ========== НОВЫЕ ТАБЛИЦЫ ДЛЯ МАГАЗИНА МАШИН ==========
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
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (car_id) REFERENCES shop_cars(id)
        )
    ''')
    
    # ========== НОВЫЕ ТАБЛИЦЫ ДЛЯ МАГАЗИНА САМОЛЕТОВ ==========
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
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (plane_id) REFERENCES shop_planes(id)
        )
    ''')
    
    # ========== НОВЫЕ ТАБЛИЦЫ ДЛЯ МАГАЗИНА ДОМОВ ==========
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
    
    # ========== ТАБЛИЦЫ ДЛЯ ГОРОДОВ ==========
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
    
    # ========== ТАБЛИЦЫ ДЛЯ АДМИНОВ, БАНОВ И ВАРНОВ ==========
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
    
    # ========== ТАБЛИЦА ДЛЯ СТАТИСТИКИ РУЛЕТКИ ==========
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
    
    # ========== ТАБЛИЦА ДЛЯ СТАТИСТИКИ МИНИ-ИГР ==========
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
    
    # Добавляем главного админа
    cursor.execute('INSERT OR IGNORE INTO admins (user_id, level) VALUES (?, ?)', (5596589260, 4))
    
    # Заполняем города
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
    
    # Заполняем магазин одеждой
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
    
    # Заполняем магазин машин
    cursor.execute('SELECT COUNT(*) FROM shop_cars')
    if cursor.fetchone()[0] == 0:
        cars_data = [
            ("Развалюха", 10_000_000, "https://iimg.su/i/kqaEfh", 30),
            ("Жигули", 50_000_000, "https://iimg.su/i/C53UkD", 50),
            ("Ауди", 50_000_000, "https://iimg.su/i/v5CjqO", 55),
            ("Хендай", 300_000_000, "https://iimg.su/i/ajQsBS", 80),
            ("Крузак-300", 600_000_000, "https://iimg.su/i/gwyWEO", 100),
            ("Мерседес-Акула", 777_777_777, "https://iimg.su/i/CSVixs", 120),
            ("БЭМЭВЭ", 1_000_000_000, "https://iimg.su/i/F2Jfb4", 150),
            ("Мерседес-ГелентВаген", 1_000_000_000, "https://iimg.su/i/Lsmr1y", 140),
            ("РолсРойс", 7_777_777_777, "https://iimg.su/i/T8Uji6", 200)
        ]
        cursor.executemany('''
            INSERT INTO shop_cars (name, price, photo_url, speed)
            VALUES (?, ?, ?, ?)
        ''', cars_data)
    
    # Заполняем магазин самолетов
    cursor.execute('SELECT COUNT(*) FROM shop_planes')
    if cursor.fetchone()[0] == 0:
        planes_data = [
            ("Свалка", 50_000_000, "https://iimg.su/i/EjWevF", 200),
            ("Как у бабушки", 100_000_000, "https://iimg.su/i/AfRIlY", 250),
            ("Тестная халупа", 200_000_000, "https://iimg.su/i/icWz0I", 300),
            ("Домик", 500_000_000, "https://iimg.su/i/YiNOvU", 400),
            ("Красивый дом", 1_000_000_000, "https://iimg.su/i/UtiAP3", 500),
            ("Дом2", 2_000_000_000, "https://iimg.su/i/yxkgAD", 600),
            ("Замок", 5_000_000_000, "https://iimg.su/i/3V4lup", 700),
            ("Особняк", 10_000_000_000, "https://iimg.su/i/jthfeq", 800),
            ("Мэрия", 20_000_000_000, "https://iimg.su/i/xVVHLe", 900)
        ]
        cursor.executemany('''
            INSERT INTO shop_planes (name, price, photo_url, speed)
            VALUES (?, ?, ?, ?)
        ''', planes_data)
    
    # Заполняем магазин домов
    cursor.execute('SELECT COUNT(*) FROM shop_houses')
    if cursor.fetchone()[0] == 0:
        houses_data = [
            ("Свалка", 50_000_000, "https://iimg.su/i/EjWevF", 10),
            ("Как у бабушки", 100_000_000, "https://iimg.su/i/AfRIlY", 20),
            ("Тестная халупа", 200_000_000, "https://iimg.su/i/icWz0I", 30),
            ("Домик", 500_000_000, "https://iimg.su/i/YiNOvU", 40),
            ("Красивый дом", 1_000_000_000, "https://iimg.su/i/UtiAP3", 50),
            ("Дом2", 2_000_000_000, "https://iimg.su/i/yxkgAD", 60),
            ("Замок", 5_000_000_000, "https://iimg.su/i/3V4lup", 70),
            ("Особняк", 10_000_000_000, "https://iimg.su/i/jthfeq", 80),
            ("Мэрия", 20_000_000_000, "https://iimg.su/i/xVVHLe", 90)
        ]
        cursor.executemany('''
            INSERT INTO shop_houses (name, price, photo_url, comfort)
            VALUES (?, ?, ?, ?)
        ''', houses_data)
    
    # Обновляем business_data с фото
    businesses_data = [
        ("🥤 Киоск", 500_000, "🥤", 1_000, 2_000, 60, "https://th.bing.com/th/id/R.4634fab1300b0376abe417c30426a9b7?rik=xcaYMuQThvYHig&riu=http%3a%2f%2fidei-biz.com%2fwp-content%2fuploads%2f2015%2f04%2fkak-otkryt-kiosk.gif&ehk=Vgms8Tfzm6kKm5Me0BE8ByekknYG3Df%2fjHuMD3NjPGM%3d&risl=&pid=ImgRaw&r=0", "Маленький киоск с напитками и снеками"),
        ("🍔 Фастфуд", 5_000_000, "🍔", 2_500, 5_000, 60, "https://tse1.mm.bing.net/th/id/OIP.HEYen4QlXTiaZzGiYuutCQHaEc?cb=defcache2&defcache=1&rs=1&pid=ImgDetMain&o=7&rm=3", "Бургерная с быстрым обслуживанием"),
        ("🏪 Минимаркет", 15_000_000, "🏪", 30_000, 60_000, 60, "https://tse1.mm.bing.net/th/id/OIP.JQQSzTluO8SxcChv5ZrjWAHaE7?cb=defcache2&defcache=1&rs=1&pid=ImgDetMain&o=7&rm=3", "Небольшой магазин у дома"),
        ("⛽ Заправка", 50_000_000, "⛽", 200_000, 400_000, 60, "https://th.bing.com/th/id/R.1b578b96a209d5a4b42fafe640c98c06?rik=fhxZHgYsQRp5Yw&riu=http%3a%2f%2fcdn.motorpage.ru%2fPhotos%2f800%2f213FE.jpg&ehk=kQHdWpflr8ztgGn9DA3XNkz%2fkSj6dzlVhm3%2biuromWk%3d&risl=&pid=ImgRaw&r=0", "Автозаправочная станция"),
        ("🏨 Отель", 1_000_000_000, "🏨", 1_000_000, 2_000_000, 120, "https://tse1.mm.bing.net/th/id/OIP.oa6wkUpT9KjcmuimacYq3gHaE6?cb=defcache2&defcache=1&rs=1&pid=ImgDetMain&o=7&rm=3", "Роскошный отель для богатых клиентов")
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
    print("✅ База данных проверена/создана")

# ========== ЗАГРУЗКА ДАННЫХ ==========
def load_admins_from_db():
    try:
        conn = get_db()
        admins = {a['user_id']:a['level'] for a in conn.execute('SELECT user_id, level FROM admins').fetchall()}
        conn.close()
        return admins or {5596589260:4}
    except: return {5596589260:4}

def load_bans_from_db():
    try:
        conn = get_db()
        bans = {b['user_id']:{'reason':b['reason'],'until':b['until']} for b in conn.execute('SELECT user_id, reason, until FROM bans').fetchall()}
        conn.close()
        return bans
    except: return {}

def load_warns_from_db():
    try:
        conn = get_db()
        warns = {w['user_id']:w['count'] for w in conn.execute('SELECT user_id, count FROM warns').fetchall()}
        conn.close()
        return warns
    except: return {}

init_db()
ADMINS = load_admins_from_db()
BANS = load_bans_from_db()
WARNS = load_warns_from_db()

# ========== ФУНКЦИИ АДМИНОВ ==========
def get_admin_level(user_id):
    if user_id in ADMINS: return ADMINS[user_id]
    try:
        conn = get_db()
        admin = conn.execute('SELECT level FROM admins WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        if admin:
            ADMINS[user_id] = admin['level']
            return admin['level']
    except: pass
    return 0

def is_admin(user_id, required_level=1): return get_admin_level(user_id) >= required_level

def add_admin(user_id, level):
    try:
        conn = get_db()
        if conn.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,)).fetchone():
            conn.close()
            return False, "❌ Уже админ"
        conn.execute('INSERT INTO admins (user_id, level) VALUES (?,?)', (user_id, level))
        conn.commit()
        conn.close()
        ADMINS[user_id] = level
        return True, f"✅ Админ {level} уровня"
    except: return False, "❌ Ошибка"

def remove_admin(user_id):
    try:
        conn = get_db()
        conn.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        if user_id in ADMINS: del ADMINS[user_id]
        return True
    except: return False

def is_banned(user_id):
    if user_id in BANS:
        ban = BANS[user_id]
        if ban['until'] == 0 or datetime.now().timestamp() < ban['until']: return True
        else:
            del BANS[user_id]
            try:
                conn = get_db()
                conn.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
                conn.commit()
                conn.close()
            except: pass
            return False
    try:
        conn = get_db()
        ban = conn.execute('SELECT until FROM bans WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        if ban:
            if ban['until'] == 0 or datetime.now().timestamp() < ban['until']:
                BANS[user_id] = {'reason':'unknown','until':ban['until']}
                return True
            else:
                conn = get_db()
                conn.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
                conn.commit()
                conn.close()
    except: pass
    return False

def add_ban(user_id, hours=0, reason="admin"):
    try:
        conn = get_db()
        until = 0 if hours == 0 else (datetime.now() + timedelta(hours=hours)).timestamp()
        conn.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
        conn.execute('INSERT INTO bans (user_id, reason, until) VALUES (?,?,?)', (user_id, reason, until))
        conn.commit()
        conn.close()
        BANS[user_id] = {'reason':reason,'until':until}
        return True
    except: return False

def remove_ban(user_id):
    try:
        conn = get_db()
        conn.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        if user_id in BANS: del BANS[user_id]
        return True
    except: return False

def add_warn(user_id):
    try:
        current = WARNS.get(user_id, 0) + 1
        conn = get_db()
        conn.execute('INSERT OR REPLACE INTO warns (user_id, count, last_warn) VALUES (?,?,?)', (user_id, current, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        WARNS[user_id] = current
        if current >= MAX_WARNS:
            add_ban(user_id, hours=24*30, reason="warn")
            WARNS[user_id] = 0
            conn = get_db()
            conn.execute('UPDATE warns SET count = 0 WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            return True, "❌ Бан на 30 дней"
        return False, f"⚠️ Варн {current}/{MAX_WARNS}"
    except: return False, "❌ Ошибка"

def get_warns(user_id):
    if user_id in WARNS: return WARNS[user_id]
    try:
        conn = get_db()
        warn = conn.execute('SELECT count FROM warns WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        if warn:
            WARNS[user_id] = warn['count']
            return warn['count']
    except: pass
    return 0

# ========== ОСНОВНЫЕ ФУНКЦИИ ==========
def add_balance(user_id, amount):
    try:
        conn = get_db()
        conn.execute('UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?', (amount, max(0, amount), user_id))
        conn.commit()
        conn.close()
        return True
    except: return False

def get_balance(user_id):
    try:
        conn = get_db()
        res = conn.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        return res[0] if res else 0
    except: return 0

def add_exp(user_id, amount):
    try:
        conn = get_db()
        u = conn.execute('SELECT exp, level FROM users WHERE user_id = ?', (user_id,)).fetchone()
        exp = u[0] if u else 0
        lvl = u[1] if u else 1
        nexp = exp + amount
        nlvl = nexp // 100 + 1
        conn.execute('UPDATE users SET exp = ?, level = ? WHERE user_id = ?', (nexp, nlvl, user_id))
        conn.commit()
        conn.close()
        return True
    except: return False

def get_user_stats(user_id):
    try:
        conn = get_db()
        r = conn.execute('SELECT exp, level, work_count, total_earned FROM users WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        return r if r else (0,1,0,0)
    except: return (0,1,0,0)

def get_user_profile(user_id):
    try:
        conn = get_db()
        u = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        return u
    except: return None

def get_user_by_username(username):
    try:
        conn = get_db()
        u = conn.execute('SELECT user_id, first_name, username, custom_name, warns FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        return u
    except: return None

def get_user_by_custom_name(custom_name):
    try:
        conn = get_db()
        u = conn.execute('SELECT user_id, first_name, username, custom_name, warns FROM users WHERE custom_name = ? COLLATE NOCASE', (custom_name,)).fetchone()
        conn.close()
        return u
    except: return None

def get_user_display_name(user_data):
    if not user_data: return "Игрок"
    custom, username, first = user_data[3], user_data[2], user_data[1]
    if custom: return f"{custom} (@{username})" if username and username != "NoUsername" else custom
    elif username and username != "NoUsername": return f"@{username}"
    elif first: return first
    return "Игрок"

def set_custom_name(user_id, name):
    try:
        conn = get_db()
        conn.execute('UPDATE users SET custom_name = ? WHERE user_id = ?', (name, user_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError: return False
    except: return False

def get_available_jobs(user_id):
    try:
        conn = get_db()
        exp = conn.execute('SELECT exp FROM users WHERE user_id = ?', (user_id,)).fetchone()[0]
        jobs = conn.execute('SELECT job_name, min_exp, min_reward, max_reward, exp_reward, emoji FROM jobs WHERE min_exp <= ? ORDER BY min_exp ASC', (exp,)).fetchall()
        conn.close()
        return jobs
    except: return []

def get_user_business(user_id):
    try:
        conn = get_db()
        b = conn.execute('SELECT * FROM businesses WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        return b
    except: return None

def get_business_data(business_name):
    try:
        conn = get_db()
        d = conn.execute('SELECT * FROM business_data WHERE name = ?', (business_name,)).fetchone()
        conn.close()
        return d
    except: return None

def has_active_delivery(user_id):
    try:
        conn = get_db()
        c = conn.execute('SELECT COUNT(*) as count FROM deliveries WHERE user_id = ? AND delivered = 0', (user_id,)).fetchone()['count']
        conn.close()
        return c > 0
    except: return False

def find_user_by_input(s):
    if s.startswith('@'): return get_user_by_username(s[1:])
    else: return get_user_by_custom_name(s)

def get_user_city(user_id):
    try:
        conn = get_db()
        c = conn.execute('SELECT current_city FROM users WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        return c[0] if c else "Москва"
    except: return "Москва"

def get_city_info(city_name):
    try:
        conn = get_db()
        c = conn.execute('SELECT * FROM cities WHERE name = ?', (city_name,)).fetchone()
        conn.close()
        return c
    except: return None

def get_user_equipped_clothes(user_id):
    try:
        conn = get_db()
        c = conn.execute('SELECT sc.* FROM shop_clothes sc JOIN user_clothes uc ON sc.id = uc.clothes_id WHERE uc.user_id = ? AND uc.equipped = 1', (user_id,)).fetchone()
        conn.close()
        return c
    except: return None

def get_user_profile_photo(user_id):
    c = get_user_equipped_clothes(user_id)
    return c['photo_url'] if c and c['photo_url'] else "https://iimg.su/i/waxabI"

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

# ========== НОВЫЕ ФУНКЦИИ ДЛЯ МАШИН ==========
def get_user_car(user_id):
    try:
        conn = get_db()
        car = conn.execute('''
            SELECT sc.* FROM shop_cars sc
            JOIN user_cars uc ON sc.id = uc.car_id
            WHERE uc.user_id = ?
        ''', (user_id,)).fetchone()
        conn.close()
        return car
    except: return None

def buy_car(user_id, car_id):
    try:
        conn = get_db()
        # Проверяем, есть ли уже машина
        if conn.execute('SELECT id FROM user_cars WHERE user_id = ?', (user_id,)).fetchone():
            conn.close()
            return False, "❌ У тебя уже есть машина! Продай её, чтобы купить новую."
        
        car = conn.execute('SELECT * FROM shop_cars WHERE id = ?', (car_id,)).fetchone()
        if not car: conn.close(); return False, "❌ Машина не найдена"
        
        user = conn.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if not user or user['balance'] < car['price']:
            conn.close()
            return False, f"❌ Недостаточно средств! Нужно {car['price']:,} {CURRENCY}"
        
        conn.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (car['price'], user_id))
        conn.execute('INSERT INTO user_cars (user_id, car_id) VALUES (?,?)', (user_id, car_id))
        conn.execute('UPDATE users SET has_car = 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True, f"✅ Поздравляем! Ты купил {car['name']}!"
    except Exception as e:
        print(f"Ошибка при покупке машины: {e}")
        return False, "❌ Ошибка при покупке"

def sell_car(user_id):
    try:
        conn = get_db()
        car = conn.execute('''
            SELECT sc.* FROM shop_cars sc
            JOIN user_cars uc ON sc.id = uc.car_id
            WHERE uc.user_id = ?
        ''', (user_id,)).fetchone()
        
        if not car:
            conn.close()
            return False, "❌ У тебя нет машины для продажи!"
        
        sell_price = car['price'] // 2
        conn.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (sell_price, user_id))
        conn.execute('DELETE FROM user_cars WHERE user_id = ?', (user_id,))
        conn.execute('UPDATE users SET has_car = 0 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True, f"💰 Ты продал {car['name']} за {sell_price:,} {CURRENCY}!"
    except Exception as e:
        print(f"Ошибка при продаже машины: {e}")
        return False, "❌ Ошибка при продаже"

# ========== НОВЫЕ ФУНКЦИИ ДЛЯ САМОЛЕТОВ ==========
def get_user_plane(user_id):
    try:
        conn = get_db()
        plane = conn.execute('''
            SELECT sp.* FROM shop_planes sp
            JOIN user_planes up ON sp.id = up.plane_id
            WHERE up.user_id = ?
        ''', (user_id,)).fetchone()
        conn.close()
        return plane
    except: return None

def buy_plane(user_id, plane_id):
    try:
        conn = get_db()
        if conn.execute('SELECT id FROM user_planes WHERE user_id = ?', (user_id,)).fetchone():
            conn.close()
            return False, "❌ У тебя уже есть самолет! Продай его, чтобы купить новый."
        
        plane = conn.execute('SELECT * FROM shop_planes WHERE id = ?', (plane_id,)).fetchone()
        if not plane: conn.close(); return False, "❌ Самолет не найден"
        
        user = conn.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if not user or user['balance'] < plane['price']:
            conn.close()
            return False, f"❌ Недостаточно средств! Нужно {plane['price']:,} {CURRENCY}"
        
        conn.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (plane['price'], user_id))
        conn.execute('INSERT INTO user_planes (user_id, plane_id) VALUES (?,?)', (user_id, plane_id))
        conn.execute('UPDATE users SET has_plane = 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True, f"✅ Поздравляем! Ты купил {plane['name']}!"
    except Exception as e:
        print(f"Ошибка при покупке самолета: {e}")
        return False, "❌ Ошибка при покупке"

def sell_plane(user_id):
    try:
        conn = get_db()
        plane = conn.execute('''
            SELECT sp.* FROM shop_planes sp
            JOIN user_planes up ON sp.id = up.plane_id
            WHERE up.user_id = ?
        ''', (user_id,)).fetchone()
        
        if not plane:
            conn.close()
            return False, "❌ У тебя нет самолета для продажи!"
        
        sell_price = plane['price'] // 2
        conn.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (sell_price, user_id))
        conn.execute('DELETE FROM user_planes WHERE user_id = ?', (user_id,))
        conn.execute('UPDATE users SET has_plane = 0 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True, f"💰 Ты продал {plane['name']} за {sell_price:,} {CURRENCY}!"
    except Exception as e:
        print(f"Ошибка при продаже самолета: {e}")
        return False, "❌ Ошибка при продаже"

# ========== НОВЫЕ ФУНКЦИИ ДЛЯ ДОМОВ ==========
def get_user_house(user_id):
    try:
        conn = get_db()
        user = conn.execute('SELECT owned_house_id, house_purchase_price, house_purchase_city FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if not user or not user['owned_house_id']:
            conn.close()
            return None
        
        house = conn.execute('SELECT * FROM shop_houses WHERE id = ?', (user['owned_house_id'],)).fetchone()
        conn.close()
        return {'house': house, 'price': user['house_purchase_price'], 'city': user['house_purchase_city']}
    except: return None

def buy_house(user_id, house_id):
    try:
        conn = get_db()
        user = conn.execute('SELECT owned_house_id, balance FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if user['owned_house_id']:
            conn.close()
            return False, "❌ У тебя уже есть дом! Продай его, чтобы купить новый."
        
        house = conn.execute('SELECT * FROM shop_houses WHERE id = ?', (house_id,)).fetchone()
        if not house: conn.close(); return False, "❌ Дом не найден"
        
        if user['balance'] < house['price']:
            conn.close()
            return False, f"❌ Недостаточно средств! Нужно {house['price']:,} {CURRENCY}"
        
        current_city = get_user_city(user_id)
        
        conn.execute('UPDATE users SET balance = balance - ?, owned_house_id = ?, house_purchase_price = ?, house_purchase_city = ? WHERE user_id = ?', 
                    (house['price'], house_id, house['price'], current_city, user_id))
        conn.execute('UPDATE users SET has_house = 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True, f"✅ Поздравляем! Ты купил {house['name']} в городе {current_city} за {house['price']:,} {CURRENCY}!"
    except Exception as e:
        print(f"Ошибка при покупке дома: {e}")
        return False, "❌ Ошибка при покупке"

def sell_house(user_id):
    try:
        conn = get_db()
        user = conn.execute('SELECT owned_house_id, house_purchase_price FROM users WHERE user_id = ?', (user_id,)).fetchone()
        
        if not user or not user['owned_house_id']:
            conn.close()
            return False, "❌ У тебя нет дома для продажи!"
        
        house = conn.execute('SELECT name FROM shop_houses WHERE id = ?', (user['owned_house_id'],)).fetchone()
        sell_price = user['house_purchase_price'] // 2
        
        conn.execute('UPDATE users SET balance = balance + ?, owned_house_id = NULL, house_purchase_price = 0, house_purchase_city = NULL WHERE user_id = ?', 
                    (sell_price, user_id))
        conn.execute('UPDATE users SET has_house = 0 WHERE user_id = ?', (user_id,))
        # При продаже дома шкаф и одежда остаются, слоты тоже
        conn.commit()
        conn.close()
        return True, f"💰 Ты продал {house['name']} за {sell_price:,} {CURRENCY}!\n🏠 Твой шкаф и одежда сохранены."
    except Exception as e:
        print(f"Ошибка при продаже дома: {e}")
        return False, "❌ Ошибка при продаже"

# ========== НОВЫЕ ФУНКЦИИ ДЛЯ ШКАФА ==========
def get_user_closet(user_id):
    """Возвращает список одежды в шкафу (не надетой)"""
    try:
        conn = get_db()
        clothes = conn.execute('''
            SELECT sc.*, uc.id as user_clothes_id FROM shop_clothes sc
            JOIN user_clothes uc ON sc.id = uc.clothes_id
            WHERE uc.user_id = ? AND uc.equipped = 0
            ORDER BY uc.purchased_at DESC
        ''', (user_id,)).fetchall()
        conn.close()
        return clothes
    except: return []

def get_user_wardrobe_stats(user_id):
    try:
        conn = get_db()
        user = conn.execute('SELECT closet_slots, next_slot_price FROM users WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        return user
    except: return None

def buy_closet_slot(user_id):
    try:
        conn = get_db()
        user = conn.execute('SELECT closet_slots, next_slot_price, balance FROM users WHERE user_id = ?', (user_id,)).fetchone()
        
        if user['balance'] < user['next_slot_price']:
            conn.close()
            return False, f"❌ Недостаточно средств! Нужно {user['next_slot_price']:,} {CURRENCY}"
        
        new_slots = user['closet_slots'] + 1
        new_price = user['next_slot_price'] + 100_000_000
        
        conn.execute('UPDATE users SET balance = balance - ?, closet_slots = ?, next_slot_price = ? WHERE user_id = ?', 
                    (user['next_slot_price'], new_slots, new_price, user_id))
        conn.commit()
        conn.close()
        return True, f"✅ Ты купил новый слот в шкафу! Теперь у тебя {new_slots} слотов."
    except Exception as e:
        print(f"Ошибка при покупке слота: {e}")
        return False, "❌ Ошибка при покупке слота"

def equip_clothes(user_id, user_clothes_id):
    """Надевает одежду из шкафа"""
    try:
        conn = get_db()
        # Сначала снимаем текущую
        conn.execute('UPDATE user_clothes SET equipped = 0 WHERE user_id = ?', (user_id,))
        # Надеваем новую
        conn.execute('UPDATE user_clothes SET equipped = 1 WHERE id = ?', (user_clothes_id,))
        # Обновляем equipped_clothes в users
        clothes = conn.execute('SELECT clothes_id FROM user_clothes WHERE id = ?', (user_clothes_id,)).fetchone()
        if clothes:
            conn.execute('UPDATE users SET equipped_clothes = ? WHERE user_id = ?', (clothes['clothes_id'], user_id))
        conn.commit()
        conn.close()
        return True, "✅ Одежда надета!"
    except Exception as e:
        print(f"Ошибка при надевании: {e}")
        return False, "❌ Ошибка при надевании"

def add_clothes_to_closet(user_id, clothes_id):
    """Добавляет купленную одежду в шкаф, если есть место"""
    try:
        conn = get_db()
        user = conn.execute('SELECT closet_slots FROM users WHERE user_id = ?', (user_id,)).fetchone()
        owned_count = conn.execute('SELECT COUNT(*) as cnt FROM user_clothes WHERE user_id = ?', (user_id,)).fetchone()['cnt']
        
        if owned_count >= user['closet_slots']:
            conn.close()
            return False, "❌ В твоем шкафу нет места! Купи новый слот или продай/надежды старую одежду."
        
        # Добавляем в шкаф (equipped = 0)
        conn.execute('INSERT INTO user_clothes (user_id, clothes_id, equipped) VALUES (?,?,0)', (user_id, clothes_id))
        conn.commit()
        conn.close()
        return True, "✅ Одежда добавлена в шкаф!"
    except Exception as e:
        print(f"Ошибка добавления в шкаф: {e}")
        return False, "❌ Ошибка при добавлении в шкаф"

# ========== ОБНОВЛЕННАЯ ФУНКЦИЯ ПОКУПКИ ОДЕЖДЫ ==========
def buy_clothes(user_id, clothes_id):
    try:
        conn = get_db()
        clothes = conn.execute('SELECT * FROM shop_clothes WHERE id = ?', (clothes_id,)).fetchone()
        if not clothes: conn.close(); return False, "❌ Товар не найден"
        
        user = conn.execute('SELECT balance, closet_slots FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if not user or user['balance'] < clothes['price']:
            conn.close()
            return False, f"❌ Недостаточно средств! Нужно {clothes['price']:,} {CURRENCY}"
        
        # Проверяем наличие дома перед покупкой
        has_house = conn.execute('SELECT owned_house_id FROM users WHERE user_id = ?', (user_id,)).fetchone()['owned_house_id']
        if not has_house:
            conn.close()
            return False, "❌ У тебя нет дома! Купи дом в Мурино, чтобы хранить одежду."
        
        # Проверяем место в шкафу
        owned_count = conn.execute('SELECT COUNT(*) as cnt FROM user_clothes WHERE user_id = ?', (user_id,)).fetchone()['cnt']
        if owned_count >= user['closet_slots']:
            conn.close()
            return False, f"❌ В твоем шкафу нет места! У тебя {user['closet_slots']} слотов. Купи новый слот в доме."
        
        # Снимаем деньги
        conn.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (clothes['price'], user_id))
        
        # Добавляем в шкаф (не надетую)
        conn.execute('INSERT INTO user_clothes (user_id, clothes_id, equipped) VALUES (?,?,0)', (user_id, clothes_id))
        
        conn.commit()
        conn.close()
        return True, f"✅ Ты купил {clothes['name']}! Одежда перемещена в шкаф."
    except Exception as e:
        print(f"Ошибка при покупке: {e}")
        return False, "❌ Ошибка при покупке"

# ========== ФУНКЦИИ ДЛЯ ПУТЕШЕСТВИЙ С УЧЕТОМ ТРАНСПОРТА ==========
def calculate_travel_time(user_id, base_time):
    """Рассчитывает время поездки с учетом транспорта"""
    car = get_user_car(user_id)
    plane = get_user_plane(user_id)
    
    # Если есть самолет, используем его скорость
    if plane:
        speed_multiplier = plane['speed'] / 100  # Базовая скорость 100 = 1.0
        return max(10, int(base_time / speed_multiplier))
    # Если есть машина, используем ее скорость
    elif car:
        speed_multiplier = car['speed'] / 100
        return max(15, int(base_time / speed_multiplier))
    # Если ничего нет, едем на такси
    else:
        return base_time

def start_travel(user_id, to_city, transport):
    try:
        conn = get_db()
        if conn.execute('SELECT id FROM travels WHERE user_id = ? AND completed = 0', (user_id,)).fetchone():
            conn.close()
            return False, "❌ У тебя уже есть активная поездка!"
        
        from_city = get_user_city(user_id)
        base_time = random.randint(30, 60)
        travel_time = calculate_travel_time(user_id, base_time)
        
        end_time = (datetime.now() + timedelta(seconds=travel_time)).isoformat()
        
        conn.execute('INSERT INTO travels (user_id, from_city, to_city, transport, end_time, completed) VALUES (?,?,?,?,?,0)', 
                    (user_id, from_city, to_city, transport, end_time))
        conn.commit()
        conn.close()
        
        transport_emoji = "🚕" if transport == "Такси" else "🚗" if transport == "Личная машина" else "✈️"
        bot.send_message(
            user_id,
            f"{transport_emoji} Ты отправился в {to_city} на {transport}!\n⏱️ Время в пути: {travel_time} сек.\n\n⌛ Ожидай...",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return True, None
    except Exception as e:
        print(f"Ошибка поездки: {e}")
        return False, "❌ Ошибка при начале поездки"

# ========== ФУНКЦИИ ДЛЯ МАГАЗИНОВ (СТРАНИЦЫ) ==========
def get_cars_page(page=0):
    try:
        conn = get_db()
        all = conn.execute('SELECT * FROM shop_cars WHERE in_shop = 1 ORDER BY price').fetchall()
        conn.close()
        if not all: return None,0,0
        if page<0: page=0
        elif page>=len(all): page=len(all)-1
        return all[page], page, len(all)
    except: return None,0,0

def get_planes_page(page=0):
    try:
        conn = get_db()
        all = conn.execute('SELECT * FROM shop_planes WHERE in_shop = 1 ORDER BY price').fetchall()
        conn.close()
        if not all: return None,0,0
        if page<0: page=0
        elif page>=len(all): page=len(all)-1
        return all[page], page, len(all)
    except: return None,0,0

def get_houses_page(page=0):
    try:
        conn = get_db()
        all = conn.execute('SELECT * FROM shop_houses WHERE in_shop = 1 ORDER BY price').fetchall()
        conn.close()
        if not all: return None,0,0
        if page<0: page=0
        elif page>=len(all): page=len(all)-1
        return all[page], page, len(all)
    except: return None,0,0

def get_clothes_page(page=0):
    try:
        conn = get_db()
        all = conn.execute('SELECT * FROM shop_clothes WHERE in_shop = 1 ORDER BY price').fetchall()
        conn.close()
        if not all: return None,0,0
        if page<0: page=0
        elif page>=len(all): page=len(all)-1
        return all[page], page, len(all)
    except: return None,0,0

def get_clothes_navigation_keyboard(current_page, total_items):
    markup = types.InlineKeyboardMarkup(row_width=3)
    btns = []
    btns.append(types.InlineKeyboardButton("◀️", callback_data=f"shop_page_{current_page-1}") if current_page>0 else types.InlineKeyboardButton("⬜️", callback_data="noop"))
    btns.append(types.InlineKeyboardButton("🛒 Купить", callback_data=f"shop_buy_{current_page}"))
    btns.append(types.InlineKeyboardButton("▶️", callback_data=f"shop_page_{current_page+1}") if current_page<total_items-1 else types.InlineKeyboardButton("⬜️", callback_data="noop"))
    markup.row(*btns)
    markup.row(types.InlineKeyboardButton("❌ Закрыть", callback_data="shop_close"))
    return markup

def get_cars_navigation_keyboard(current_page, total_items, shop_type):
    markup = types.InlineKeyboardMarkup(row_width=3)
    btns = []
    btns.append(types.InlineKeyboardButton("◀️", callback_data=f"{shop_type}_page_{current_page-1}") if current_page>0 else types.InlineKeyboardButton("⬜️", callback_data="noop"))
    btns.append(types.InlineKeyboardButton("🛒 Купить", callback_data=f"{shop_type}_buy_{current_page}"))
    btns.append(types.InlineKeyboardButton("▶️", callback_data=f"{shop_type}_page_{current_page+1}") if current_page<total_items-1 else types.InlineKeyboardButton("⬜️", callback_data="noop"))
    markup.row(*btns)
    markup.row(types.InlineKeyboardButton("❌ Закрыть", callback_data="shop_close"))
    return markup

def get_houses_navigation_keyboard(current_page, total_items, shop_type):
    markup = types.InlineKeyboardMarkup(row_width=3)
    btns = []
    btns.append(types.InlineKeyboardButton("◀️", callback_data=f"{shop_type}_page_{current_page-1}") if current_page>0 else types.InlineKeyboardButton("⬜️", callback_data="noop"))
    btns.append(types.InlineKeyboardButton("🏠 Купить", callback_data=f"{shop_type}_buy_{current_page}"))
    btns.append(types.InlineKeyboardButton("▶️", callback_data=f"{shop_type}_page_{current_page+1}") if current_page<total_items-1 else types.InlineKeyboardButton("⬜️", callback_data="noop"))
    markup.row(*btns)
    markup.row(types.InlineKeyboardButton("❌ Закрыть", callback_data="shop_close"))
    return markup

def get_closet_navigation_keyboard(clothes_list, current_page):
    """Клавиатура для просмотра шкафа"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    start_idx = current_page * 5
    end_idx = start_idx + 5
    page_items = clothes_list[start_idx:end_idx]
    
    for item in page_items:
        btn_text = f"👕 {item['name']}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"closet_equip_{item['user_clothes_id']}"))
    
    nav_btns = []
    if current_page > 0:
        nav_btns.append(types.InlineKeyboardButton("◀️", callback_data=f"closet_page_{current_page-1}"))
    if end_idx < len(clothes_list):
        nav_btns.append(types.InlineKeyboardButton("▶️", callback_data=f"closet_page_{current_page+1}"))
    if nav_btns:
        markup.row(*nav_btns)
    
    markup.row(types.InlineKeyboardButton("➕ Купить слот", callback_data="closet_buy_slot"))
    markup.row(types.InlineKeyboardButton("🔙 Назад", callback_data="closet_back"))
    return markup

# ========== ФУНКЦИИ ДЛЯ РУЛЕТКИ ==========
def parse_bet_amount(amount_str):
    amount_str = amount_str.lower().strip()
    mult = {'к':1000,'кк':1000000,'ккк':1000000000,'кккк':1000000000000,'kk':1000,'kkk':1000000,'kkkk':1000000000,'kkkkk':1000000000000}
    if amount_str in ['все','алл','максимум','всё','all','max']: return -1
    for suf, m in mult.items():
        if amount_str.endswith(suf):
            try: return int(float(amount_str[:-len(suf)]) * m)
            except: pass
    try: return int(amount_str)
    except: return None

def parse_roulette_bet(t):
    t = t.lower().strip().split()
    if len(t)!=3 or not (t[0].startswith('рул') or t[0].startswith('рулетка')): return None
    bet = parse_bet_amount(t[2])
    if bet is None: return None
    types = {'крас':'red','красное':'red','чер':'black','черное':'black','чет':'even','четное':'even','нечет':'odd','нечетное':'odd','бол':'high','большое':'high','мал':'low','маленькое':'low','1-12':'1-12','13-24':'13-24','25-36':'25-36','зеро':'0'}
    for k,v in types.items():
        if t[1]==k or t[1] in k.split(): return (v, bet)
    if t[1].isdigit():
        n = int(t[1])
        if 0<=n<=36: return (f'num_{n}', bet)
    return None

def update_roulette_stats(uid, bet, win):
    try:
        conn = get_db()
        s = conn.execute('SELECT * FROM roulette_stats WHERE user_id = ?', (uid,)).fetchone()
        if s:
            gp = s['games_played']+1
            tb = s['total_bet']+bet
            w = s['wins']+(1 if win>0 else 0)
            l = s['losses']+(1 if win==0 else 0)
            tw = s['total_win']+(win if win>0 else 0)
            tl = s['total_lose']+(bet if win==0 else 0)
            bw = max(s['biggest_win'], win) if win>0 else s['biggest_win']
            bl = max(s['biggest_lose'], bet) if win==0 else s['biggest_lose']
            conn.execute('UPDATE roulette_stats SET games_played=?, wins=?, losses=?, total_bet=?, total_win=?, total_lose=?, biggest_win=?, biggest_lose=?, last_game=? WHERE user_id=?', (gp,w,l,tb,tw,tl,bw,bl,datetime.now().isoformat(),uid))
        else:
            conn.execute('INSERT INTO roulette_stats (user_id, games_played, wins, losses, total_bet, total_win, total_lose, biggest_win, biggest_lose, last_game) VALUES (?,1,?,?,?,?,?,?,?,?)', (uid,1 if win>0 else 0,1 if win==0 else 0,bet,win if win>0 else 0,bet if win==0 else 0,win if win>0 else 0,bet if win==0 else 0,datetime.now().isoformat()))
        conn.commit(); conn.close()
        return True
    except: return False

def get_roulette_stats(uid):
    try:
        conn = get_db()
        s = conn.execute('SELECT * FROM roulette_stats WHERE user_id = ?', (uid,)).fetchone()
        conn.close()
        return s
    except: return None

def get_roulette_result(n):
    if n==0: return {'name':'Зеро','emoji':'🟢','color':'green'}
    red = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    return {'name':'Красное','emoji':'🔴','color':'red'} if n in red else {'name':'Черное','emoji':'⚫','color':'black'}

def check_roulette_win(n, bt, ba):
    red = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    black = [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35]
    if bt=='red' and n in red: return ba*2
    if bt=='black' and n in black: return ba*2
    if bt=='even' and n!=0 and n%2==0: return ba*2
    if bt=='odd' and n%2==1: return ba*2
    if bt=='high' and 19<=n<=36: return ba*2
    if bt=='low' and 1<=n<=18: return ba*2
    if bt=='1-12' and 1<=n<=12: return ba*3
    if bt=='13-24' and 13<=n<=24: return ba*3
    if bt=='25-36' and 25<=n<=36: return ba*3
    if bt=='0' and n==0: return ba*36
    if bt.startswith('num_') and n==int(bt.split('_')[1]): return ba*36
    return 0

def gen_anim(f):
    return "[" + "] [".join([str(random.randint(0,36)) for _ in range(5)] + [str(f)]) + "]"

def bet_name(bt):
    names = {'red':'🔴 КРАСНОЕ','black':'⚫ ЧЕРНОЕ','even':'💰 ЧЕТНОЕ','odd':'📊 НЕЧЕТНОЕ','high':'📈 БОЛЬШОЕ (19-36)','low':'📉 МАЛЕНЬКОЕ (1-18)','1-12':'🎯 1-12','13-24':'🎯 13-24','25-36':'🎯 25-36','0':'🎰 ЗЕРО'}
    if bt.startswith('num_'): return f"⚡ ЧИСЛО {bt.split('_')[1]}"
    return names.get(bt, bt)

# ========== ФУНКЦИИ ДЛЯ МИНИ-ИГР ==========
def update_work_stats(user_id, job_type, score, time_spent, earned):
    try:
        conn = get_db()
        s = conn.execute('SELECT * FROM work_stats WHERE user_id = ? AND job_type = ?', (user_id, job_type)).fetchone()
        if s:
            gp = s['games_played']+1
            pg = s['perfect_games']+(1 if score==100 else 0)
            bt = min(s['best_time'], time_spent) if s['best_time']>0 else time_spent
            te = s['total_earned']+earned
            av = (s['avg_score']*s['games_played']+score)//gp
            conn.execute('UPDATE work_stats SET games_played=?, perfect_games=?, best_time=?, total_earned=?, avg_score=? WHERE user_id=? AND job_type=?', (gp,pg,bt,te,av,user_id,job_type))
        else:
            conn.execute('INSERT INTO work_stats (user_id, job_type, games_played, perfect_games, best_time, total_earned, avg_score) VALUES (?,?,1,?,?,?,?)', (user_id,job_type,1 if score==100 else 0,time_spent,earned,score))
        conn.commit(); conn.close()
        return True
    except: return False

# ГРУЗЧИК
def start_loader_game(user_id, job_name):
    target = random.sample(range(1,10),3)
    markup = types.InlineKeyboardMarkup(row_width=3)
    row = []
    for i in range(9):
        row.append(types.InlineKeyboardButton(f"📦 {i+1}", callback_data=f"loader_{i+1}"))
        if (i+1)%3==0: markup.row(*row); row=[]
    loader_games[user_id] = {'targets':target,'collected':[],'start':time.time()}
    return markup, f"🚚 **{job_name}**\n🎯 Найди коробки: {target}\n⏱️ Время пошло!"

def check_loader_click(user_id, num):
    if user_id not in loader_games: return None
    g = loader_games[user_id]
    if num in g['targets'] and num not in g['collected']:
        g['collected'].append(num)
        if len(g['collected']) == len(g['targets']):
            ts = time.time()-g['start']; del loader_games[user_id]
            return {'win':True,'time':ts,'score':100}
    return {'win':False,'collected':len(g['collected']),'total':len(g['targets'])}

# УБОРЩИК
def start_cleaner_game(user_id, job_name):
    trash = random.sample(range(1,10),5)
    markup = types.InlineKeyboardMarkup(row_width=3)
    row = []
    for i in range(9):
        btn_text = "🧹" if (i+1) in trash else "⬜"
        row.append(types.InlineKeyboardButton(btn_text, callback_data=f"cleaner_{i+1}"))
        if (i+1)%3==0: markup.row(*row); row=[]
    cleaner_games[user_id] = {'trash':trash,'cleaned':[],'start':time.time()}
    return markup, f"🧹 **{job_name}**\n🎯 Убери 5 мусора\n⏱️ Время пошло!"

def check_cleaner_click(user_id, pos):
    if user_id not in cleaner_games: return None
    g = cleaner_games[user_id]
    if pos in g['trash'] and pos not in g['cleaned']:
        g['cleaned'].append(pos)
        if len(g['cleaned']) == len(g['trash']):
            ts = time.time()-g['start']; del cleaner_games[user_id]
            return {'win':True,'time':ts,'score':100}
    return {'win':False,'collected':len(g['cleaned']),'total':len(g['trash'])}

# КУРЬЕР
def start_courier_game(user_id, job_name):
    routes = [{'name':'Кратчайший','time':15,'correct':True},{'name':'Быстрый','time':25,'correct':False},{'name':'Объезд','time':40,'correct':False},{'name':'Платный','time':10,'correct':False}]
    random.shuffle(routes)
    markup = types.InlineKeyboardMarkup(row_width=2)
    for r in routes: markup.add(types.InlineKeyboardButton(f"🚦 {r['name']} ({r['time']} сек)", callback_data=f"courier_{r['correct']}_{r['time']}"))
    courier_games[user_id] = {'start':time.time()}
    return markup, f"📦 **{job_name}**\n🗺️ Выбери быстрый маршрут\n⏱️ 30 сек"

def check_courier_choice(user_id, cor, rt):
    if user_id not in courier_games: return None
    ts = time.time()-courier_games[user_id]['start']; del courier_games[user_id]
    if cor=='True' and ts<=rt: return {'win':True,'time':ts,'score':100}
    return {'win':False,'time':ts,'score':0}

# МЕХАНИК
def start_mechanic_game(user_id, job_name):
    parts = [1,2,3,4]; random.shuffle(parts)
    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = []
    for i,p in enumerate(parts): btns.append(types.InlineKeyboardButton(f"🔧 Деталь {p}", callback_data=f"mechanic_{i}_{p}"))
    markup.add(*btns)
    mechanic_games[user_id] = {'parts':parts,'solution':[1,2,3,4],'current':[],'start':time.time()}
    return markup, f"🔧 **{job_name}**\n🔩 Собери 1→2→3→4\n⏱️ Время пошло!"

def check_mechanic_click(user_id, idx, part):
    if user_id not in mechanic_games: return None
    g = mechanic_games[user_id]
    if part == g['solution'][len(g['current'])]:
        g['current'].append(part)
        if len(g['current'])==4:
            ts = time.time()-g['start']; del mechanic_games[user_id]
            return {'win':True,'time':ts,'score':100}
    return {'win':False,'progress':len(g['current'])}

# ПРОГРАММИСТ
def start_programmer_game(user_id, job_name):
    bugs = [{'code':'x = 10\ny = "5"\nprint(x + y)','cor':1},{'code':'for i in range(10)\n    print(i)','cor':2},{'code':'if x = 5:\n    print("ok")','cor':2}]
    b = random.choice(bugs)
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i,opt in enumerate(['Тип данных','Синтаксис','Логика'],1):
        markup.add(types.InlineKeyboardButton(opt, callback_data=f"programmer_{'correct' if i==b['cor'] else 'wrong'}"))
    programmer_games[user_id] = {'start':time.time()}
    return markup, f"💻 **{job_name}**\n```python\n{b['code']}\n```\n❓ Ошибка?\n⏱️ Время пошло!"

def check_programmer_choice(user_id, cor):
    if user_id not in programmer_games: return None
    ts = time.time()-programmer_games[user_id]['start']; del programmer_games[user_id]
    if cor=='correct': return {'win':True,'time':ts,'score':max(100-int(ts),50)}
    return {'win':False,'time':ts,'score':0}

# ДЕТЕКТИВ
def start_detective_game(user_id, job_name):
    clues = [{'clue':'Он был высоким и в шляпе','opts':['Дворецкий','Садовник','Повар'],'cor':0},{'clue':'Нашли сигарету','opts':['Курильщик','Не курильщик','Случайный'],'cor':0},{'clue':'Собака не лаяла','opts':['Свой','Чужой','Призрак'],'cor':0}]
    c = random.choice(clues)
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i,opt in enumerate(c['opts']):
        markup.add(types.InlineKeyboardButton(f"🕵️ {opt}", callback_data=f"detective_{'correct' if i==c['cor'] else 'wrong'}"))
    detective_games[user_id] = {'start':time.time()}
    return markup, f"🕵️ **{job_name}**\n🔍 {c['clue']}\n❓ Кто?\n⏱️ Время пошло!"

def check_detective_choice(user_id, cor):
    if user_id not in detective_games: return None
    ts = time.time()-detective_games[user_id]['start']; del detective_games[user_id]
    if cor=='correct': return {'win':True,'time':ts,'score':max(100-int(ts),60)}
    return {'win':False,'time':ts,'score':0}

# ИНЖЕНЕР
def start_engineer_game(user_id, job_name):
    scheme = [random.choice(['🔴','🔵','🟢','🟡']) for _ in range(5)]
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("🔴", callback_data="engineer_🔴"), types.InlineKeyboardButton("🔵", callback_data="engineer_🔵"), types.InlineKeyboardButton("🟢", callback_data="engineer_🟢"), types.InlineKeyboardButton("🟡", callback_data="engineer_🟡"))
    engineer_games[user_id] = {'scheme':scheme,'answer':[],'start':time.time(),'mem':False}
    return markup, f"👨‍🔧 **{job_name}**\n🎯 Запомни: {' '.join(scheme)}\n⏱️ 5 сек!"

def check_engineer_click(user_id, color):
    if user_id not in engineer_games: return None
    g = engineer_games[user_id]
    if time.time()-g['start']<5: return {'mem':True,'prog':len(g['answer'])}
    g['mem']=True; g['answer'].append(color)
    if len(g['answer'])==len(g['scheme']):
        ts = time.time()-g['start']; del engineer_games[user_id]
        if g['answer']==g['scheme']: return {'win':True,'time':ts,'score':100}
        else: return {'win':False,'time':ts,'score':0}
    return {'prog':len(g['answer']),'total':len(g['scheme'])}

# ВРАЧ
def start_doctor_game(user_id, job_name):
    patients = [{'sym':'Боль в груди, одышка','act':['Нитроглицерин','Аспирин','Валидол'],'cor':0,'time':10},{'sym':'Температура, кашель','act':['Антибиотики','Парацетамол','Витамины'],'cor':1,'time':8},{'sym':'Головная боль, тошнота','act':['Анальгин','Но-шпа','Активированный уголь'],'cor':2,'time':7}]
    p = random.choice(patients)
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i,act in enumerate(p['act']):
        markup.add(types.InlineKeyboardButton(f"💊 {act}", callback_data=f"doctor_{'correct' if i==p['cor'] else 'wrong'}_{p['time']}"))
    doctor_games[user_id] = {'start':time.time(),'limit':p['time']}
    return markup, f"👨‍⚕️ **{job_name}**\n🏥 {p['sym']}\n⏱️ {p['time']} сек!"

def check_doctor_choice(user_id, cor, lim):
    if user_id not in doctor_games: return None
    ts = time.time()-doctor_games[user_id]['start']; del doctor_games[user_id]
    if cor=='correct' and ts<=lim: return {'win':True,'time':ts,'score':max(100-int(ts*2),70)}
    return {'win':False,'time':ts,'score':0}

# АРТИСТ
def start_artist_game(user_id, job_name):
    songs = [{'emo':'🎸🌧️🎵','opt':['Группа крови','Звезда','Кукушка'],'cor':0},{'emo':'💃🕺🔥','opt':['Лада седан','Розовый вечер','Владимирский'],'cor':1},{'emo':'❤️💔📱','opt':['Phone 404','Позвони мне','СМС'],'cor':2}]
    s = random.choice(songs)
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i,opt in enumerate(s['opt']):
        markup.add(types.InlineKeyboardButton(f"🎵 {opt}", callback_data=f"artist_{'correct' if i==s['cor'] else 'wrong'}"))
    artist_games[user_id] = {'start':time.time()}
    return markup, f"👨‍🎤 **{job_name}**\n🎼 {s['emo']}\n❓ Песня?\n⏱️ Время пошло!"

def check_artist_choice(user_id, cor):
    if user_id not in artist_games: return None
    ts = time.time()-artist_games[user_id]['start']; del artist_games[user_id]
    if cor=='correct': return {'win':True,'time':ts,'score':max(100-int(ts),70)}
    return {'win':False,'time':ts,'score':0}

# КОСМОНАВТ
def start_cosmonaut_game(user_id, job_name):
    size = 5
    rocket = (2,2)
    station = (0,4)
    fuel = []
    while len(fuel)<3:
        pos = (random.randint(0,4), random.randint(0,4))
        if pos!=rocket and pos!=station and pos not in fuel: fuel.append(pos)
    markup = types.InlineKeyboardMarkup(row_width=size)
    for i in range(size):
        row = []
        for j in range(size):
            if (i,j)==rocket: row.append(types.InlineKeyboardButton("🚀", callback_data="cosmo_rocket"))
            elif (i,j)==station: row.append(types.InlineKeyboardButton("🛸", callback_data="cosmo_station"))
            elif (i,j) in fuel: row.append(types.InlineKeyboardButton("⛽", callback_data=f"cosmo_fuel_{i}_{j}"))
            else: row.append(types.InlineKeyboardButton("⬜", callback_data=f"cosmo_move_{i}_{j}"))
        markup.row(*row)
    markup.row(types.InlineKeyboardButton("⬆️", callback_data="cosmo_up"), types.InlineKeyboardButton("⬇️", callback_data="cosmo_down"), types.InlineKeyboardButton("⬅️", callback_data="cosmo_left"), types.InlineKeyboardButton("➡️", callback_data="cosmo_right"))
    cosmonaut_games[user_id] = {'rocket':rocket,'station':station,'fuel':fuel,'collected':[],'size':size,'start':time.time()}
    return markup, f"👨‍🚀 **{job_name}**\n🛸 Доставь 🚀 к 🛸, собери ⛽\n⬆️⬇️⬅️➡️"

def check_cosmonaut_move(user_id, direction):
    if user_id not in cosmonaut_games: return None
    g = cosmonaut_games[user_id]
    x,y = g['rocket']
    size = g['size']
    nx, ny = x, y
    if direction=='up' and x>0: nx = x-1
    elif direction=='down' and x<size-1: nx = x+1
    elif direction=='left' and y>0: ny = y-1
    elif direction=='right' and y<size-1: ny = y+1
    else: return {'invalid':True}
    g['rocket'] = (nx,ny)
    if (nx,ny) in g['fuel'] and (nx,ny) not in g['collected']: g['collected'].append((nx,ny))
    markup = types.InlineKeyboardMarkup(row_width=size)
    for i in range(size):
        row = []
        for j in range(size):
            if (i,j)==g['rocket']: row.append(types.InlineKeyboardButton("🚀", callback_data="cosmo_rocket"))
            elif (i,j)==g['station']: row.append(types.InlineKeyboardButton("🛸", callback_data="cosmo_station"))
            elif (i,j) in g['fuel'] and (i,j) not in g['collected']: row.append(types.InlineKeyboardButton("⛽", callback_data=f"cosmo_fuel_{i}_{j}"))
            else: row.append(types.InlineKeyboardButton("⬜", callback_data=f"cosmo_move_{i}_{j}"))
        markup.row(*row)
    markup.row(types.InlineKeyboardButton("⬆️", callback_data="cosmo_up"), types.InlineKeyboardButton("⬇️", callback_data="cosmo_down"), types.InlineKeyboardButton("⬅️", callback_data="cosmo_left"), types.InlineKeyboardButton("➡️", callback_data="cosmo_right"))
    if g['rocket']==g['station'] and len(g['collected'])==len(g['fuel']):
        ts = time.time()-g['start']; del cosmonaut_games[user_id]
        score = max(100-int(ts),70)
        return {'win':True,'time':ts,'score':score,'markup':markup}
    return {'moved':True,'markup':markup,'collected':len(g['collected']),'total':len(g['fuel'])}

# ========== ФУНКЦИИ ДЛЯ ЧАТА ==========
def send_profile_to_chat(cid, uid, tid=None):
    if tid is None: tid=uid
    ud = get_user_profile(tid)
    if not ud: bot.send_message(cid, "❌ Не найден"); return
    bal = get_balance(tid); name = get_user_display_name(ud); city = get_user_city(tid)
    exp,lvl,wc,total = get_user_stats(tid)
    clothes = get_user_equipped_clothes(tid); ci = f", одет: {clothes['name']}" if clothes else ""
    biz = get_user_business(tid); bi = "Нет" if not biz else f"{biz['business_name']} (ур.{biz['level']})"
    car = get_user_car(tid); ci_car = f", 🚗 {car['name']}" if car else ""
    plane = get_user_plane(tid); ci_plane = f", ✈️ {plane['name']}" if plane else ""
    house = get_user_house(tid); hi = f", 🏠 {house['house']['name']}" if house else ""
    msg = f"👤 **ПРОФИЛЬ**\n👤 {name}{ci}{ci_car}{ci_plane}{hi}\n📍 {city}\n💰 {bal:,}\n⭐ {exp} (ур.{lvl})\n🔨 {wc}\n💵 {total:,}\n🏭 {bi}"
    if biz: msg += f"\n📦 {biz['raw_material']}/1000\n💰 Прибыль: {biz['stored_profit']:,}"
    if house: msg += f"\n🏠 Дом куплен в {house['city']} за {house['price']:,}"
    rs = get_roulette_stats(tid)
    if rs:
        profit = rs['total_win']-rs['total_lose']; ps = "+" if profit>=0 else ""
        wr = (rs['wins']/rs['games_played']*100) if rs['games_played']>0 else 0
        msg += f"\n\n🎰 **РУЛЕТКА**\n🎮 {rs['games_played']} | Побед: {wr:.1f}%\n💰 Выиграно: {rs['total_win']:,}\n💸 Проиграно: {rs['total_lose']:,}\n📈 {ps}{profit:,}"
    photo = get_user_profile_photo(tid)
    if photo: bot.send_photo(cid, photo, caption=msg, parse_mode="Markdown")
    else: bot.send_message(cid, msg, parse_mode="Markdown")

def process_raw_order(uid, cid):
    biz = get_user_business(uid)
    if not biz: bot.send_message(cid, "❌ Нет бизнеса"); return
    d = get_business_data(biz['business_name'])
    if not d: bot.send_message(cid, "❌ Ошибка"); return
    bal = get_balance(uid); cost = d['raw_cost_per_unit']; maxb = bal//cost
    total = biz['raw_material']+biz['raw_in_delivery']; free = 1000-total
    amt = min(maxb, free)
    if amt<=0: bot.send_message(cid, f"❌ {'Склад полон' if free<=0 else f'Нужно {cost:,}💰'}"); return
    tc = amt*cost
    if not add_balance(uid, -tc): bot.send_message(cid, "❌ Ошибка"); return
    if has_active_delivery(uid): bot.send_message(cid, "❌ Уже есть доставка"); add_balance(uid, tc); return
    conn = get_db()
    conn.execute('INSERT INTO deliveries (user_id, amount, end_time, delivered) VALUES (?,?,?,0)', (uid, amt, (datetime.now()+timedelta(minutes=15)).isoformat()))
    conn.execute('UPDATE businesses SET raw_in_delivery = raw_in_delivery + ?, total_invested = total_invested + ? WHERE user_id = ?', (amt, tc, uid))
    conn.commit(); conn.close()
    bot.send_message(cid, f"✅ Заказ на {amt} сырья!\n💰 {tc:,}\n📦 Будет: {total+amt}/1000\n⏱️ 15 мин")

def send_top_to_chat(cid):
    try:
        conn = get_db()
        top = conn.execute('SELECT first_name, username, custom_name, balance FROM users ORDER BY balance DESC LIMIT 10').fetchall()
        conn.close()
        if not top: bot.send_message(cid, "❌ Топ пуст"); return
        msg = "🏆 **ТОП 10 БОГАЧЕЙ**\n"
        for i,(fn,un,cn,bal) in enumerate(top,1):
            medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
            name = cn or (f"@{un}" if un and un!="NoUsername" else fn)
            msg += f"{medal} {name}: {bal:,}💰\n"
        bot.send_message(cid, msg, parse_mode="Markdown")
    except: bot.send_message(cid, "❌ Ошибка")

# ========== КЛАВИАТУРЫ ==========
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(types.KeyboardButton("💼 Работы"), types.KeyboardButton("🏭 Бизнесы"))
    markup.row(types.KeyboardButton("👕 Магазин одежды"), types.KeyboardButton("🎁 Ежедневно"))
    markup.row(types.KeyboardButton("🗺️ Карта"), types.KeyboardButton("🏠 Мой дом"))
    markup.row(types.KeyboardButton("⚙️ Настройки"), types.KeyboardButton("🔄"))
    return markup

def cities_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(types.KeyboardButton("🏙️ Москва"), types.KeyboardButton("🏙️ Село Молочное"))
    markup.row(types.KeyboardButton("🏙️ Кропоткин"), types.KeyboardButton("🏙️ Мурино"))
    markup.row(types.KeyboardButton("🔙 Назад"))
    return markup

def transport_keyboard(city):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(types.KeyboardButton("🚕 Такси"), types.KeyboardButton("🚗 Личная машина"))
    markup.row(types.KeyboardButton("✈️ Личный самолет"), types.KeyboardButton("🔙 Назад"))
    return markup

def jobs_keyboard(user_id):
    jobs = get_available_jobs(user_id)
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    for job in jobs: markup.add(types.KeyboardButton(f"{job[5]} {job[0]}"))
    markup.row(types.KeyboardButton("👥 Рефералы"), types.KeyboardButton("🔙 Назад"))
    return markup

def businesses_main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(types.KeyboardButton("📊 Мой бизнес"), types.KeyboardButton("💰 Собрать прибыль"))
    markup.row(types.KeyboardButton("📦 Закупить на всё"), types.KeyboardButton("🏪 Купить бизнес"))
    markup.row(types.KeyboardButton("💰 Продать бизнес"), types.KeyboardButton("🔙 Назад"))
    return markup

def buy_business_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(types.KeyboardButton("🥤 Киоск"), types.KeyboardButton("🍔 Фастфуд"))
    markup.row(types.KeyboardButton("🏪 Минимаркет"), types.KeyboardButton("⛽ Заправка"))
    markup.row(types.KeyboardButton("🏨 Отель"), types.KeyboardButton("🔙 Назад"))
    return markup

def settings_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(types.KeyboardButton("✏️ Сменить никнейм"), types.KeyboardButton("📋 Помощь"))
    markup.row(types.KeyboardButton("🔙 Назад"))
    return markup

def city_shop_keyboard(shop_type):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    if shop_type=='clothes': markup.row(types.KeyboardButton("👕 Смотреть одежду"))
    elif shop_type=='cars': 
        markup.row(types.KeyboardButton("🚗 Смотреть машины"))
        markup.row(types.KeyboardButton("💰 Продать машину"))
    elif shop_type=='planes': 
        markup.row(types.KeyboardButton("✈️ Смотреть самолеты"))
        markup.row(types.KeyboardButton("💰 Продать самолет"))
    elif shop_type=='houses': 
        markup.row(types.KeyboardButton("🏠 Смотреть дома"))
    markup.row(types.KeyboardButton("🔙 Назад"))
    return markup

def house_menu_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(types.KeyboardButton("👕 Шкаф"), types.KeyboardButton("💰 Продать дом"))
    markup.row(types.KeyboardButton("🔙 Назад"))
    return markup

def get_business_buy_keyboard(business_name):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("✅ Купить", callback_data=f"buy_business_{business_name}"), types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_buy_business"))
    return markup

# ========== АДМИН КОМАНДЫ ==========
@bot.message_handler(commands=['adminhelp'])
def admin_help(m):
    uid = m.from_user.id; lvl = get_admin_level(uid)
    if lvl==0: bot.reply_to(m, "❌ Только для админов!"); return
    txt = f"👑 **АДМИН (Ур.{lvl})**\n"
    txt += "Ур.1: /giveme [сумма], /addexpm [опыт]\n"
    if lvl>=2: txt += "Ур.2: /give [юзер] [сумма], /addexp [юзер] [опыт], /profile [юзер], /giveskin [юзер] [скин]\n"
    if lvl>=3: txt += "Ур.3: /addadmin [юзер] [ур], /adminlist, /reset [юзер], /wipe [юзер]\n"
    if lvl>=4: txt += "Ур.4: /removeadmin [юзер], /setadminlevel [юзер] [ур], /ban [юзер] [ч], /unban [юзер], /warn [юзер], /warns [юзер]"
    bot.reply_to(m, txt, parse_mode="Markdown")

@bot.message_handler(commands=['giveme'])
def give_me(m):
    uid = m.from_user.id
    if not is_admin(uid,1): bot.reply_to(m, "❌ Нет прав"); return
    try:
        amt = int(m.text.split()[1])
        if add_balance(uid, amt): bot.reply_to(m, f"✅ +{amt}💰\nНовый баланс: {get_balance(uid):,}")
        else: bot.reply_to(m, "❌ Ошибка")
    except: bot.reply_to(m, "❌ Формат: /giveme [сумма]")

@bot.message_handler(commands=['addexpm'])
def add_exp_me(m):
    uid = m.from_user.id
    if not is_admin(uid,1): bot.reply_to(m, "❌ Нет прав"); return
    try:
        amt = int(m.text.split()[1])
        if add_exp(uid, amt): s = get_user_stats(uid); bot.reply_to(m, f"✅ +{amt}⭐\nТеперь: {s[0]}⭐ (ур.{s[1]})")
        else: bot.reply_to(m, "❌ Ошибка")
    except: bot.reply_to(m, "❌ Формат: /addexpm [количество]")

@bot.message_handler(commands=['give'])
def give_money(m):
    uid = m.from_user.id
    if not is_admin(uid,2): bot.reply_to(m, "❌ Нет прав"); return
    try:
        p = m.text.split()
        if len(p)==2:
            amt = int(p[1])
            if add_balance(uid, amt): bot.reply_to(m, f"✅ +{amt}💰 себе\nБаланс: {get_balance(uid):,}")
            else: bot.reply_to(m, "❌ Ошибка")
        elif len(p)==3:
            target = p[1]; amt = int(p[2])
            ud = find_user_by_input(target)
            if not ud: bot.reply_to(m, f"❌ {target} не найден"); return
            tid = ud[0]; name = get_user_display_name(ud)
            if add_balance(tid, amt):
                try: bot.send_message(tid, f"💰 Админ выдал {amt}💰")
                except: pass
                bot.reply_to(m, f"✅ {amt}💰 выдано {name}")
            else: bot.reply_to(m, "❌ Ошибка")
        else: bot.reply_to(m, "❌ Формат: /give [сумма] или /give [юзер] [сумма]")
    except: bot.reply_to(m, "❌ Ошибка")

@bot.message_handler(commands=['addexp'])
def add_exp(m):
    uid = m.from_user.id
    if not is_admin(uid,2): bot.reply_to(m, "❌ Нет прав"); return
    try:
        p = m.text.split()
        if len(p)==2:
            amt = int(p[1])
            if add_exp(uid, amt): s = get_user_stats(uid); bot.reply_to(m, f"✅ +{amt}⭐ себе\nТеперь: {s[0]}⭐ (ур.{s[1]})")
            else: bot.reply_to(m, "❌ Ошибка")
        elif len(p)==3:
            target = p[1]; amt = int(p[2])
            ud = find_user_by_input(target)
            if not ud: bot.reply_to(m, f"❌ {target} не найден"); return
            tid = ud[0]; name = get_user_display_name(ud)
            if add_exp(tid, amt):
                try: bot.send_message(tid, f"⭐ Админ выдал {amt} опыта")
                except: pass
                s = get_user_stats(tid)
                bot.reply_to(m, f"✅ {amt}⭐ опыта выдано {name}\nТеперь: {s[0]}⭐ (ур.{s[1]})")
            else: bot.reply_to(m, "❌ Ошибка")
        else: bot.reply_to(m, "❌ Формат: /addexp [опыт] или /addexp [юзер] [опыт]")
    except: bot.reply_to(m, "❌ Ошибка")

@bot.message_handler(commands=['profile'])
def profile_cmd(m):
    uid = m.from_user.id
    if not is_admin(uid,2): bot.reply_to(m, "❌ Нет прав"); return
    try:
        target = m.text.split()[1]
        ud = find_user_by_input(target)
        if not ud: bot.reply_to(m, f"❌ {target} не найден"); return
        send_profile_to_chat(m.chat.id, uid, ud[0])
    except: bot.reply_to(m, "❌ Формат: /profile [юзер]")

@bot.message_handler(commands=['giveskin'])
def give_skin(m):
    uid = m.from_user.id
    if not is_admin(uid,2): bot.reply_to(m, "❌ Нет прав"); return
    try:
        p = m.text.split(maxsplit=2)
        if len(p)!=3:
            conn = get_db()
            skins = conn.execute('SELECT name FROM shop_clothes ORDER BY name').fetchall()
            conn.close()
            sl = "\n".join([f"• {s['name']}" for s in skins])
            bot.reply_to(m, f"❌ Формат: /giveskin [юзер] [скин]\n\n📋 **Скины:**\n{sl}", parse_mode="Markdown")
            return
        target, skin_name = p[1], p[2]
        ud = find_user_by_input(target)
        if not ud: bot.reply_to(m, f"❌ {target} не найден"); return
        tid = ud[0]; tname = get_user_display_name(ud)
        conn = get_db()
        skin = conn.execute('SELECT * FROM shop_clothes WHERE name LIKE ? COLLATE NOCASE', (f'%{skin_name}%',)).fetchone()
        if not skin: skin = conn.execute('SELECT * FROM shop_clothes WHERE name = ? COLLATE NOCASE', (skin_name,)).fetchone()
        if not skin: conn.close(); bot.reply_to(m, f"❌ Скин '{skin_name}' не найден"); return
        existing = conn.execute('SELECT id FROM user_clothes WHERE user_id = ? AND clothes_id = ?', (tid, skin['id'])).fetchone()
        if existing: conn.close(); bot.reply_to(m, f"❌ У {tname} уже есть скин '{skin['name']}'"); return
        conn.execute('UPDATE user_clothes SET equipped = 0 WHERE user_id = ?', (tid,))
        conn.execute('INSERT INTO user_clothes (user_id, clothes_id, equipped) VALUES (?,?,1)', (tid, skin['id']))
        conn.execute('UPDATE users SET equipped_clothes = ? WHERE user_id = ?', (skin['id'], tid))
        conn.commit(); conn.close()
        try: bot.send_message(tid, f"👑 Админ выдал тебе скин **{skin['name']}**!", parse_mode="Markdown")
        except: pass
        bot.reply_to(m, f"✅ Скин '{skin['name']}' выдан {tname}!")
    except Exception as e: bot.reply_to(m, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['addadmin'])
def add_admin_cmd(m):
    uid = m.from_user.id
    if not is_admin(uid,3): bot.reply_to(m, "❌ Нет прав"); return
    try:
        p = m.text.split()
        if len(p)!=3: bot.reply_to(m, "❌ Формат: /addadmin [юзер] [уровень]"); return
        target, lvl = p[1], int(p[2])
        if lvl<1 or lvl>3: bot.reply_to(m, "❌ Уровень 1-3"); return
        ud = find_user_by_input(target)
        if not ud: bot.reply_to(m, f"❌ {target} не найден"); return
        ok, msg = add_admin(ud[0], lvl)
        if ok:
            try: bot.send_message(ud[0], f"👑 Вы админ {lvl} уровня!\n/adminhelp")
            except: pass
            bot.reply_to(m, f"✅ {get_user_display_name(ud)} теперь админ {lvl} уровня!")
        else: bot.reply_to(m, msg)
    except: bot.reply_to(m, "❌ Ошибка")

@bot.message_handler(commands=['adminlist'])
def admin_list(m):
    uid = m.from_user.id
    if not is_admin(uid,3): bot.reply_to(m, "❌ Нет прав"); return
    txt = "👑 **АДМИНЫ**\n"
    for aid,lvl in ADMINS.items():
        ud = get_user_profile(aid)
        name = get_user_display_name(ud) if ud else f"ID: {aid}"
        txt += f"• {name} - ур.{lvl}\n"
    bot.reply_to(m, txt, parse_mode="Markdown")

@bot.message_handler(commands=['reset'])
def reset_account(m):
    uid = m.from_user.id
    if not is_admin(uid,3): bot.reply_to(m, "❌ Нет прав"); return
    try:
        target = m.text.split()[1]
        ud = find_user_by_input(target)
        if not ud: bot.reply_to(m, f"❌ {target} не найден"); return
        tid = ud[0]; name = get_user_display_name(ud)
        conn = get_db()
        conn.execute('DELETE FROM businesses WHERE user_id = ?', (tid,))
        conn.execute('DELETE FROM deliveries WHERE user_id = ?', (tid,))
        conn.execute('DELETE FROM user_clothes WHERE user_id = ?', (tid,))
        conn.execute('DELETE FROM user_cars WHERE user_id = ?', (tid,))
        conn.execute('DELETE FROM user_planes WHERE user_id = ?', (tid,))
        conn.execute('DELETE FROM travels WHERE user_id = ?', (tid,))
        conn.execute('DELETE FROM warns WHERE user_id = ?', (tid,))
        conn.execute('DELETE FROM bans WHERE user_id = ?', (tid,))
        conn.execute('DELETE FROM roulette_stats WHERE user_id = ?', (tid,))
        conn.execute('DELETE FROM work_stats WHERE user_id = ?', (tid,))
        conn.execute('UPDATE users SET balance=0, exp=0, level=1, work_count=0, total_earned=0, custom_name=NULL, equipped_clothes=NULL, current_city="Москва", has_car=0, has_plane=0, has_house=0, owned_house_id=NULL, house_purchase_price=0, house_purchase_city=NULL, closet_slots=5, next_slot_price=100000000 WHERE user_id=?', (tid,))
        conn.commit(); conn.close()
        if tid in WARNS: del WARNS[tid]
        if tid in BANS: del BANS[tid]
        try: bot.send_message(tid, "♻️ Аккаунт сброшен админом")
        except: pass
        bot.reply_to(m, f"✅ Аккаунт {name} обнулен")
    except: bot.reply_to(m, "❌ Формат: /reset [юзер]")

@bot.message_handler(commands=['wipe'])
def wipe_account(m):
    uid = m.from_user.id
    if not is_admin(uid,3): bot.reply_to(m, "❌ Нет прав"); return
    try:
        target = m.text.split()[1]
        ud = find_user_by_input(target)
        if not ud: bot.reply_to(m, f"❌ {target} не найден"); return
        tid = ud[0]; name = get_user_display_name(ud)
        conn = get_db()
        conn.execute('UPDATE users SET balance=0, exp=0, level=1 WHERE user_id=?', (tid,))
        conn.commit(); conn.close()
        try: bot.send_message(tid, "🧹 Баланс и опыт обнулены")
        except: pass
        bot.reply_to(m, f"✅ {name} обнулен")
    except: bot.reply_to(m, "❌ Формат: /wipe [юзер]")

@bot.message_handler(commands=['ban'])
def ban_user(m):
    uid = m.from_user.id
    if not is_admin(uid,4): bot.reply_to(m, "❌ Нет прав"); return
    try:
        p = m.text.split()
        if len(p) not in [2,3]: bot.reply_to(m, "❌ Формат: /ban [юзер] [часы]"); return
        target = p[1]; hours = int(p[2]) if len(p)==3 else 0
        ud = find_user_by_input(target)
        if not ud: bot.reply_to(m, f"❌ {target} не найден"); return
        tid = ud[0]; name = get_user_display_name(ud)
        if add_ban(tid, hours, "admin"):
            txt = "навсегда" if hours==0 else f"на {hours} ч."
            try: bot.send_message(tid, f"🔨 Вы забанены {txt}")
            except: pass
            bot.reply_to(m, f"✅ {name} забанен {txt}")
        else: bot.reply_to(m, "❌ Ошибка")
    except: bot.reply_to(m, "❌ Ошибка")

@bot.message_handler(commands=['unban'])
def unban_user(m):
    uid = m.from_user.id
    if not is_admin(uid,4): bot.reply_to(m, "❌ Нет прав"); return
    try:
        target = m.text.split()[1]
        ud = find_user_by_input(target)
        if not ud: bot.reply_to(m, f"❌ {target} не найден"); return
        tid = ud[0]; name = get_user_display_name(ud)
        if remove_ban(tid):
            try: bot.send_message(tid, "✅ Вы разбанены")
            except: pass
            bot.reply_to(m, f"✅ {name} разбанен")
        else: bot.reply_to(m, "❌ Ошибка")
    except: bot.reply_to(m, "❌ Формат: /unban [юзер]")

@bot.message_handler(commands=['warn'])
def warn_user(m):
    uid = m.from_user.id
    if not is_admin(uid,4): bot.reply_to(m, "❌ Нет прав"); return
    try:
        target = m.text.split()[1]
        ud = find_user_by_input(target)
        if not ud: bot.reply_to(m, f"❌ {target} не найден"); return
        tid = ud[0]; name = get_user_display_name(ud)
        banned, msg = add_warn(tid)
        try: bot.send_message(tid, msg)
        except: pass
        bot.reply_to(m, f"✅ Варн {name}\n{msg}")
    except: bot.reply_to(m, "❌ Формат: /warn [юзер]")

@bot.message_handler(commands=['warns'])
def show_warns(m):
    uid = m.from_user.id
    if not is_admin(uid,4): bot.reply_to(m, "❌ Нет прав"); return
    try:
        target = m.text.split()[1]
        ud = find_user_by_input(target)
        if not ud: bot.reply_to(m, f"❌ {target} не найден"); return
        w = get_warns(ud[0])
        bot.reply_to(m, f"⚠️ У {get_user_display_name(ud)} {w}/3 варнов")
    except: bot.reply_to(m, "❌ Формат: /warns [юзер]")

@bot.message_handler(commands=['removeadmin'])
def remove_admin_cmd(m):
    uid = m.from_user.id
    if not is_admin(uid,4): bot.reply_to(m, "❌ Нет прав"); return
    try:
        target = m.text.split()[1]
        ud = find_user_by_input(target)
        if not ud: bot.reply_to(m, f"❌ {target} не найден"); return
        tid = ud[0]; name = get_user_display_name(ud)
        if tid==5596589260: bot.reply_to(m, "❌ Нельзя снять главного"); return
        if remove_admin(tid):
            try: bot.send_message(tid, "👑 Права админа сняты")
            except: pass
            bot.reply_to(m, f"✅ Права сняты с {name}")
        else: bot.reply_to(m, "❌ Ошибка")
    except: bot.reply_to(m, "❌ Формат: /removeadmin [юзер]")

@bot.message_handler(commands=['setadminlevel'])
def set_admin_level_cmd(m):
    uid = m.from_user.id
    if not is_admin(uid,4): bot.reply_to(m, "❌ Нет прав"); return
    try:
        p = m.text.split()
        if len(p)!=3: bot.reply_to(m, "❌ Формат: /setadminlevel [юзер] [уровень]"); return
        target, lvl = p[1], int(p[2])
        if lvl<1 or lvl>4: bot.reply_to(m, "❌ Уровень 1-4"); return
        ud = find_user_by_input(target)
        if not ud: bot.reply_to(m, f"❌ {target} не найден"); return
        tid = ud[0]; name = get_user_display_name(ud)
        if tid==5596589260: bot.reply_to(m, "❌ Нельзя изменить главного"); return
        if set_admin_level(tid, lvl):
            try: bot.send_message(tid, f"👑 Ваш уровень админа изменен на {lvl}")
            except: pass
            bot.reply_to(m, f"✅ Уровень {name} изменен на {lvl}")
        else: bot.reply_to(m, "❌ Ошибка")
    except: bot.reply_to(m, "❌ Ошибка")

# ========== ТОП ==========
@bot.message_handler(commands=['top'])
def top_cmd(m):
    uid = m.from_user.id
    mk = types.InlineKeyboardMarkup(row_width=2).add(types.InlineKeyboardButton("💰 Деньги", callback_data="top_money"), types.InlineKeyboardButton("⭐ Опыт", callback_data="top_exp"))
    bot.send_message(uid, "🏆 **ВЫБЕРИ ТОП**", parse_mode="Markdown", reply_markup=mk)

def send_top_by_type(uid, typ):
    try:
        conn = get_db()
        if typ=="money":
            top = conn.execute('SELECT first_name, username, custom_name, balance FROM users ORDER BY balance DESC LIMIT 10').fetchall()
            title = "💰 ТОП 10 ПО ДЕНЬГАМ"
        else:
            top = conn.execute('SELECT first_name, username, custom_name, exp FROM users ORDER BY exp DESC LIMIT 10').fetchall()
            title = "⭐ ТОП 10 ПО ОПЫТУ"
        conn.close()
        if not top: bot.send_message(uid, "❌ Топ пуст"); return
        msg = f"🏆 **{title}**\n"
        for i,(fn,un,cn,val) in enumerate(top,1):
            medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
            name = cn or (f"@{un}" if un and un!="NoUsername" else fn)
            msg += f"{medal} {name}: {val:,}\n"
        bot.send_message(uid, msg, parse_mode="Markdown")
    except: bot.send_message(uid, "❌ Ошибка")

# ========== СТАРТ ==========
@bot.message_handler(commands=['start'])
def start(m):
    uid = m.from_user.id
    if is_banned(uid): ban = BANS.get(uid,{}); bot.reply_to(m, f"🔨 Забанен {'навсегда' if ban.get('until')==0 else 'до '+datetime.fromtimestamp(ban['until']).strftime('%d.%m.%Y %H:%M')}"); return
    uname = m.from_user.username or "NoUsername"
    fname = m.from_user.first_name
    conn = get_db()
    if not conn.execute('SELECT * FROM users WHERE user_id = ?', (uid,)).fetchone():
        conn.execute('INSERT INTO users (user_id, username, first_name, balance, exp, level, work_count, total_earned, current_city) VALUES (?,?,?,0,0,1,0,0,?)', (uid, uname, fname, 'Москва'))
        conn.commit(); conn.close()
        bot.send_message(uid, "🌟 **ДОБРО ПОЖАЛОВАТЬ!**\n\n✨ Выбери никнейм:", parse_mode="Markdown")
        bot.register_next_step_handler(bot.send_message(uid, "🔤 Напиши никнейм:", reply_markup=types.ForceReply()), process_name_step)
    else:
        conn.close()
        lvl = get_admin_level(uid)
        bot.send_message(uid, f"👋 С возвращением, {fname}!" + (f"\n👑 Админ {lvl} уровня" if lvl>0 else ""))
        send_main_menu_with_profile(uid)

def process_name_step(m):
    uid = m.from_user.id; name = m.text.strip()
    if len(name)<2 or len(name)>30: bot.send_message(uid, "❌ От 2 до 30 символов"); bot.register_next_step_handler(m, process_name_step); return
    if not all(c in set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_ -!@#$%^&*()") for c in name):
        bot.send_message(uid, "❌ Недопустимые символы"); bot.register_next_step_handler(m, process_name_step); return
    if get_user_by_custom_name(name):
        bot.send_message(uid, f"❌ Ник {name} занят"); bot.register_next_step_handler(m, process_name_step); return
    if set_custom_name(uid, name):
        bot.send_message(uid, f"✅ Ник {name} сохранен!\n\n👇 Твоё меню:", parse_mode="Markdown")
        send_main_menu_with_profile(uid)
    else:
        bot.send_message(uid, "❌ Ошибка"); bot.register_next_step_handler(m, process_name_step)

def change_nickname_step(m):
    uid = m.from_user.id; nn = m.text.strip()
    if len(nn)<2 or len(nn)>30: bot.send_message(uid, "❌ От 2 до 30"); bot.register_next_step_handler(m, change_nickname_step); return
    if not all(c in set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_ -!@#$%^&*()") for c in nn):
        bot.send_message(uid, "❌ Недопустимые символы"); bot.register_next_step_handler(m, change_nickname_step); return
    if get_user_by_custom_name(nn):
        bot.send_message(uid, f"❌ Ник {nn} занят"); bot.register_next_step_handler(m, change_nickname_step); return
    ud = get_user_profile(uid); old = ud[3] if ud and ud[3] else "Не установлен"
    if set_custom_name(uid, nn):
        bot.send_message(uid, f"✅ Ник изменен!\n🔄 {old} → {nn}", reply_markup=settings_keyboard())
    else:
        bot.send_message(uid, "❌ Ошибка"); bot.register_next_step_handler(m, change_nickname_step)

# ========== ОСНОВНОЙ ОБРАБОТЧИК ==========
@bot.message_handler(func=lambda m: True)
def handle(m):
    uid = m.from_user.id
    txt = m.text
    
    if is_banned(uid):
        ban = BANS.get(uid,{})
        bot.reply_to(m, f"🔨 Забанен {'навсегда' if ban.get('until')==0 else 'до '+datetime.fromtimestamp(ban['until']).strftime('%d.%m.%Y %H:%M')}")
        return
    
    print(f"{txt} от {uid}")
    
    try:
        conn = get_db()
        conn.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (uid,))
        conn.commit()
        conn.close()
    except:
        pass
    
    ud = get_user_profile(uid)
    dname = get_user_display_name(ud) if ud else "Игрок"
    
    # Проверка активной поездки
    at = get_active_travel(uid)
    if at:
        et = datetime.fromisoformat(at['end_time'])
        if datetime.now() >= et:
            complete_travel(at['id'], uid)
        else:
            bot.reply_to(m, f"⏳ В пути! Осталось {(et-datetime.now()).seconds} сек.", reply_markup=types.ReplyKeyboardRemove())
            return
    
    # Главное меню
    if txt == "💼 Работы":
        bot.send_message(uid, "🔨 Выбери работу:", reply_markup=jobs_keyboard(uid))
    
    elif txt == "🏭 Бизнесы":
        bot.send_message(uid, "🏪 Управление:", reply_markup=businesses_main_keyboard())
    
    elif txt == "👕 Магазин одежды":
        city = get_user_city(uid)
        ci = get_city_info(city)
        if ci and ci['shop_type']=='clothes':
            c, p, t = get_clothes_page(0)
            if c:
                bot.send_message(uid, "🛍️ **МАГАЗИН ОДЕЖДЫ**", parse_mode="Markdown")
                bot.send_photo(uid, c['photo_url'], caption=f"👕 *{c['name']}*\n💰 {c['price']:,}", parse_mode="Markdown", reply_markup=get_clothes_navigation_keyboard(p,t))
            else:
                bot.send_message(uid, "❌ Товаров нет")
        else:
            bot.send_message(uid, f"❌ В {city} нет магазина одежды")
    
    elif txt == "🎁 Ежедневно":
        try:
            conn = get_db()
            last = conn.execute('SELECT last_daily FROM users WHERE user_id = ?', (uid,)).fetchone()
            if last and last[0]:
                lt = datetime.fromisoformat(last[0])
                if datetime.now()-lt < timedelta(hours=24):
                    nxt = lt+timedelta(hours=24)
                    left = nxt-datetime.now()
                    bot.send_message(uid, f"⏳ Через {left.seconds//3600}ч {(left.seconds%3600)//60}м")
                    conn.close()
                    return
            bonus = random.randint(500,2000)
            bexp = random.randint(50,200)
            conn.execute('UPDATE users SET balance = balance + ?, exp = exp + ?, last_daily = ? WHERE user_id = ?', (bonus, bexp, datetime.now().isoformat(), uid))
            conn.commit()
            conn.close()
            bot.send_message(uid, f"🎁 +{bonus}💰 +{bexp}⭐!")
        except:
            bot.send_message(uid, "❌ Ошибка")
    
    elif txt == "🗺️ Карта":
        bot.send_message(uid, "🗺️ **ВЫБЕРИ ГОРОД**\n\n🏙️ Москва - 👕 Одежда\n🏙️ Село Молочное - 🚗 Машины\n🏙️ Кропоткин - ✈️ Самолеты\n🏙️ Мурино - 🏠 Дома", parse_mode="Markdown", reply_markup=cities_keyboard())
    
    elif txt == "🏠 Мой дом":
        house_data = get_user_house(uid)
        if not house_data:
            bot.send_message(uid, "🏠 У тебя нет дома! Отправляйся в Мурино и купи себе дом.")
        else:
            house = house_data['house']
            msg = (f"🏠 **{house['name']}**\n\n"
                   f"💰 Куплен за: {house_data['price']:,} {CURRENCY}\n"
                   f"📍 Город: {house_data['city']}\n"
                   f"🏡 Комфорт: {house['comfort']}\n\n"
                   f"👕 Слотов в шкафу: {ud['closet_slots']}")
            bot.send_photo(uid, house['photo_url'], caption=msg, parse_mode="Markdown", reply_markup=house_menu_keyboard())
    
    elif txt == "👕 Шкаф":
        house_data = get_user_house(uid)
        if not house_data:
            bot.send_message(uid, "🏠 Сначала купи дом в Мурино!")
            return
        
        clothes = get_user_closet(uid)
        stats = get_user_wardrobe_stats(uid)
        
        if not clothes:
            bot.send_message(uid, f"👕 Шкаф пуст. Купи одежду в Москве!\nСлотов: {stats['closet_slots']}\nЦена нового слота: {stats['next_slot_price']:,}💰", reply_markup=get_closet_navigation_keyboard(clothes, 0))
        else:
            msg = f"👕 **ТВОЙ ШКАФ**\nВсего вещей: {len(clothes)}/{stats['closet_slots']}\nЦена нового слота: {stats['next_slot_price']:,}💰"
            bot.send_message(uid, msg, reply_markup=get_closet_navigation_keyboard(clothes, 0))
    
    elif txt == "💰 Продать дом":
        res, msg = sell_house(uid)
        bot.send_message(uid, msg)
        if "✅" in msg or "💰" in msg:
            send_main_menu_with_profile(uid)
    
    elif txt == "⚙️ Настройки":
        bot.send_message(uid, "🔧 **НАСТРОЙКИ**", parse_mode="Markdown", reply_markup=settings_keyboard())
    
    elif txt == "🔄":
        ud = get_user_profile(uid)
        if ud:
            bot.send_photo(uid, get_user_profile_photo(uid), caption=f"👤 *{get_user_display_name(ud)}*\n💰 {get_balance(uid):,}", parse_mode="Markdown")
        else:
            bot.send_message(uid, "❌ Ошибка")
    
    # Города
    elif txt in ["🏙️ Москва","🏙️ Село Молочное","🏙️ Кропоткин","🏙️ Мурино"]:
        city = txt.replace("🏙️ ","")
        cur = get_user_city(uid)
        if city == cur:
            ci = get_city_info(city)
            bot.send_message(uid, f"🏙️ Ты в {city}\n📌 Продают: {ci['shop_type']}", reply_markup=city_shop_keyboard(ci['shop_type']))
        else:
            bot.send_message(uid, f"🚀 Транспорт в {city}:", reply_markup=transport_keyboard(city))
            bot.register_next_step_handler(m, process_travel, city)
    
    # Магазины города
    elif txt == "👕 Смотреть одежду":
        c,p,t = get_clothes_page(0)
        if c:
            bot.send_photo(uid, c['photo_url'], caption=f"👕 *{c['name']}*\n💰 {c['price']:,}", parse_mode="Markdown", reply_markup=get_clothes_navigation_keyboard(p,t))
        else:
            bot.send_message(uid, "❌ Нет товаров")
    
    elif txt == "🚗 Смотреть машины":
        c,p,t = get_cars_page(0)
        if c:
            car = get_user_car(uid)
            msg = f"🚗 *{c['name']}*\n💰 {c['price']:,}\n⚡ Скорость: {c['speed']}"
            if car:
                msg += f"\n\n🚗 Твоя текущая машина: {car['name']}"
            bot.send_photo(uid, c['photo_url'], caption=msg, parse_mode="Markdown", reply_markup=get_cars_navigation_keyboard(p,t,'cars'))
        else:
            bot.send_message(uid, "❌ Нет машин")
    
    elif txt == "💰 Продать машину":
        res, msg = sell_car(uid)
        bot.send_message(uid, msg)
        if "✅" in msg or "💰" in msg:
            send_main_menu_with_profile(uid)
    
    elif txt == "✈️ Смотреть самолеты":
        c,p,t = get_planes_page(0)
        if c:
            plane = get_user_plane(uid)
            msg = f"✈️ *{c['name']}*\n💰 {c['price']:,}\n⚡ Скорость: {c['speed']}"
            if plane:
                msg += f"\n\n✈️ Твой текущий самолет: {plane['name']}"
            bot.send_photo(uid, c['photo_url'], caption=msg, parse_mode="Markdown", reply_markup=get_cars_navigation_keyboard(p,t,'planes'))
        else:
            bot.send_message(uid, "❌ Нет самолетов")
    
    elif txt == "💰 Продать самолет":
        res, msg = sell_plane(uid)
        bot.send_message(uid, msg)
        if "✅" in msg or "💰" in msg:
            send_main_menu_with_profile(uid)
    
    elif txt == "🏠 Смотреть дома":
        c,p,t = get_houses_page(0)
        if c:
            bot.send_photo(uid, c['photo_url'], caption=f"🏠 *{c['name']}*\n💰 {c['price']:,}\n🏡 Комфорт: {c['comfort']}", parse_mode="Markdown", reply_markup=get_houses_navigation_keyboard(p,t,'houses'))
        else:
            bot.send_message(uid, "❌ Нет домов")
    
    elif txt == "🏪 Купить бизнес":
        bot.send_message(uid, "Выбери бизнес:", reply_markup=buy_business_keyboard())
    
    elif txt in ["🥤 Киоск","🍔 Фастфуд","🏪 Минимаркет","⛽ Заправка","🏨 Отель"]:
        if get_user_business(uid):
            bot.send_message(uid, "❌ Уже есть бизнес")
            return
        d = get_business_data(txt)
        if d:
            msg = (f"{d['emoji']} **{d['name']}**\n\n"
                   f"💰 Цена: {d['price']:,}\n"
                   f"📦 Сырьё: {d['raw_cost_per_unit']:,} за 1 шт\n"
                   f"💵 Прибыль: {d['profit_per_raw']:,} с 1 сырья\n"
                   f"⏱️ Время: {d['base_time']} сек\n"
                   f"📝 {d['description']}")
            bot.send_photo(uid, d['photo_url'], caption=msg, parse_mode="Markdown", reply_markup=get_business_buy_keyboard(txt))
        else:
            bot.send_message(uid, "❌ Ошибка")
    
    # РАБОТЫ
    elif any(job in txt for job in ["🚚 Грузчик","🧹 Уборщик","📦 Курьер","🔧 Механик","💻 Программист","🕵️ Детектив","👨‍🔧 Инженер","👨‍⚕️ Врач","👨‍🎤 Артист","👨‍🚀 Космонавт"]):
        job_name = txt
        ok, rem = check_cooldown(uid, job_name)
        if not ok:
            bot.send_message(uid, f"⏳ Подожди еще {rem} сек!")
            return
        
        if "Грузчик" in job_name:
            mk, msg = start_loader_game(uid, job_name)
            bot.send_message(uid, msg, reply_markup=mk)
        elif "Уборщик" in job_name:
            mk, msg = start_cleaner_game(uid, job_name)
            bot.send_message(uid, msg, reply_markup=mk)
        elif "Курьер" in job_name:
            mk, msg = start_courier_game(uid, job_name)
            bot.send_message(uid, msg, reply_markup=mk)
        elif "Механик" in job_name:
            mk, msg = start_mechanic_game(uid, job_name)
            bot.send_message(uid, msg, reply_markup=mk)
        elif "Программист" in job_name:
            mk, msg = start_programmer_game(uid, job_name)
            bot.send_message(uid, msg, parse_mode="Markdown", reply_markup=mk)
        elif "Детектив" in job_name:
            mk, msg = start_detective_game(uid, job_name)
            bot.send_message(uid, msg, reply_markup=mk)
        elif "Инженер" in job_name:
            mk, msg = start_engineer_game(uid, job_name)
            bot.send_message(uid, msg, reply_markup=mk)
        elif "Врач" in job_name:
            mk, msg = start_doctor_game(uid, job_name)
            bot.send_message(uid, msg, reply_markup=mk)
        elif "Артист" in job_name:
            mk, msg = start_artist_game(uid, job_name)
            bot.send_message(uid, msg, reply_markup=mk)
        elif "Космонавт" in job_name:
            mk, msg = start_cosmonaut_game(uid, job_name)
            bot.send_message(uid, msg, reply_markup=mk)
    
    elif txt == "👥 Рефералы":
        link = f"https://t.me/{bot.get_me().username}?start={uid}"
        bot.send_message(uid, f"👥 **РЕФЕРАЛЫ**\n🔗 {link}\n\n💡 За друга +1000💰 +50⭐", parse_mode="Markdown")
    
    elif txt == "📊 Мой бизнес":
        biz = get_user_business(uid)
        if not biz:
            bot.send_message(uid, "📭 Нет бизнеса")
            return
        d = get_business_data(biz['business_name'])
        if not d:
            bot.send_message(uid, "❌ Ошибка")
            return
        sp = {1:1.0,2:1.2,3:2.0}
        cs = sp.get(biz['level'],1.0)
        tpr = d['base_time']/cs
        total = biz['raw_material']+biz['raw_in_delivery']
        pot = biz['raw_material']*d['profit_per_raw']
        msg = f"{d['emoji']} **{biz['business_name']}**\n📊 Ур.{biz['level']}\n⏱️ {tpr:.0f} сек/сырьё\n📦 {biz['raw_material']}/1000\n🚚 {biz['raw_in_delivery']}\n📊 {total}/1000\n💰 Прибыль: {biz['stored_profit']:,}\n💵 Вложено: {biz['total_invested']:,}\n🎯 Потенциал: {pot:,}"
        if d['photo_url']:
            bot.send_photo(uid, d['photo_url'], caption=msg, parse_mode="Markdown")
        else:
            bot.send_message(uid, msg, parse_mode="Markdown")
    
    elif txt == "💰 Собрать прибыль":
        biz = get_user_business(uid)
        if not biz:
            bot.send_message(uid, "📭 Нет бизнеса")
            return
        if biz['stored_profit']<=0:
            bot.send_message(uid, "❌ Нет прибыли")
            return
        prof = biz['stored_profit']
        conn = get_db()
        conn.execute('UPDATE businesses SET stored_profit = 0 WHERE user_id = ?', (uid,))
        conn.commit()
        conn.close()
        add_balance(uid, prof)
        bot.send_message(uid, f"✅ Собрано {prof:,}💰")
    
    elif txt == "📦 Закупить на всё":
        biz = get_user_business(uid)
        if not biz:
            bot.send_message(uid, "❌ Нет бизнеса")
            return
        d = get_business_data(biz['business_name'])
        if not d:
            bot.send_message(uid, "❌ Ошибка")
            return
        bal = get_balance(uid)
        cost = d['raw_cost_per_unit']
        maxb = bal//cost
        total = biz['raw_material']+biz['raw_in_delivery']
        free = 1000-total
        amt = min(maxb, free)
        if amt<=0:
            bot.send_message(uid, f"❌ {'Склад полон' if free<=0 else f'Нужно {cost:,}💰'}")
            return
        tc = amt*cost
        if not add_balance(uid, -tc):
            bot.send_message(uid, "❌ Ошибка")
            return
        if has_active_delivery(uid):
            bot.send_message(uid, "❌ Уже есть доставка")
            add_balance(uid, tc)
            return
        conn = get_db()
        conn.execute('INSERT INTO deliveries (user_id, amount, end_time, delivered) VALUES (?,?,?,0)', (uid, amt, (datetime.now()+timedelta(minutes=15)).isoformat()))
        conn.execute('UPDATE businesses SET raw_in_delivery = raw_in_delivery + ?, total_invested = total_invested + ? WHERE user_id = ?', (amt, tc, uid))
        conn.commit()
        conn.close()
        bot.send_message(uid, f"✅ Заказ на {amt} сырья!\n💰 {tc:,}\n📦 Будет: {total+amt}/1000\n⏱️ 15 мин")
    
    elif txt == "💰 Продать бизнес":
        biz = get_user_business(uid)
        if not biz:
            bot.send_message(uid, "❌ Нет бизнеса")
            return
        d = get_business_data(biz['business_name'])
        if not d:
            bot.send_message(uid, "❌ Ошибка")
            return
        price = d['price']//2
        if add_balance(uid, price):
            conn = get_db()
            conn.execute('DELETE FROM businesses WHERE user_id = ?', (uid,))
            conn.execute('DELETE FROM deliveries WHERE user_id = ?', (uid,))
            conn.commit()
            conn.close()
            bot.send_message(uid, f"💰 Продано за {price:,}!")
        else:
            bot.send_message(uid, "❌ Ошибка")
    
    elif txt == "📊 Статистика":
        e,l,wc,t = get_user_stats(uid)
        eq = get_user_equipped_clothes(uid)
        ci = f", одет: {eq['name']}" if eq else ""
        bot.send_message(uid, f"📊 **СТАТИСТИКА**\n👤 {dname}{ci}\n📍 {get_user_city(uid)}\n⭐ {e}\n📈 Ур.{l}\n🔨 {wc}\n💵 {t:,}", parse_mode="Markdown")
    
    elif txt == "✏️ Сменить никнейм":
        cur = dname if dname!="Игрок" else "Не установлен"
        bot.register_next_step_handler(bot.send_message(uid, f"🎮 **СМЕНА НИКА**\nТекущий: `{cur}`\n🔤 Новый ник:", parse_mode="Markdown"), change_nickname_step)
    
    elif txt == "📋 Помощь":
        bot.send_message(uid, "📚 **ПОМОЩЬ**\n💼 Работы - мини-игры\n🏭 Бизнесы - управление\n👕 Магазин одежды (Москва)\n🚗 Машины (С.Молочное)\n✈️ Самолеты (Кропоткин)\n🏠 Дома (Мурино)\n🏠 Мой дом - шкаф, продажа\n🎁 Ежедневно - бонус\n🗺️ Карта - города\n⚙️ Настройки - смена ника\n🔄 - профиль\n🎰 рул крас 1000 - рулетка\n📊 статистика - показатели\n🏆 /top - топ", parse_mode="Markdown")
    
    elif txt == "❓ Помощь":
        bot.send_message(uid, "💼 Работы\n🏭 Бизнесы\n👕 Магазин одежды\n🎁 Ежедневно\n🗺️ Карта\n🏠 Мой дом\n⚙️ Настройки\n🔄 - профиль\n🎰 рул крас 1000\n📊 статистика\n🏆 /top")
    
    elif txt == "🔙 Назад":
        send_main_menu_with_profile(uid)
    
    # Обработка команд в чате
    elif txt and (txt.lower().startswith('рул') or txt.lower().startswith('рулетка')):
        bi = parse_roulette_bet(txt)
        if not bi:
            bot.reply_to(m, "❌ Пример: рул крас 1000, рул чет все, рул 7 500")
            return
        bt, ba = bi
        bal = get_balance(uid)
        if ba == -1:
            ba = bal
        if bal < ba:
            bot.reply_to(m, f"❌ Не хватает! Баланс: {bal:,}")
            return
        if ba < 1:
            bot.reply_to(m, "❌ Минимум 1💰")
            return
        n = random.randint(0,36)
        res = get_roulette_result(n)
        win = check_roulette_win(n, bt, ba)
        if win > 0:
            add_balance(uid, win-ba)
            nb = get_balance(uid)
            update_roulette_stats(uid, ba, win)
            bot.send_message(m.chat.id, f"🎡 **РУЛЕТКА**\n👤 {m.from_user.first_name}\n💰 {ba:,} на {bet_name(bt)}\n{gen_anim(n)}\n🎯 {n} {res['emoji']} {res['name']}\n🎉 **ВЫИГРЫШ!** +{win:,}💰\n💎 Баланс: {nb:,}", parse_mode="Markdown")
        else:
            add_balance(uid, -ba)
            nb = get_balance(uid)
            update_roulette_stats(uid, ba, 0)
            bot.send_message(m.chat.id, f"🎡 **РУЛЕТКА**\n👤 {m.from_user.first_name}\n💰 {ba:,} на {bet_name(bt)}\n{gen_anim(n)}\n🎯 {n} {res['emoji']} {res['name']}\n😭 **ПРОИГРЫШ** -{ba:,}💰\n💎 Баланс: {nb:,}", parse_mode="Markdown")
    
    elif txt and txt.lower().strip() in ['статистика','стата','статс','моя статистика','моя стата','моя статс','общая статистика','статистика казино']:
        if txt.lower().strip() in ['общая статистика','статистика казино']:
            send_top_to_chat(m.chat.id)
        else:
            s = get_roulette_stats(uid)
            if not s:
                bot.reply_to(m, "📊 Еще не играл! Попробуй: рул крас 1000")
                return
            prof = s['total_win']-s['total_lose']
            ps = "+" if prof>=0 else ""
            wr = (s['wins']/s['games_played']*100) if s['games_played']>0 else 0
            bot.reply_to(m, f"🎰 **ТВОЯ СТАТИСТИКА**\n🎮 Игр: {s['games_played']}\n✅ Побед: {s['wins']} ({wr:.1f}%)\n❌ Поражений: {s['losses']}\n💰 Выиграно: {s['total_win']:,}\n💸 Проиграно: {s['total_lose']:,}\n📈 {ps}{prof:,}\n🏆 Макс.выигрыш: {s['biggest_win']:,}\n💔 Макс.проигрыш: {s['biggest_lose']:,}", parse_mode="Markdown")
    
    elif txt and txt.lower().strip() == 'я':
        send_profile_to_chat(m.chat.id, uid, uid)
    
    elif txt and txt.lower().strip() == 'сырье все':
        process_raw_order(uid, m.chat.id)
    
    elif txt and txt.lower().strip() == 'топ':
        send_top_to_chat(m.chat.id)

def process_travel(m, target_city):
    uid = m.from_user.id
    tr = m.text
    
    if tr == "🔙 Назад":
        send_main_menu_with_profile(uid)
        return
    
    if tr not in ["🚕 Такси","🚗 Личная машина","✈️ Личный самолет"]:
        bot.send_message(uid, "❌ Выбери транспорт")
        bot.register_next_step_handler(m, process_travel, target_city)
        return
    
    conn = get_db()
    u = conn.execute('SELECT has_car, has_plane FROM users WHERE user_id = ?', (uid,)).fetchone()
    conn.close()
    
    if tr == "🚗 Личная машина" and (not u or u['has_car']==0):
        bot.send_message(uid, "❌ Нет машины! Купи в Селе Молочном.")
        bot.send_message(uid, f"🚀 Транспорт в {target_city}:", reply_markup=transport_keyboard(target_city))
        bot.register_next_step_handler(m, process_travel, target_city)
        return
    
    if tr == "✈️ Личный самолет" and (not u or u['has_plane']==0):
        bot.send_message(uid, "❌ Нет самолета! Купи в Кропоткине.")
        bot.send_message(uid, f"🚀 Транспорт в {target_city}:", reply_markup=transport_keyboard(target_city))
        bot.register_next_step_handler(m, process_travel, target_city)
        return
    
    # Используем новую функцию с расчетом времени
    start_travel(uid, target_city, tr)

# ========== КОЛБЭКИ ==========
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id, "🔨 Забанен", show_alert=True)
        return
    
    data = call.data
    
    # Топ
    if data == "top_money":
        bot.delete_message(uid, call.message.message_id)
        send_top_by_type(uid, "money")
        bot.answer_callback_query(call.id)
        return
    elif data == "top_exp":
        bot.delete_message(uid, call.message.message_id)
        send_top_by_type(uid, "exp")
        bot.answer_callback_query(call.id)
        return
    
    # МИНИ-ИГРЫ
    if data.startswith("loader_"):
        num = int(data.split("_")[1])
        res = check_loader_click(uid, num)
        if not res:
            bot.answer_callback_query(call.id, "❌ Игра не найдена")
            return
        if res['win']:
            conn = get_db()
            job_data = conn.execute('SELECT min_reward, max_reward, exp_reward FROM jobs WHERE job_name = ?', ("🚚 Грузчик",)).fetchone()
            conn.close()
            min_r, max_r, exp_r = job_data[0], job_data[1], job_data[2]
            earn = random.randint(min_r, max_r)
            add_balance(uid, earn)
            add_exp(uid, exp_r)
            update_work_stats(uid, "Грузчик", res['score'], res['time'], earn)
            set_cooldown(uid, "🚚 Грузчик")
            bot.edit_message_text(f"✅ **ПОБЕДА!**\n⏱️ {res['time']:.1f} сек\n💰 +{earn}\n⭐ +{exp_r}", uid, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, f"✅ {res['collected']}/{res['total']}")
        return
    
    if data.startswith("cleaner_"):
        pos = int(data.split("_")[1])
        res = check_cleaner_click(uid, pos)
        if not res:
            bot.answer_callback_query(call.id, "❌ Игра не найдена")
            return
        if res['win']:
            conn = get_db()
            job_data = conn.execute('SELECT min_reward, max_reward, exp_reward FROM jobs WHERE job_name = ?', ("🧹 Уборщик",)).fetchone()
            conn.close()
            min_r, max_r, exp_r = job_data[0], job_data[1], job_data[2]
            earn = random.randint(min_r, max_r)
            add_balance(uid, earn)
            add_exp(uid, exp_r)
            update_work_stats(uid, "Уборщик", res['score'], res['time'], earn)
            set_cooldown(uid, "🧹 Уборщик")
            bot.edit_message_text(f"✅ **ПОБЕДА!**\n⏱️ {res['time']:.1f} сек\n💰 +{earn}\n⭐ +{exp_r}", uid, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, f"✅ {res['collected']}/{res['total']}")
        return
    
    if data.startswith("courier_"):
        parts = data.split("_")
        cor, rt = parts[1], int(parts[2])
        res = check_courier_choice(uid, cor, rt)
        if not res:
            bot.answer_callback_query(call.id, "❌ Игра не найдена")
            return
        if res['win']:
            conn = get_db()
            job_data = conn.execute('SELECT min_reward, max_reward, exp_reward FROM jobs WHERE job_name = ?', ("📦 Курьер",)).fetchone()
            conn.close()
            min_r, max_r, exp_r = job_data[0], job_data[1], job_data[2]
            earn = random.randint(min_r, max_r)
            add_balance(uid, earn)
            add_exp(uid, exp_r)
            update_work_stats(uid, "Курьер", res['score'], res['time'], earn)
            set_cooldown(uid, "📦 Курьер")
            bot.edit_message_text(f"✅ **ДОСТАВЛЕНО!**\n⏱️ {res['time']:.1f} сек\n💰 +{earn}\n⭐ +{exp_r}", uid, call.message.message_id)
        else:
            bot.edit_message_text("❌ **НЕУДАЧА**\nПопробуй еще!", uid, call.message.message_id)
        return
    
    if data.startswith("mechanic_"):
        parts = data.split("_")
        idx, part = int(parts[1]), int(parts[2])
        res = check_mechanic_click(uid, idx, part)
        if not res:
            bot.answer_callback_query(call.id, "❌ Игра не найдена")
            return
        if res.get('win'):
            conn = get_db()
            job_data = conn.execute('SELECT min_reward, max_reward, exp_reward FROM jobs WHERE job_name = ?', ("🔧 Механик",)).fetchone()
            conn.close()
            min_r, max_r, exp_r = job_data[0], job_data[1], job_data[2]
            earn = random.randint(min_r, max_r)
            add_balance(uid, earn)
            add_exp(uid, exp_r)
            update_work_stats(uid, "Механик", res['score'], res['time'], earn)
            set_cooldown(uid, "🔧 Механик")
            bot.edit_message_text(f"✅ **СОБРАНО!**\n⏱️ {res['time']:.1f} сек\n💰 +{earn}\n⭐ +{exp_r}", uid, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, f"✅ Прогресс: {res.get('progress',0)}/4")
        return
    
    if data.startswith("programmer_"):
        cor = data.split("_")[1]
        res = check_programmer_choice(uid, cor)
        if not res:
            bot.answer_callback_query(call.id, "❌ Игра не найдена")
            return
        if res['win']:
            conn = get_db()
            job_data = conn.execute('SELECT min_reward, max_reward, exp_reward FROM jobs WHERE job_name = ?', ("💻 Программист",)).fetchone()
            conn.close()
            min_r, max_r, exp_r = job_data[0], job_data[1], job_data[2]
            earn = random.randint(min_r, max_r)
            add_balance(uid, earn)
            add_exp(uid, exp_r)
            update_work_stats(uid, "Программист", res['score'], res['time'], earn)
            set_cooldown(uid, "💻 Программист")
            bot.edit_message_text(f"✅ **БАГ ИСПРАВЛЕН!**\n⏱️ {res['time']:.1f} сек\n📊 {res['score']}%\n💰 +{earn}\n⭐ +{exp_r}", uid, call.message.message_id)
        else:
            bot.edit_message_text("❌ **НЕПРАВИЛЬНО**\nПопробуй еще!", uid, call.message.message_id)
        return
    
    if data.startswith("detective_"):
        cor = data.split("_")[1]
        res = check_detective_choice(uid, cor)
        if not res:
            bot.answer_callback_query(call.id, "❌ Игра не найдена")
            return
        if res['win']:
            conn = get_db()
            job_data = conn.execute('SELECT min_reward, max_reward, exp_reward FROM jobs WHERE job_name = ?', ("🕵️ Детектив",)).fetchone()
            conn.close()
            min_r, max_r, exp_r = job_data[0], job_data[1], job_data[2]
            earn = random.randint(min_r, max_r)
            add_balance(uid, earn)
            add_exp(uid, exp_r)
            update_work_stats(uid, "Детектив", res['score'], res['time'], earn)
            set_cooldown(uid, "🕵️ Детектив")
            bot.edit_message_text(f"✅ **ПРЕСТУПНИК НАЙДЕН!**\n⏱️ {res['time']:.1f} сек\n💰 +{earn}\n⭐ +{exp_r}", uid, call.message.message_id)
        else:
            bot.edit_message_text("❌ **НЕПРАВИЛЬНО**\nПопробуй еще!", uid, call.message.message_id)
        return
    
    if data.startswith("engineer_"):
        color = data.split("_")[1]
        res = check_engineer_click(uid, color)
        if not res:
            bot.answer_callback_query(call.id, "❌ Игра не найдена")
            return
        if res.get('win'):
            conn = get_db()
            job_data = conn.execute('SELECT min_reward, max_reward, exp_reward FROM jobs WHERE job_name = ?', ("👨‍🔧 Инженер",)).fetchone()
            conn.close()
            min_r, max_r, exp_r = job_data[0], job_data[1], job_data[2]
            earn = random.randint(min_r, max_r)
            add_balance(uid, earn)
            add_exp(uid, exp_r)
            update_work_stats(uid, "Инженер", res['score'], res['time'], earn)
            set_cooldown(uid, "👨‍🔧 Инженер")
            bot.edit_message_text(f"✅ **СХЕМА СОБРАНА!**\n⏱️ {res['time']:.1f} сек\n💰 +{earn}\n⭐ +{exp_r}", uid, call.message.message_id)
        elif res.get('mem'):
            bot.answer_callback_query(call.id, f"⏳ Запоминай...")
        else:
            bot.answer_callback_query(call.id, f"✅ {res.get('prog',0)}/{res.get('total',5)}")
        return
    
    if data.startswith("doctor_"):
        parts = data.split("_")
        cor, lim = parts[1], int(parts[2])
        res = check_doctor_choice(uid, cor, lim)
        if not res:
            bot.answer_callback_query(call.id, "❌ Игра не найдена")
            return
        if res['win']:
            conn = get_db()
            job_data = conn.execute('SELECT min_reward, max_reward, exp_reward FROM jobs WHERE job_name = ?', ("👨‍⚕️ Врач",)).fetchone()
            conn.close()
            min_r, max_r, exp_r = job_data[0], job_data[1], job_data[2]
            earn = random.randint(min_r, max_r)
            add_balance(uid, earn)
            add_exp(uid, exp_r)
            update_work_stats(uid, "Врач", res['score'], res['time'], earn)
            set_cooldown(uid, "👨‍⚕️ Врач")
            bot.edit_message_text(f"✅ **ПАЦИЕНТ СПАСЕН!**\n⏱️ {res['time']:.1f} сек\n💰 +{earn}\n⭐ +{exp_r}", uid, call.message.message_id)
        else:
            bot.edit_message_text("❌ **ПАЦИЕНТ УМЕР**\nПопробуй еще!", uid, call.message.message_id)
        return
    
    if data.startswith("artist_"):
        cor = data.split("_")[1]
        res = check_artist_choice(uid, cor)
        if not res:
            bot.answer_callback_query(call.id, "❌ Игра не найдена")
            return
        if res['win']:
            conn = get_db()
            job_data = conn.execute('SELECT min_reward, max_reward, exp_reward FROM jobs WHERE job_name = ?', ("👨‍🎤 Артист",)).fetchone()
            conn.close()
            min_r, max_r, exp_r = job_data[0], job_data[1], job_data[2]
            earn = random.randint(min_r, max_r)
            add_balance(uid, earn)
            add_exp(uid, exp_r)
            update_work_stats(uid, "Артист", res['score'], res['time'], earn)
            set_cooldown(uid, "👨‍🎤 Артист")
            bot.edit_message_text(f"✅ **ПРАВИЛЬНО!**\n⏱️ {res['time']:.1f} сек\n💰 +{earn}\n⭐ +{exp_r}", uid, call.message.message_id)
        else:
            bot.edit_message_text("❌ **НЕ УГАДАЛ**\nПопробуй еще!", uid, call.message.message_id)
        return
    
    if data.startswith("cosmo_"):
        if data in ["cosmo_up","cosmo_down","cosmo_left","cosmo_right"]:
            direction = data.split("_")[1]
            res = check_cosmonaut_move(uid, direction)
            if not res:
                bot.answer_callback_query(call.id, "❌ Игра не найдена")
                return
            if res.get('win'):
                conn = get_db()
                job_data = conn.execute('SELECT min_reward, max_reward, exp_reward FROM jobs WHERE job_name = ?', ("👨‍🚀 Космонавт",)).fetchone()
                conn.close()
                min_r, max_r, exp_r = job_data[0], job_data[1], job_data[2]
                earn = random.randint(min_r, max_r)
                add_balance(uid, earn)
                add_exp(uid, exp_r)
                update_work_stats(uid, "Космонавт", res['score'], res['time'], earn)
                set_cooldown(uid, "👨‍🚀 Космонавт")
                bot.edit_message_text(f"✅ **МИССИЯ ВЫПОЛНЕНА!**\n⏱️ {res['time']:.1f} сек\n💰 +{earn}\n⭐ +{exp_r}", uid, call.message.message_id)
            elif res.get('moved'):
                bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=res['markup'])
                bot.answer_callback_query(call.id, f"⛽ Топливо: {res['collected']}/{res['total']}")
            elif res.get('invalid'):
                bot.answer_callback_query(call.id, "❌ Нельзя")
        else:
            bot.answer_callback_query(call.id, "🔄 Игра продолжается")
        return
    
    # МАГАЗИН ОДЕЖДЫ
    if data.startswith("shop_page_"):
        page = int(data.split("_")[2])
        c, cp, t = get_clothes_page(page)
        if c:
            cap = f"👕 *{c['name']}*\n💰 {c['price']:,}\n🛍️ {t}"
            try:
                bot.edit_message_media(types.InputMediaPhoto(media=c['photo_url'], caption=cap, parse_mode="Markdown"), uid, call.message.message_id, reply_markup=get_clothes_navigation_keyboard(cp,t))
            except:
                bot.send_photo(uid, c['photo_url'], caption=cap, parse_mode="Markdown", reply_markup=get_clothes_navigation_keyboard(cp,t))
                bot.delete_message(uid, call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("shop_buy_"):
        page = int(data.split("_")[2])
        c, cp, t = get_clothes_page(page)
        if c:
            # Проверяем наличие дома
            conn = get_db()
            has_house = conn.execute('SELECT owned_house_id FROM users WHERE user_id = ?', (uid,)).fetchone()['owned_house_id']
            if not has_house:
                conn.close()
                bot.answer_callback_query(call.id, "❌ Купи дом в Мурино, чтобы хранить одежду!", show_alert=True)
                return
            
            # Проверяем место в шкафу
            user = conn.execute('SELECT closet_slots FROM users WHERE user_id = ?', (uid,)).fetchone()
            owned_count = conn.execute('SELECT COUNT(*) as cnt FROM user_clothes WHERE user_id = ?', (uid,)).fetchone()['cnt']
            if owned_count >= user['closet_slots']:
                conn.close()
                bot.answer_callback_query(call.id, f"❌ В шкафу нет места! У тебя {user['closet_slots']} слотов.", show_alert=True)
                return
            
            # Проверяем, есть ли уже такой скин
            existing = conn.execute('SELECT id FROM user_clothes WHERE user_id = ? AND clothes_id = ?', (uid, c['id'])).fetchone()
            if existing:
                conn.close()
                bot.answer_callback_query(call.id, "❌ У тебя уже есть этот комплект!", show_alert=True)
                return
            conn.close()
            
            success, msg = buy_clothes(uid, c['id'])
            if success:
                cap = f"👕 *{c['name']}*\n💰 {c['price']:,}\n✅ КУПЛЕНО!"
                mk = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("◀️ В магазин", callback_data=f"shop_page_{cp}"), types.InlineKeyboardButton("❌ Закрыть", callback_data="shop_close"))
                try:
                    bot.edit_message_media(types.InputMediaPhoto(media=c['photo_url'], caption=cap, parse_mode="Markdown"), uid, call.message.message_id, reply_markup=mk)
                except:
                    pass
                bot.answer_callback_query(call.id, "✅ Куплено!", show_alert=True)
            else:
                bot.answer_callback_query(call.id, msg, show_alert=True)
        return
    
    # МАГАЗИН МАШИН
    if data.startswith("cars_page_"):
        page = int(data.split("_")[2])
        c, cp, t = get_cars_page(page)
        if c:
            car = get_user_car(uid)
            cap = f"🚗 *{c['name']}*\n💰 {c['price']:,}\n⚡ {c['speed']} км/ч\n🛍️ {t}"
            if car:
                cap += f"\n\n🚗 Твоя текущая машина: {car['name']}"
            try:
                bot.edit_message_media(types.InputMediaPhoto(media=c['photo_url'], caption=cap, parse_mode="Markdown"), uid, call.message.message_id, reply_markup=get_cars_navigation_keyboard(cp,t,'cars'))
            except:
                bot.send_photo(uid, c['photo_url'], caption=cap, parse_mode="Markdown", reply_markup=get_cars_navigation_keyboard(cp,t,'cars'))
                bot.delete_message(uid, call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("cars_buy_"):
        page = int(data.split("_")[2])
        c, cp, t = get_cars_page(page)
        if c:
            ok, msg = buy_car(uid, c['id'])
            if ok:
                bot.edit_message_text(f"✅ **КУПЛЕНО!**\n🚗 {c['name']}\n💰 {c['price']:,}", uid, call.message.message_id)
            else:
                bot.answer_callback_query(call.id, msg, show_alert=True)
        return
    
    # МАГАЗИН САМОЛЕТОВ
    if data.startswith("planes_page_"):
        page = int(data.split("_")[2])
        c, cp, t = get_planes_page(page)
        if c:
            plane = get_user_plane(uid)
            cap = f"✈️ *{c['name']}*\n💰 {c['price']:,}\n⚡ {c['speed']} км/ч\n🛍️ {t}"
            if plane:
                cap += f"\n\n✈️ Твой текущий самолет: {plane['name']}"
            try:
                bot.edit_message_media(types.InputMediaPhoto(media=c['photo_url'], caption=cap, parse_mode="Markdown"), uid, call.message.message_id, reply_markup=get_cars_navigation_keyboard(cp,t,'planes'))
            except:
                bot.send_photo(uid, c['photo_url'], caption=cap, parse_mode="Markdown", reply_markup=get_cars_navigation_keyboard(cp,t,'planes'))
                bot.delete_message(uid, call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("planes_buy_"):
        page = int(data.split("_")[2])
        c, cp, t = get_planes_page(page)
        if c:
            ok, msg = buy_plane(uid, c['id'])
            if ok:
                bot.edit_message_text(f"✅ **КУПЛЕНО!**\n✈️ {c['name']}\n💰 {c['price']:,}", uid, call.message.message_id)
            else:
                bot.answer_callback_query(call.id, msg, show_alert=True)
        return
    
    # МАГАЗИН ДОМОВ
    if data.startswith("houses_page_"):
        page = int(data.split("_")[2])
        c, cp, t = get_houses_page(page)
        if c:
            cap = f"🏠 *{c['name']}*\n💰 {c['price']:,}\n🏡 Комфорт: {c['comfort']}\n🛍️ {t}"
            try:
                bot.edit_message_media(types.InputMediaPhoto(media=c['photo_url'], caption=cap, parse_mode="Markdown"), uid, call.message.message_id, reply_markup=get_houses_navigation_keyboard(cp,t,'houses'))
            except:
                bot.send_photo(uid, c['photo_url'], caption=cap, parse_mode="Markdown", reply_markup=get_houses_navigation_keyboard(cp,t,'houses'))
                bot.delete_message(uid, call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("houses_buy_"):
        page = int(data.split("_")[2])
        c, cp, t = get_houses_page(page)
        if c:
            ok, msg = buy_house(uid, c['id'])
            if ok:
                bot.edit_message_text(f"✅ **КУПЛЕНО!**\n🏠 {c['name']}\n💰 {c['price']:,}", uid, call.message.message_id)
                bot.send_message(uid, "👕 Теперь у тебя есть дом! Можешь хранить одежду в шкафу.", reply_markup=main_keyboard())
            else:
                bot.answer_callback_query(call.id, msg, show_alert=True)
        return
    
    # ШКАФ
    if data.startswith("closet_page_"):
        page = int(data.split("_")[2])
        clothes = get_user_closet(uid)
        stats = get_user_wardrobe_stats(uid)
        msg = f"👕 **ТВОЙ ШКАФ**\nВсего вещей: {len(clothes)}/{stats['closet_slots']}\nЦена нового слота: {stats['next_slot_price']:,}💰"
        bot.edit_message_text(msg, uid, call.message.message_id, reply_markup=get_closet_navigation_keyboard(clothes, page))
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("closet_equip_"):
        user_clothes_id = int(data.split("_")[2])
        ok, msg = equip_clothes(uid, user_clothes_id)
        bot.answer_callback_query(call.id, msg, show_alert=True)
        if ok:
            # Обновляем отображение шкафа
            clothes = get_user_closet(uid)
            stats = get_user_wardrobe_stats(uid)
            msg = f"👕 **ТВОЙ ШКАФ**\nВсего вещей: {len(clothes)}/{stats['closet_slots']}\nЦена нового слота: {stats['next_slot_price']:,}💰"
            bot.edit_message_text(msg, uid, call.message.message_id, reply_markup=get_closet_navigation_keyboard(clothes, 0))
        return
    
    if data == "closet_buy_slot":
        ok, msg = buy_closet_slot(uid)
        if ok:
            clothes = get_user_closet(uid)
            stats = get_user_wardrobe_stats(uid)
            msg = f"👕 **ТВОЙ ШКАФ**\nВсего вещей: {len(clothes)}/{stats['closet_slots']}\nЦена нового слота: {stats['next_slot_price']:,}💰"
            bot.edit_message_text(msg, uid, call.message.message_id, reply_markup=get_closet_navigation_keyboard(clothes, 0))
        bot.answer_callback_query(call.id, msg, show_alert=True)
        return
    
    if data == "closet_back":
        house_data = get_user_house(uid)
        if house_data:
            house = house_data['house']
            msg = (f"🏠 **{house['name']}**\n\n"
                   f"💰 Куплен за: {house_data['price']:,} {CURRENCY}\n"
                   f"📍 Город: {house_data['city']}\n"
                   f"🏡 Комфорт: {house['comfort']}")
            stats = get_user_wardrobe_stats(uid)
            bot.edit_message_media(
                types.InputMediaPhoto(media=house['photo_url'], caption=msg, parse_mode="Markdown"),
                uid, call.message.message_id,
                reply_markup=house_menu_keyboard()
            )
        else:
            bot.delete_message(uid, call.message.message_id)
            send_main_menu_with_profile(uid)
        bot.answer_callback_query(call.id)
        return
    
    # ПОКУПКА БИЗНЕСА
    if data.startswith("buy_business_"):
        name = data.replace("buy_business_", "")
        if get_user_business(uid):
            bot.answer_callback_query(call.id, "❌ Уже есть бизнес", show_alert=True)
            return
        d = get_business_data(name)
        if not d:
            bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)
            return
        bal = get_balance(uid)
        if bal < d['price']:
            bot.answer_callback_query(call.id, f"❌ Нужно {d['price']-bal:,}💰", show_alert=True)
            return
        if add_balance(uid, -d['price']):
            conn = get_db()
            conn.execute('INSERT INTO businesses (user_id, business_name, level, raw_material, raw_in_delivery, raw_spent, total_invested, stored_profit, last_update) VALUES (?,?,1,0,0,0,0,0,?)', (uid, name, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            bot.delete_message(uid, call.message.message_id)
            bot.send_message(uid, f"✅ Куплено {name} за {d['price']:,}💰!", reply_markup=main_keyboard())
            bot.answer_callback_query(call.id, "✅ Покупка успешна!")
        else:
            bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)
        return
    
    if data == "cancel_buy_business":
        bot.delete_message(uid, call.message.message_id)
        bot.send_message(uid, "Выбери бизнес:", reply_markup=buy_business_keyboard())
        bot.answer_callback_query(call.id)
        return
    
    if data == "shop_close":
        bot.delete_message(uid, call.message.message_id)
        send_main_menu_with_profile(uid)
        bot.answer_callback_query(call.id)
        return
    
    if data == "noop":
        bot.answer_callback_query(call.id)
        return

# ========== ФОНОВЫЕ ПРОЦЕССЫ ==========
def check_travels():
    while True:
        try:
            conn = get_db()
            for t in conn.execute('SELECT * FROM travels WHERE completed = 0 AND end_time <= ?', (datetime.now().isoformat(),)).fetchall():
                conn.execute('UPDATE users SET current_city = ? WHERE user_id = ?', (t['to_city'], t['user_id']))
                conn.execute('UPDATE travels SET completed = 1 WHERE id = ?', (t['id'],))
                try:
                    bot.send_message(t['user_id'], f"✅ Прибыл в {t['to_city']}!", reply_markup=main_keyboard())
                except:
                    pass
                conn.commit()
            conn.close()
            time.sleep(5)
        except:
            time.sleep(5)

def process_raw_material():
    while True:
        try:
            conn = get_db()
            for b in conn.execute('SELECT * FROM businesses').fetchall():
                if b['raw_material']>0:
                    d = get_business_data(b['business_name'])
                    if d:
                        sp = {1:1.0,2:1.2,3:2.0}
                        cs = sp.get(b['level'],1.0)
                        tpr = d['base_time']/cs
                        lu = datetime.fromisoformat(b['last_update'])
                        tp = (datetime.now()-lu).total_seconds()
                        units = int(tp/tpr)
                        if units>0 and b['raw_material']>0:
                            proc = min(units, b['raw_material'])
                            prof = proc*d['profit_per_raw']
                            conn.execute('UPDATE businesses SET raw_material = raw_material - ?, raw_spent = raw_spent + ?, stored_profit = stored_profit + ?, last_update = ? WHERE user_id = ?', (proc, proc, prof, datetime.now().isoformat(), b['user_id']))
                            total = b['raw_spent']+proc
                            if total>=50000 and b['level']==1:
                                conn.execute('UPDATE businesses SET level = 2 WHERE user_id = ?', (b['user_id'],))
                                try:
                                    bot.send_message(b['user_id'], "🎉 Бизнес 2 ур.! Скорость +20%!")
                                except:
                                    pass
                            elif total>=200000 and b['level']==2:
                                conn.execute('UPDATE businesses SET level = 3 WHERE user_id = ?', (b['user_id'],))
                                try:
                                    bot.send_message(b['user_id'], "🎉 Бизнес 3 ур.! Скорость +100%!")
                                except:
                                    pass
                            conn.commit()
            conn.close()
            time.sleep(10)
        except:
            time.sleep(10)

def check_deliveries():
    while True:
        try:
            conn = get_db()
            for d in conn.execute('SELECT * FROM deliveries WHERE delivered = 0 AND end_time <= ?', (datetime.now().isoformat(),)).fetchall():
                conn.execute('UPDATE businesses SET raw_material = raw_material + ?, raw_in_delivery = raw_in_delivery - ? WHERE user_id = ?', (d['amount'], d['amount'], d['user_id']))
                conn.execute('UPDATE deliveries SET delivered = 1 WHERE id = ?', (d['id'],))
                try:
                    b = get_user_business(d['user_id'])
                    if b:
                        bot.send_message(d['user_id'], f"✅ Сырье доставлено!\n📦 +{d['amount']}\n📦 Теперь: {b['raw_material']+d['amount']}/1000")
                except:
                    pass
                conn.commit()
            conn.close()
            time.sleep(30)
        except:
            time.sleep(30)

threading.Thread(target=process_raw_material, daemon=True).start()
threading.Thread(target=check_deliveries, daemon=True).start()
threading.Thread(target=check_travels, daemon=True).start()

# ========== ЗАПУСК ==========
from flask import Flask
from threading import Thread

app = Flask('')
@app.route('/')
def home(): return "Бот работает!"
def run(): app.run(host='0.0.0.0', port=8080)
threading.Thread(target=run, daemon=True).start()

print("✅ Бот запущен!")
print(f"👑 Админов: {len(ADMINS)}")
print(f"🏙️ Города: Москва(👕), С.Молочное(🚗), Кропоткин(✈️), Мурино(🏠)")
print(f"🎮 Все 10 работ с мини-играми и перезарядкой 7 сек!")
print(f"🏠 Система домов и шкафа активирована!")
print(f"🚗 Магазин машин: 9 моделей")
print(f"✈️ Магазин самолетов: 9 моделей")
print(f"⚙️ В главном меню кнопка 'Мой дом'")
print("🔄 - профиль (не трогает меню)")
bot.infinity_polling()
