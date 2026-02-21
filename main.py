import telebot
import sqlite3
import random
import os
from datetime import datetime, timedelta
from telebot import types
import threading
import time
import re
from flask import Flask
from threading import Thread

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

# ✅ ИСПРАВЛЕНО: каждое объявление на отдельной строке
loader_games = {}
cleaner_games = {}
courier_games = {}
mechanic_games = {}programmer_games = {}
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
            job_name TEXT UNIQUE,            min_exp INTEGER,
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
            name TEXT NOT NULL,            price INTEGER NOT NULL,
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
        CREATE TABLE IF NOT EXISTS admins (            user_id INTEGER PRIMARY KEY,
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
            ("Развалюха", 10_000_000, "https://iimg.su/i/kqaEfh", 30),
            ("Жигули", 50_000_000, "https://iimg.su/i/C53UkD", 50),
            ("Ауди", 50_000_000, "https://iimg.su/i/v5CjqO", 55),
            ("Хендай", 300_000_000, "https://iimg.su/i/ajQsBS", 80),
            ("Крузак-300", 600_000_000, "https://iimg.su/i/gwyWEO", 100),
            ("Мерседес-Акула", 777_777_777, "https://iimg.su/i/CSVixs", 120),            ("БЭМЭВЭ", 1_000_000_000, "https://iimg.su/i/F2Jfb4", 150),
            ("Мерседес-ГелентВаген", 1_000_000_000, "https://iimg.su/i/Lsmr1y", 140),
            ("РолсРойс", 7_777_777_777, "https://iimg.su/i/T8Uji6", 200)
        ]
        cursor.executemany('''
            INSERT INTO shop_cars (name, price, photo_url, speed)
            VALUES (?, ?, ?, ?)
        ''', cars_data)
    
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
    
    businesses_data = [
        ("🥤 Киоск", 500_000, "🥤", 1_000, 2_000, 60, "https://th.bing.com/th/id/R.4634fab1300b0376abe417c30426a9b7?rik=xcaYMuQThvYHig&riu=http%3a%2f%2fidei-biz.com%2fwp-content%2fuploads%2f2015%2f04%2fkak-otkryt-kiosk.gif&ehk=Vgms8Tfzm6kKm5Me0BE8ByekknYG3Df%2fjHuMD3NjPGM%3d&risl=&pid=ImgRaw&r=0", "Маленький киоск с напитками и снеками"),
        ("🍔 Фастфуд", 5_000_000, "🍔", 2_500, 5_000, 60, "https://tse1.mm.bing.net/th/id/OIP.HEYen4QlXTiaZzGiYuutCQHaEc?cb=defcache2&defcache=1&rs=1&pid=ImgDetMain&o=7&rm=3", "Бургерная с быстрым обслуживанием"),
        ("🏪 Минимаркет", 15_000_000, "🏪", 30_000, 60_000, 60, "https://tse1.mm.bing.net/th/id/OIP.JQQSzTluO8SxcChv5ZrjWAHaE7?cb=defcache2&defcache=1&rs=1&pid=ImgDetMain&o=7&rm=3", "Небольшой магазин у дома"),
        ("⛽ Заправка", 50_000_000, "⛽", 200_000, 400_000, 60, "https://th.bing.com/th/id/R.1b578b96a209d5a4b42fafe640c98c06?rik=fhxZHgYsQRp5Yw&riu=http%3a%2f%2fcdn.motorpage.ru%2fPhotos%2f800%2f213FE.jpg&ehk=kQHdWpflr8ztgGn9DA3XNkz%2fkSj6dzlVhm3%2biuromWk%3d&risl=&pid=ImgRaw&r=0", "Автозаправочная станция"),        ("🏨 Отель", 1_000_000_000, "🏨", 1_000_000, 2_000_000, 120, "https://tse1.mm.bing.net/th/id/OIP.oa6wkUpT9KjcmuimacYq3gHaE6?cb=defcache2&defcache=1&rs=1&pid=ImgDetMain&o=7&rm=3", "Роскошный отель для богатых клиентов")
    ]
    
    for bd in businesses_
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
    
    for job in jobs_
        cursor.execute('''
            INSERT OR REPLACE INTO jobs (job_name, min_exp, min_reward, max_reward, exp_reward, emoji)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', job)
    
    conn.commit()
    conn.close()
    print("✅ База данных проверена/создана")

def load_admins_from_db():
    try:
        conn = get_db()
        cursor = conn.cursor()
        admins = cursor.execute('SELECT user_id, level FROM admins').fetchall()
        conn.close()
        
        admin_dict = {}
        for admin in admins:
            admin_dict[admin['user_id']] = admin['level']
        return admin_dict
    except Exception as e:
        print(f"Ошибка загрузки админов: {e}")
        return {5596589260: 4}

def load_bans_from_db():
    try:
        conn = get_db()        cursor = conn.cursor()
        bans = cursor.execute('SELECT user_id, reason, until FROM bans').fetchall()
        conn.close()
        
        ban_dict = {}
        for ban in bans:
            ban_dict[ban['user_id']] = {
                'reason': ban['reason'],
                'until': ban['until']
            }
        return ban_dict
    except Exception as e:
        print(f"Ошибка загрузки банов: {e}")
        return {}

def load_warns_from_db():
    try:
        conn = get_db()
        cursor = conn.cursor()
        warns = cursor.execute('SELECT user_id, count FROM warns').fetchall()
        conn.close()
        
        warn_dict = {}
        for warn in warns:
            warn_dict[warn['user_id']] = warn['count']
        return warn_dict
    except Exception as e:
        print(f"Ошибка загрузки варнов: {e}")
        return {}

init_db()
ADMINS = load_admins_from_db()
BANS = load_bans_from_db()
WARNS = load_warns_from_db()

print(f"👑 Загружено админов: {len(ADMINS)}")
print(f"🔨 Загружено банов: {len(BANS)}")
print(f"⚠️ Загружено варнов: {len(WARNS)}")

def get_admin_level(user_id):
    if user_id in ADMINS:
        return ADMINS[user_id]
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        admin = cursor.execute('SELECT level FROM admins WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        
        if admin:            level = admin['level']
            ADMINS[user_id] = level
            return level
    except:
        pass
    
    return 0

def is_admin(user_id, required_level=1):
    return get_admin_level(user_id) >= required_level

def is_banned(user_id):
    if user_id in BANS:
        ban_info = BANS[user_id]
        if ban_info['until'] == 0:
            return True
        elif datetime.now().timestamp() < ban_info['until']:
            return True
        else:
            del BANS[user_id]
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
                conn.commit()
                conn.close()
            except:
                pass
            return False
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        ban = cursor.execute('SELECT until FROM bans WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        
        if ban:
            until = ban['until']
            if until == 0:
                BANS[user_id] = {'reason': 'unknown', 'until': 0}
                return True
            elif datetime.now().timestamp() < until:
                BANS[user_id] = {'reason': 'unknown', 'until': until}
                return True
            else:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
                conn.commit()
                conn.close()    except:
        pass
    
    return False

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

def get_user_stats(user_id):    try:
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

def get_user_by_custom_name(custom_name):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, first_name, username, custom_name, warns FROM users WHERE custom_name = ? COLLATE NOCASE', (custom_name,))
        user = cursor.fetchone()
        conn.close()
        return user
    except:
        return None

def get_user_display_name(user_data):
    if not user_
        return "Игрок"
    
    custom = user_data[3]
    username = user_data[2]
    
    if custom:
        if username and username != "NoUsername":
            return f"{custom} (@{username})"
        return custom
    elif username and username != "NoUsername":
        return f"@{username}"
    elif user_data[1]:
        return user_data[1]
    return "Игрок"

def set_custom_name(user_id, name):    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET custom_name = ? WHERE user_id = ?', (name, user_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f"Ошибка установки имени: {e}")
        return False

def get_available_jobs(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT exp FROM users WHERE user_id = ?', (user_id,))
        exp = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT job_name, min_exp, min_reward, max_reward, exp_reward, emoji 
            FROM jobs 
            WHERE min_exp <= ?
            ORDER BY min_exp ASC
        ''', (exp,))
        jobs = cursor.fetchall()
        conn.close()
        return jobs
    except Exception as e:
        print(f"Ошибка get_available_jobs: {e}")
        return []

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
        data = cursor.fetchone()        conn.close()
        return data
    except:
        return None

def has_active_delivery(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM deliveries WHERE user_id = ? AND delivered = 0', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result['count'] > 0
    except:
        return False

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
            SELECT sc.* FROM shop_clothes sc            JOIN user_clothes uc ON sc.id = uc.clothes_id
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
    if not user_
        return
    
    balance = get_balance(user_id)
    display_name = get_user_display_name(user_data)
    current_city = get_user_city(user_id)
    
    caption = (f"👤 *{display_name}*\n\n"
               f"💰 Баланс: {balance:,} {CURRENCY}\n"
               f"📍 Город: {current_city}")
    
    photo_url = get_user_profile_photo(user_id)
    
    bot.send_photo(
        chat_id,
        photo_url,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=main_keyboard_for_city(user_id)
    )

def buy_car(user_id, car_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        if cursor.execute('SELECT id FROM user_cars WHERE user_id = ?', (user_id,)).fetchone():
            conn.close()
            return False, "❌ У тебя уже есть машина!"
        
        car = cursor.execute('SELECT * FROM shop_cars WHERE id = ?', (car_id,)).fetchone()
        if not car:
            conn.close()
            return False, "❌ Машина не найдена"
        
        user = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if not user or user['balance'] < car['price']:
            conn.close()
            return False, f"❌ Недостаточно средств!"
        
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (car['price'], user_id))
        cursor.execute('INSERT INTO user_cars (user_id, car_id) VALUES (?, ?)', (user_id, car_id))
        cursor.execute('UPDATE users SET has_car = 1 WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        return True, f"✅ Купил {car['name']}!"
    except Exception as e:        print(f"Ошибка: {e}")
        return False, "❌ Ошибка"

def sell_car(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        car = cursor.execute('''
            SELECT sc.* FROM shop_cars sc
            JOIN user_cars uc ON sc.id = uc.car_id
            WHERE uc.user_id = ?
        ''', (user_id,)).fetchone()
        
        if not car:
            conn.close()
            return False, "❌ Нет машины"
        
        sell_price = car['price'] // 2
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (sell_price, user_id))
        cursor.execute('DELETE FROM user_cars WHERE user_id = ?', (user_id,))
        cursor.execute('UPDATE users SET has_car = 0 WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        return True, f"💰 Продал за {sell_price:,}"
    except Exception as e:
        print(f"Ошибка: {e}")
        return False, "❌ Ошибка"

def buy_plane(user_id, plane_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        if cursor.execute('SELECT id FROM user_planes WHERE user_id = ?', (user_id,)).fetchone():
            conn.close()
            return False, "❌ Уже есть самолет"
        
        plane = cursor.execute('SELECT * FROM shop_planes WHERE id = ?', (plane_id,)).fetchone()
        if not plane:
            conn.close()
            return False, "❌ Не найден"
        
        user = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if not user or user['balance'] < plane['price']:
            conn.close()
            return False, f"❌ Недостаточно средств!"
        
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (plane['price'], user_id))        cursor.execute('INSERT INTO user_planes (user_id, plane_id) VALUES (?, ?)', (user_id, plane_id))
        cursor.execute('UPDATE users SET has_plane = 1 WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        return True, f"✅ Купил {plane['name']}!"
    except Exception as e:
        return False, "❌ Ошибка"

def sell_plane(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        plane = cursor.execute('''
            SELECT sp.* FROM shop_planes sp
            JOIN user_planes up ON sp.id = up.plane_id
            WHERE up.user_id = ?
        ''', (user_id,)).fetchone()
        
        if not plane:
            conn.close()
            return False, "❌ Нет самолета"
        
        sell_price = plane['price'] // 2
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (sell_price, user_id))
        cursor.execute('DELETE FROM user_planes WHERE user_id = ?', (user_id,))
        cursor.execute('UPDATE users SET has_plane = 0 WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        return True, f"💰 Продал за {sell_price:,}"
    except:
        return False, "❌ Ошибка"

def buy_house(user_id, house_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        user = cursor.execute('SELECT owned_house_id, balance FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if user and user['owned_house_id']:
            conn.close()
            return False, "❌ Уже есть дом"
        
        house = cursor.execute('SELECT * FROM shop_houses WHERE id = ?', (house_id,)).fetchone()
        if not house:
            conn.close()
            return False, "❌ Не найден"
                if not user or user['balance'] < house['price']:
            conn.close()
            return False, f"❌ Недостаточно средств!"
        
        current_city = get_user_city(user_id)
        
        cursor.execute('UPDATE users SET balance = balance - ?, owned_house_id = ?, house_purchase_price = ?, house_purchase_city = ? WHERE user_id = ?', 
                      (house['price'], house_id, house['price'], current_city, user_id))
        cursor.execute('UPDATE users SET has_house = 1 WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        return True, f"✅ Купил {house['name']}!"
    except:
        return False, "❌ Ошибка"

def sell_house(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        user = cursor.execute('SELECT owned_house_id, house_purchase_price FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if not user or not user['owned_house_id']:
            conn.close()
            return False, "❌ Нет дома"
        
        house = cursor.execute('SELECT name FROM shop_houses WHERE id = ?', (user['owned_house_id'],)).fetchone()
        sell_price = user['house_purchase_price'] // 2
        
        cursor.execute('UPDATE users SET balance = balance + ?, owned_house_id = NULL, house_purchase_price = 0, house_purchase_city = NULL WHERE user_id = ?', 
                      (sell_price, user_id))
        cursor.execute('UPDATE users SET has_house = 0 WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        return True, f"💰 Продал за {sell_price:,}"
    except:
        return False, "❌ Ошибка"

def get_user_closet(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        clothes = cursor.execute('''
            SELECT sc.*, uc.id as user_clothes_id FROM shop_clothes sc
            JOIN user_clothes uc ON sc.id = uc.clothes_id
            WHERE uc.user_id = ? AND uc.equipped = 0
            ORDER BY uc.purchased_at DESC
        ''', (user_id,)).fetchall()
        conn.close()        return clothes
    except:
        return []

def get_user_wardrobe_stats(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        user = cursor.execute('SELECT closet_slots, next_slot_price FROM users WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        return user
    except:
        return None

def buy_closet_slot(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        user = cursor.execute('SELECT closet_slots, next_slot_price, balance FROM users WHERE user_id = ?', (user_id,)).fetchone()
        
        if not user or user['balance'] < user['next_slot_price']:
            conn.close()
            return False, f"❌ Недостаточно средств!"
        
        new_slots = user['closet_slots'] + 1
        new_price = user['next_slot_price'] + 100_000_000
        
        cursor.execute('UPDATE users SET balance = balance - ?, closet_slots = ?, next_slot_price = ? WHERE user_id = ?', 
                      (user['next_slot_price'], new_slots, new_price, user_id))
        
        conn.commit()
        conn.close()
        return True, f"✅ Купил слот! Теперь {new_slots}"
    except:
        return False, "❌ Ошибка"

def equip_clothes(user_id, user_clothes_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE user_clothes SET equipped = 0 WHERE user_id = ?', (user_id,))
        cursor.execute('UPDATE user_clothes SET equipped = 1 WHERE id = ?', (user_clothes_id,))
        
        clothes = cursor.execute('SELECT clothes_id FROM user_clothes WHERE id = ?', (user_clothes_id,)).fetchone()
        if clothes:
            cursor.execute('UPDATE users SET equipped_clothes = ? WHERE user_id = ?', (clothes['clothes_id'], user_id))
        
        conn.commit()        conn.close()
        return True, "✅ Надел!"
    except:
        return False, "❌ Ошибка"

def buy_clothes(user_id, clothes_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        clothes = cursor.execute('SELECT * FROM shop_clothes WHERE id = ?', (clothes_id,)).fetchone()
        if not clothes:
            conn.close()
            return False, "❌ Не найдено"
        
        user = cursor.execute('SELECT balance, closet_slots FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if not user or user['balance'] < clothes['price']:
            conn.close()
            return False, f"❌ Недостаточно средств!"
        
        has_house = cursor.execute('SELECT owned_house_id FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if not has_house or not has_house['owned_house_id']:
            conn.close()
            return False, "❌ Купи дом в Мурино!"
        
        owned_count = cursor.execute('SELECT COUNT(*) as cnt FROM user_clothes WHERE user_id = ?', (user_id,)).fetchone()
        if owned_count and owned_count['cnt'] >= user['closet_slots']:
            conn.close()
            return False, f"❌ Нет места в шкафу!"
        
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (clothes['price'], user_id))
        cursor.execute('INSERT INTO user_clothes (user_id, clothes_id, equipped) VALUES (?, ?, 0)', (user_id, clothes_id))
        
        conn.commit()
        conn.close()
        return True, f"✅ Купил {clothes['name']}!"
    except:
        return False, "❌ Ошибка"

def get_clothes_page(page=0):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM shop_clothes WHERE in_shop = 1 ORDER BY price')
        all_clothes = cursor.fetchall()
        conn.close()
        
        total = len(all_clothes)
        if total == 0:
            return None, 0, 0        
        if page < 0:
            page = 0
        elif page >= total:
            page = total - 1
        
        return all_clothes[page], page, total
    except:
        return None, 0, 0

def get_cars_page(page=0):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM shop_cars WHERE in_shop = 1 ORDER BY price')
        all_cars = cursor.fetchall()
        conn.close()
        
        total = len(all_cars)
        if total == 0:
            return None, 0, 0
        
        if page < 0:
            page = 0
        elif page >= total:
            page = total - 1
        
        return all_cars[page], page, total
    except:
        return None, 0, 0

def get_planes_page(page=0):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM shop_planes WHERE in_shop = 1 ORDER BY price')
        all_planes = cursor.fetchall()
        conn.close()
        
        total = len(all_planes)
        if total == 0:
            return None, 0, 0
        
        if page < 0:
            page = 0
        elif page >= total:
            page = total - 1
        
        return all_planes[page], page, total
    except:        return None, 0, 0

def get_houses_page(page=0):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM shop_houses WHERE in_shop = 1 ORDER BY price')
        all_houses = cursor.fetchall()
        conn.close()
        
        total = len(all_houses)
        if total == 0:
            return None, 0, 0
        
        if page < 0:
            page = 0
        elif page >= total:
            page = total - 1
        
        return all_houses[page], page, total
    except:
        return None, 0, 0

def get_clothes_navigation_keyboard(current_page, total_items):
    markup = types.InlineKeyboardMarkup(row_width=3)
    
    buttons = []
    if current_page > 0:
        buttons.append(types.InlineKeyboardButton("◀️", callback_data=f"shop_page_{current_page-1}"))
    else:
        buttons.append(types.InlineKeyboardButton("⬜️", callback_data="noop"))
    
    buttons.append(types.InlineKeyboardButton(f"🛒 Купить", callback_data=f"shop_buy_{current_page}"))
    
    if current_page < total_items - 1:
        buttons.append(types.InlineKeyboardButton("▶️", callback_data=f"shop_page_{current_page+1}"))
    else:
        buttons.append(types.InlineKeyboardButton("⬜️", callback_data="noop"))
    
    markup.row(*buttons)
    markup.row(types.InlineKeyboardButton("❌ Закрыть", callback_data="shop_close"))
    
    return markup

def get_cars_navigation_keyboard(current_page, total_items, shop_type):
    markup = types.InlineKeyboardMarkup(row_width=3)
    
    buttons = []
    if current_page > 0:
        buttons.append(types.InlineKeyboardButton("◀️", callback_data=f"{shop_type}_page_{current_page-1}"))    else:
        buttons.append(types.InlineKeyboardButton("⬜️", callback_data="noop"))
    
    buttons.append(types.InlineKeyboardButton(f"🛒 Купить", callback_data=f"{shop_type}_buy_{current_page}"))
    
    if current_page < total_items - 1:
        buttons.append(types.InlineKeyboardButton("▶️", callback_data=f"{shop_type}_page_{current_page+1}"))
    else:
        buttons.append(types.InlineKeyboardButton("⬜️", callback_data="noop"))
    
    markup.row(*buttons)
    markup.row(types.InlineKeyboardButton("❌ Закрыть", callback_data="shop_close"))
    
    return markup

def get_houses_navigation_keyboard(current_page, total_items, shop_type):
    markup = types.InlineKeyboardMarkup(row_width=3)
    
    buttons = []
    if current_page > 0:
        buttons.append(types.InlineKeyboardButton("◀️", callback_data=f"{shop_type}_page_{current_page-1}"))
    else:
        buttons.append(types.InlineKeyboardButton("⬜️", callback_data="noop"))
    
    buttons.append(types.InlineKeyboardButton(f"🏠 Купить", callback_data=f"{shop_type}_buy_{current_page}"))
    
    if current_page < total_items - 1:
        buttons.append(types.InlineKeyboardButton("▶️", callback_data=f"{shop_type}_page_{current_page+1}"))
    else:
        buttons.append(types.InlineKeyboardButton("⬜️", callback_data="noop"))
    
    markup.row(*buttons)
    markup.row(types.InlineKeyboardButton("❌ Закрыть", callback_data="shop_close"))
    
    return markup

def get_closet_navigation_keyboard(clothes_list, current_page):
    markup = types.InlineKeyboardMarkup(row_width=1)
    start_idx = current_page * 5
    end_idx = start_idx + 5
    page_items = clothes_list[start_idx:end_idx]
    
    for item in page_items:
        btn_text = f"👕 {item['name']}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"closet_equip_{item['user_clothes_id']}"))
    
    nav_buttons = []
    if current_page > 0:
        nav_buttons.append(types.InlineKeyboardButton("◀️", callback_data=f"closet_page_{current_page-1}"))
    if end_idx < len(clothes_list):        nav_buttons.append(types.InlineKeyboardButton("▶️", callback_data=f"closet_page_{current_page+1}"))
    if nav_buttons:
        markup.row(*nav_buttons)
    
    markup.row(types.InlineKeyboardButton("➕ Купить слот", callback_data="closet_buy_slot"))
    markup.row(types.InlineKeyboardButton("🔙 Назад", callback_data="closet_back"))
    
    return markup

def get_business_buy_keyboard(business_name):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Купить", callback_data=f"buy_business_{business_name}"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_buy_business")
    )
    return markup

def parse_bet_amount(amount_str):
    amount_str = amount_str.lower().strip()
    
    multipliers = {
        'к': 1000,
        'кк': 1000000,
        'ккк': 1000000000,
        'кккк': 1000000000000,
        'kk': 1000,
        'kkk': 1000000,
        'kkkk': 1000000000,
        'kkkkk': 1000000000000,
    }
    
    if amount_str in ['все', 'алл', 'максимум', 'всё', 'all', 'max']:
        return -1
    
    for suffix, multiplier in multipliers.items():
        if amount_str.endswith(suffix):
            try:
                num = float(amount_str[:-len(suffix)])
                return int(num * multiplier)
            except:
                pass
    
    try:
        return int(amount_str)
    except:
        return None

def parse_roulette_bet(text):
    text = text.lower().strip()
    words = text.split()    
    if not words:
        return None
    
    if not (words[0].startswith('рул') or words[0].startswith('рулетка')):
        return None
    
    if len(words) != 3:
        return None
    
    bet_word = words[1]
    bet_value = words[2]
    
    bet_amount = parse_bet_amount(bet_value)
    if bet_amount is None:
        return None
    
    bet_types = {
        'крас': 'red', 'красное': 'red',
        'чер': 'black', 'черное': 'black',
        'чет': 'even', 'четное': 'even',
        'нечет': 'odd', 'нечетное': 'odd',
        'бол': 'high', 'большое': 'high',
        'мал': 'low', 'маленькое': 'low',
        '1-12': '1-12',
        '13-24': '13-24',
        '25-36': '25-36',
        'зеро': '0',
    }
    
    for key, value in bet_types.items():
        if bet_word == key or bet_word in key.split():
            return (value, bet_amount)
    
    if bet_word.isdigit():
        num = int(bet_word)
        if 0 <= num <= 36:
            return (f'num_{num}', bet_amount)
    
    return None

def update_roulette_stats(user_id, bet_amount, win_amount):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        stats = cursor.execute('SELECT * FROM roulette_stats WHERE user_id = ?', (user_id,)).fetchone()
        
        if stats:
            games_played = stats['games_played'] + 1            total_bet = stats['total_bet'] + bet_amount
            wins = stats['wins'] + (1 if win_amount > 0 else 0)
            losses = stats['losses'] + (1 if win_amount == 0 else 0)
            total_win = stats['total_win'] + (win_amount if win_amount > 0 else 0)
            total_lose = stats['total_lose'] + (bet_amount if win_amount == 0 else 0)
            biggest_win = max(stats['biggest_win'], win_amount) if win_amount > 0 else stats['biggest_win']
            biggest_lose = max(stats['biggest_lose'], bet_amount) if win_amount == 0 else stats['biggest_lose']
            
            cursor.execute('''
                UPDATE roulette_stats 
                SET games_played = ?, wins = ?, losses = ?,
                    total_bet = ?, total_win = ?, total_lose = ?,
                    biggest_win = ?, biggest_lose = ?, last_game = ?
                WHERE user_id = ?
            ''', (games_played, wins, losses, total_bet, total_win, total_lose,
                  biggest_win, biggest_lose, datetime.now().isoformat(), user_id))
        else:
            wins = 1 if win_amount > 0 else 0
            losses = 1 if win_amount == 0 else 0
            biggest_win = win_amount if win_amount > 0 else 0
            biggest_lose = bet_amount if win_amount == 0 else 0
            
            cursor.execute('''
                INSERT INTO roulette_stats 
                (user_id, games_played, wins, losses, total_bet, total_win, total_lose, biggest_win, biggest_lose, last_game)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, 1, wins, losses, bet_amount, 
                  (win_amount if win_amount > 0 else 0), 
                  (bet_amount if win_amount == 0 else 0), 
                  biggest_win, biggest_lose, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка: {e}")
        return False

def get_roulette_stats(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        stats = cursor.execute('SELECT * FROM roulette_stats WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        return stats
    except:
        return None

def get_roulette_result(number):
    if number == 0:        return {'name': 'Зеро', 'emoji': '🟢', 'color': 'green'}
    
    red_numbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    if number in red_numbers:
        return {'name': 'Красное', 'emoji': '🔴', 'color': 'red'}
    else:
        return {'name': 'Черное', 'emoji': '⚫', 'color': 'black'}

def check_roulette_win(number, bet_type, bet_amount):
    red_numbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    black_numbers = [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35]
    
    if bet_type == 'red' and number in red_numbers:
        return bet_amount * 2
    elif bet_type == 'black' and number in black_numbers:
        return bet_amount * 2
    elif bet_type == 'even' and number != 0 and number % 2 == 0:
        return bet_amount * 2
    elif bet_type == 'odd' and number % 2 == 1:
        return bet_amount * 2
    elif bet_type == 'high' and 19 <= number <= 36:
        return bet_amount * 2
    elif bet_type == 'low' and 1 <= number <= 18:
        return bet_amount * 2
    elif bet_type == '1-12' and 1 <= number <= 12:
        return bet_amount * 3
    elif bet_type == '13-24' and 13 <= number <= 24:
        return bet_amount * 3
    elif bet_type == '25-36' and 25 <= number <= 36:
        return bet_amount * 3
    elif bet_type == '0' and number == 0:
        return bet_amount * 36
    elif bet_type.startswith('num_'):
        target = int(bet_type.split('_')[1])
        if number == target:
            return bet_amount * 36
    
    return 0

def generate_animation(final_number):
    numbers = []
    for _ in range(5):
        numbers.append(str(random.randint(0, 36)))
    numbers.append(str(final_number))
    return "[" + "] [".join(numbers) + "]"

def get_bet_name(bet_type):
    names = {
        'red': '🔴 КРАСНОЕ',
        'black': '⚫ ЧЕРНОЕ',        'even': '💰 ЧЕТНОЕ',
        'odd': '📊 НЕЧЕТНОЕ',
        'high': '📈 БОЛЬШОЕ (19-36)',
        'low': '📉 МАЛЕНЬКОЕ (1-18)',
        '1-12': '🎯 1-12',
        '13-24': '🎯 13-24',
        '25-36': '🎯 25-36',
        '0': '🎰 ЗЕРО',
    }
    
    if bet_type.startswith('num_'):
        number = bet_type.split('_')[1]
        return f"⚡ ЧИСЛО {number}"
    
    return names.get(bet_type, bet_type)

def start_loader_game(user_id, job_name):
    boxes = list(range(1, 10))
    random.shuffle(boxes)
    target_boxes = random.sample(range(1, 10), 3)
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    row = []
    for i in range(9):
        btn = types.InlineKeyboardButton(f"📦 {i+1}", callback_data=f"loader_{i+1}")
        row.append(btn)
        if (i+1) % 3 == 0:
            markup.row(*row)
            row = []
    
    loader_games[user_id] = {
        'targets': target_boxes,
        'collected': [],
        'start_time': time.time()
    }
    
    msg = (f"🚚 **{job_name}**\n\n"
           f"🎯 Найди: {target_boxes}\n"
           f"⏱️ Время пошло!")
    
    return markup, msg

def check_loader_click(user_id, box_num):
    if user_id not in loader_games:
        return None
    
    game = loader_games[user_id]
    
    if box_num in game['targets'] and box_num not in game['collected']:
        game['collected'].append(box_num)        
        if len(game['collected']) == len(game['targets']):
            time_spent = time.time() - game['start_time']
            del loader_games[user_id]
            return {'win': True, 'time': time_spent, 'score': 100}
    
    return {'win': False, 'collected': len(game['collected']), 'total': len(game['targets'])}

def start_cleaner_game(user_id, job_name):
    trash_positions = random.sample(range(1, 10), 5)
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    row = []
    for i in range(9):
        btn_text = "🧹" if (i+1) in trash_positions else "⬜"
        btn = types.InlineKeyboardButton(btn_text, callback_data=f"cleaner_{i+1}")
        row.append(btn)
        if (i+1) % 3 == 0:
            markup.row(*row)
            row = []
    
    cleaner_games[user_id] = {
        'trash': trash_positions,
        'cleaned': [],
        'start_time': time.time()
    }
    
    msg = f"🧹 **{job_name}**\n\n🎯 Убери 5 мусоров!\n⏱️ Пошли!"
    
    return markup, msg

def check_cleaner_click(user_id, pos):
    if user_id not in cleaner_games:
        return None
    
    game = cleaner_games[user_id]
    
    if pos in game['trash'] and pos not in game['cleaned']:
        game['cleaned'].append(pos)
        
        if len(game['cleaned']) == len(game['trash']):
            time_spent = time.time() - game['start_time']
            del cleaner_games[user_id]
            return {'win': True, 'time': time_spent, 'score': 100}
    
    return {'win': False, 'collected': len(game['cleaned']), 'total': len(game['trash'])}

def start_courier_game(user_id, job_name):
    routes = [
        {'name': 'Кратчайший', 'time': 15, 'correct': True},        {'name': 'Быстрый', 'time': 25, 'correct': False},
        {'name': 'Объезд', 'time': 40, 'correct': False},
        {'name': 'Платный', 'time': 10, 'correct': False}
    ]
    random.shuffle(routes)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for r in routes:
        markup.add(types.InlineKeyboardButton(
            f"🚦 {r['name']} ({r['time']} сек)", 
            callback_data=f"courier_{str(r['correct']).lower()}_{r['time']}"
        ))
    
    courier_games[user_id] = {'start_time': time.time()}
    
    msg = f"📦 **{job_name}**\n\n🗺️ Выбери быстрый маршрут!\n⏱️ Пошли!"
    
    return markup, msg

def check_courier_choice(user_id, is_correct, route_time):
    if user_id not in courier_games:
        return None
    
    time_spent = time.time() - courier_games[user_id]['start_time']
    del courier_games[user_id]
    
    if is_correct == 'true' and time_spent <= route_time:
        return {'win': True, 'time': time_spent, 'score': 100}
    else:
        return {'win': False, 'time': time_spent, 'score': 0}

def start_mechanic_game(user_id, job_name):
    parts = [1, 2, 3, 4]
    random.shuffle(parts)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = []
    for i, part in enumerate(parts):
        btns.append(types.InlineKeyboardButton(f"🔧 Деталь {part}", callback_data=f"mechanic_{i}_{part}"))
    markup.add(*btns)
    
    mechanic_games[user_id] = {
        'parts': parts,
        'solution': [1, 2, 3, 4],
        'current': [],
        'start_time': time.time()
    }
    
    msg = f"🔧 **{job_name}**\n\n🔩 Собери: 1→2→3→4\n⏱️ Пошли!"
        return markup, msg

def check_mechanic_click(user_id, index, part):
    if user_id not in mechanic_games:
        return None
    
    game = mechanic_games[user_id]
    next_needed = len(game['current'])
    
    if part == game['solution'][next_needed]:
        game['current'].append(part)
        
        if len(game['current']) == 4:
            time_spent = time.time() - game['start_time']
            del mechanic_games[user_id]
            return {'win': True, 'time': time_spent, 'score': 100}
        else:
            return {'progress': len(game['current'])}
    
    return {'progress': len(game['current'])}

def start_programmer_game(user_id, job_name):
    bugs = [
        {'code': 'x = 10\ny = "5"\nprint(x + y)', 'answer': 'Тип данных', 'correct': 1},
        {'code': 'for i in range(10)\n    print(i)', 'answer': 'Синтаксис', 'correct': 2},
        {'code': 'if x = 5:\n    print("ok")', 'answer': 'Синтаксис', 'correct': 2},
    ]
    bug = random.choice(bugs)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    options = ['Тип данных', 'Синтаксис', 'Логика']
    for i, opt in enumerate(options, 1):
        callback = f"programmer_{'correct' if i == bug['correct'] else 'wrong'}"
        markup.add(types.InlineKeyboardButton(f"{opt}", callback_data=callback))
    
    programmer_games[user_id] = {'start_time': time.time()}
    
    msg = f"💻 **{job_name}**\n\n❓ Найди ошибку!\n⏱️ Пошли!"
    
    return markup, msg

def check_programmer_choice(user_id, is_correct):
    if user_id not in programmer_games:
        return None
    
    time_spent = time.time() - programmer_games[user_id]['start_time']
    del programmer_games[user_id]
    
    if is_correct == 'correct':
        score = max(100 - int(time_spent), 50)        return {'win': True, 'time': time_spent, 'score': score}
    else:
        return {'win': False, 'time': time_spent, 'score': 0}

def start_detective_game(user_id, job_name):
    clues = [
        {'clue': 'Он был высоким и носил шляпу', 'options': ['Дворецкий', 'Садовник', 'Повар'], 'correct': 0},
        {'clue': 'Нашли сигарету', 'options': ['Курильщик', 'Не курильщик', 'Случайный'], 'correct': 0},
    ]
    clue = random.choice(clues)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, opt in enumerate(clue['options']):
        callback = f"detective_{'correct' if i == clue['correct'] else 'wrong'}"
        markup.add(types.InlineKeyboardButton(f"🕵️ {opt}", callback_data=callback))
    
    detective_games[user_id] = {'start_time': time.time()}
    
    msg = f"🕵️ **{job_name}**\n\n🔍 {clue['clue']}\n❓ Кто?"
    
    return markup, msg

def check_detective_choice(user_id, is_correct):
    if user_id not in detective_games:
        return None
    
    time_spent = time.time() - detective_games[user_id]['start_time']
    del detective_games[user_id]
    
    if is_correct == 'correct':
        score = max(100 - int(time_spent), 60)
        return {'win': True, 'time': time_spent, 'score': score}
    else:
        return {'win': False, 'time': time_spent, 'score': 0}

def start_engineer_game(user_id, job_name):
    scheme = [random.choice(['🔴', '🔵', '', '🟡']) for _ in range(5)]
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("🔴", callback_data="engineer_🔴"),
        types.InlineKeyboardButton("🔵", callback_data="engineer_🔵"),
        types.InlineKeyboardButton("🟢", callback_data="engineer_🟢"),
        types.InlineKeyboardButton("🟡", callback_data="engineer_🟡")
    ]
    markup.add(*buttons)
    
    engineer_games[user_id] = {
        'scheme': scheme,
        'answer': [],        'start_time': time.time(),
        'memorized': False
    }
    
    msg = f"👨‍ **{job_name}**\n\n🎯 Запомни: {' '.join(scheme)}\n⏱️ 5 сек!"
    
    return markup, msg

def check_engineer_click(user_id, color):
    if user_id not in engineer_games:
        return None
    
    game = engineer_games[user_id]
    
    if time.time() - game['start_time'] < 5:
        return {'memorize': True, 'progress': len(game['answer'])}
    
    game['memorized'] = True
    game['answer'].append(color)
    
    if len(game['answer']) == len(game['scheme']):
        if game['answer'] == game['scheme']:
            time_spent = time.time() - game['start_time']
            del engineer_games[user_id]
            return {'win': True, 'time': time_spent, 'score': 100}
        else:
            del engineer_games[user_id]
            return {'win': False, 'time': time.time() - game['start_time'], 'score': 0}
    
    return {'progress': len(game['answer']), 'total': len(game['scheme'])}

def start_doctor_game(user_id, job_name):
    patients = [
        {'symptoms': 'Боль в груди', 'actions': ['Нитроглицерин', 'Аспирин', 'Валидол'], 'correct': 0, 'time': 10},
        {'symptoms': 'Температура', 'actions': ['Антибиотики', 'Парацетамол', 'Витамины'], 'correct': 1, 'time': 8},
    ]
    patient = random.choice(patients)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, action in enumerate(patient['actions']):
        callback = f"doctor_{'correct' if i == patient['correct'] else 'wrong'}_{patient['time']}"
        markup.add(types.InlineKeyboardButton(f"💊 {action}", callback_data=callback))
    
    doctor_games[user_id] = {'start_time': time.time(), 'time_limit': patient['time']}
    
    msg = f"👨‍⚕️ **{job_name}**\n\n🏥 {patient['symptoms']}\n💊 Лечи!"
    
    return markup, msg

def check_doctor_choice(user_id, is_correct, time_limit):    if user_id not in doctor_games:
        return None
    
    time_spent = time.time() - doctor_games[user_id]['start_time']
    del doctor_games[user_id]
    
    if is_correct == 'correct' and time_spent <= time_limit:
        score = max(100 - int(time_spent * 2), 70)
        return {'win': True, 'time': time_spent, 'score': score}
    else:
        return {'win': False, 'time': time_spent, 'score': 0}

def start_artist_game(user_id, job_name):
    songs = [
        {'emojis': '🎸🌧️🎵', 'options': ['Группа крови', 'Звезда', 'Кукушка'], 'correct': 0},
        {'emojis': '💃🕺', 'options': ['Лада седан', 'Розовый вечер', 'Владимирский'], 'correct': 1},
    ]
    song = random.choice(songs)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, opt in enumerate(song['options']):
        callback = f"artist_{'correct' if i == song['correct'] else 'wrong'}"
        markup.add(types.InlineKeyboardButton(f"🎵 {opt}", callback_data=callback))
    
    artist_games[user_id] = {'start_time': time.time()}
    
    msg = f"👨‍🎤 **{job_name}**\n\n🎼 {song['emojis']}\n❓ Что за песня?"
    
    return markup, msg

def check_artist_choice(user_id, is_correct):
    if user_id not in artist_games:
        return None
    
    time_spent = time.time() - artist_games[user_id]['start_time']
    del artist_games[user_id]
    
    if is_correct == 'correct':
        score = max(100 - int(time_spent), 70)
        return {'win': True, 'time': time_spent, 'score': score}
    else:
        return {'win': False, 'time': time_spent, 'score': 0}

def start_cosmonaut_game(user_id, job_name):
    size = 5
    rocket_pos = (2, 2)
    station_pos = (0, 4)
    
    fuel_positions = []
    while len(fuel_positions) < 3:        pos = (random.randint(0, size-1), random.randint(0, size-1))
        if pos != rocket_pos and pos != station_pos and pos not in fuel_positions:
            fuel_positions.append(pos)
    
    markup = types.InlineKeyboardMarkup(row_width=size)
    for i in range(size):
        row = []
        for j in range(size):
            if (i, j) == rocket_pos:
                row.append(types.InlineKeyboardButton("🚀", callback_data="cosmo_pos"))
            elif (i, j) == station_pos:
                row.append(types.InlineKeyboardButton("🛸", callback_data="cosmo_station"))
            elif (i, j) in fuel_positions:
                row.append(types.InlineKeyboardButton("⛽", callback_data=f"cosmo_fuel_{i}_{j}"))
            else:
                row.append(types.InlineKeyboardButton("⬜", callback_data=f"cosmo_move_{i}_{j}"))
        markup.row(*row)
    
    markup.row(
        types.InlineKeyboardButton("⬆️", callback_data="cosmo_up"),
        types.InlineKeyboardButton("⬇️", callback_data="cosmo_down"),
        types.InlineKeyboardButton("⬅️", callback_data="cosmo_left"),
        types.InlineKeyboardButton("➡️", callback_data="cosmo_right")
    )
    
    cosmonaut_games[user_id] = {
        'rocket': rocket_pos,
        'station': station_pos,
        'fuel': fuel_positions,
        'collected_fuel': [],
        'size': size,
        'start_time': time.time()
    }
    
    msg = f"👨‍🚀 **{job_name}**\n\n🛸 Лети к станции!\n⛽ Собери топливо!"
    
    return markup, msg

def check_cosmonaut_move(user_id, direction):
    if user_id not in cosmonaut_games:
        return None
    
    game = cosmonaut_games[user_id]
    x, y = game['rocket']
    size = game['size']
    
    new_x, new_y = x, y
    if direction == 'up' and x > 0:
        new_x = x - 1
    elif direction == 'down' and x < size - 1:        new_x = x + 1
    elif direction == 'left' and y > 0:
        new_y = y - 1
    elif direction == 'right' and y < size - 1:
        new_y = y + 1
    else:
        return {'invalid': True}
    
    game['rocket'] = (new_x, new_y)
    
    if (new_x, new_y) in game['fuel'] and (new_x, new_y) not in game['collected_fuel']:
        game['collected_fuel'].append((new_x, new_y))
    
    markup = types.InlineKeyboardMarkup(row_width=size)
    for i in range(size):
        row = []
        for j in range(size):
            if (i, j) == game['rocket']:
                row.append(types.InlineKeyboardButton("🚀", callback_data="cosmo_pos"))
            elif (i, j) == game['station']:
                row.append(types.InlineKeyboardButton("🛸", callback_data="cosmo_station"))
            elif (i, j) in game['fuel'] and (i, j) not in game['collected_fuel']:
                row.append(types.InlineKeyboardButton("⛽", callback_data=f"cosmo_fuel_{i}_{j}"))
            else:
                row.append(types.InlineKeyboardButton("⬜", callback_data=f"cosmo_move_{i}_{j}"))
        markup.row(*row)
    
    markup.row(
        types.InlineKeyboardButton("⬆️", callback_data="cosmo_up"),
        types.InlineKeyboardButton("⬇️", callback_data="cosmo_down"),
        types.InlineKeyboardButton("⬅️", callback_data="cosmo_left"),
        types.InlineKeyboardButton("➡️", callback_data="cosmo_right")
    )
    
    if game['rocket'] == game['station'] and len(game['collected_fuel']) == len(game['fuel']):
        time_spent = time.time() - game['start_time']
        score = max(100 - int(time_spent), 70)
        del cosmonaut_games[user_id]
        return {'win': True, 'time': time_spent, 'score': score, 'markup': markup}
    
    return {'moved': True, 'markup': markup, 'collected': len(game['collected_fuel']), 'total': len(game['fuel'])}

def send_top_to_chat(chat_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT first_name, username, custom_name, balance FROM users ORDER BY balance DESC LIMIT 10')
        top = cursor.fetchall()
        conn.close()
                if not top:
            bot.send_message(chat_id, "❌ В топе пока никого нет!")
            return
        
        msg = "🏆 **ТОП 10 БОГАЧЕЙ**\n\n"
        for i, (first_name, username, custom_name, balance) in enumerate(top, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            if custom_name:
                display_name = custom_name
            elif username and username != "NoUsername":
                display_name = f"@{username}"
            else:
                display_name = first_name
            
            msg += f"{medal} {display_name}: {balance:,} {CURRENCY}\n"
        
        bot.send_message(chat_id, msg, parse_mode="Markdown")
    except Exception as e:
        print(f"Ошибка топа: {e}")
        bot.send_message(chat_id, "❌ Ошибка")

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

def transport_keyboard(city):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(
        types.KeyboardButton("🚕 Такси"),
        types.KeyboardButton("🚗 Личная машина")
    )
    markup.row(
        types.KeyboardButton("✈️ Личный самолет"),
        types.KeyboardButton("🔙 Назад")
    )
    return markup

def jobs_keyboard(user_id):
    jobs = get_available_jobs(user_id)
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)    
    for job in jobs:
        markup.add(types.KeyboardButton(f"{job[5]} {job[0]}"))
    
    markup.row(
        types.KeyboardButton("👥 Рефералы"),
        types.KeyboardButton("🔙 Назад")
    )
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
    markup.row(
        types.KeyboardButton("💰 Продать бизнес"),
        types.KeyboardButton("🔙 Назад")
    )
    return markup

def buy_business_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(
        types.KeyboardButton("🥤 Киоск"),
        types.KeyboardButton("🍔 Фастфуд")
    )
    markup.row(
        types.KeyboardButton("🏪 Минимаркет"),
        types.KeyboardButton("⛽ Заправка")
    )
    markup.row(
        types.KeyboardButton("🏨 Отель"),
        types.KeyboardButton("🔙 Назад")
    )
    return markup

def settings_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(
        types.KeyboardButton("✏️ Сменить никнейм"),
        types.KeyboardButton("📋 Помощь")
    )
    markup.row(
        types.KeyboardButton("🔙 Назад")    )
    return markup

def city_shop_keyboard(shop_type):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    if shop_type == 'clothes':
        markup.row(types.KeyboardButton("👕 Смотреть одежду"))
    elif shop_type == 'cars':
        markup.row(types.KeyboardButton("🚗 Смотреть машины"))
        markup.row(types.KeyboardButton("💰 Продать машину"))
    elif shop_type == 'planes':
        markup.row(types.KeyboardButton("✈️ Смотреть самолеты"))
        markup.row(types.KeyboardButton("💰 Продать самолет"))
    elif shop_type == 'houses':
        markup.row(types.KeyboardButton("🏠 Смотреть дома"))
    
    markup.row(types.KeyboardButton("🔙 Назад"))
    return markup

def house_menu_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(
        types.KeyboardButton("👕 Шкаф"),
        types.KeyboardButton("💰 Продать дом")
    )
    markup.row(
        types.KeyboardButton("🔙 Назад")
    )
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    
    if is_banned(user_id):
        bot.reply_to(message, "🔨 Вы забанены.")
        return
    
    username = message.from_user.username or "NoUsername"
    first_name = message.from_user.first_name
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute('''            INSERT INTO users (user_id, username, first_name, balance, exp, level, work_count, total_earned, current_city)
            VALUES (?, ?, ?, 0, 0, 1, 0, 0, 'Москва')
        ''', (user_id, username, first_name))
        conn.commit()
        conn.close()
        
        welcome_text = (
            f"🌟 **ДОБРО ПОЖАЛОВАТЬ!** 🌟\n\n"
            f"👋 {first_name}!\n\n"
            "🎮 Здесь ты сможешь:\n"
            "💼 Работать\n"
            "🏭 Покупать бизнесы\n"
            "🏙️ Путешествовать\n"
            "👕 Покупать одежду\n"
            "🚗 Машины\n"
            "✈️ Самолеты\n"
            "🏠 Дома\n"
            "🎰 Рулетка\n\n"
            "✨ Введи свой никнейм:"
        )
        
        bot.send_message(user_id, welcome_text, parse_mode="Markdown")
        
        markup = types.ForceReply(selective=True)
        msg = bot.send_message(
            user_id, 
            "🔤 **Напиши никнейм:**",
            parse_mode="Markdown",
            reply_markup=markup
        )
        
        bot.register_next_step_handler(msg, process_name_step)
        
    else:
        conn.close()
        bot.send_message(user_id, f"👋 С возвращением, {first_name}!")
        send_main_menu_with_profile(user_id)

def process_name_step(message):
    user_id = message.from_user.id
    custom_name = message.text.strip()
    
    if len(custom_name) < 2 or len(custom_name) > 30:
        bot.send_message(user_id, "❌ Ник от 2 до 30 символов!")
        bot.register_next_step_handler(message, process_name_step)
        return
    
    existing_user = get_user_by_custom_name(custom_name)
    if existing_user:
        bot.send_message(user_id, f"❌ Ник **{custom_name}** занят!")        bot.register_next_step_handler(message, process_name_step)
        return
    
    if set_custom_name(user_id, custom_name):
        bot.send_message(user_id, f"✅ Ник `{custom_name}` сохранен!")
        send_main_menu_with_profile(user_id)
    else:
        bot.send_message(user_id, "❌ Ошибка. Попробуй /start")

@bot.message_handler(func=lambda message: message.text and message.text.lower().strip().startswith(('рул', 'рулетка')))
def roulette_handler(message):
    user_id = message.from_user.id
    
    if is_banned(user_id):
        return
    
    bet_info = parse_roulette_bet(message.text)
    if not bet_info:
        bot.reply_to(message, "❌ Пример: `рул крас 1000` или `рул чер все`")
        return
    
    bet_type, bet_amount = bet_info
    
    balance = get_balance(user_id)
    
    if bet_amount == -1:
        bet_amount = balance
    
    if balance < bet_amount:
        bot.reply_to(message, f"❌ Недостаточно средств!")
        return
    
    if bet_amount < 1:
        bot.reply_to(message, f"❌ Минимум 1 {CURRENCY}")
        return
    
    number = random.randint(0, 36)
    result = get_roulette_result(number)
    
    win_amount = check_roulette_win(number, bet_type, bet_amount)
    
    if win_amount > 0:
        add_balance(user_id, win_amount - bet_amount)
        new_balance = get_balance(user_id)
        update_roulette_stats(user_id, bet_amount, win_amount)
        
        response = (
            f"🎡 **РУЛЕТКА!**\n\n"
            f"💰 Ставка: {bet_amount:,} на {get_bet_name(bet_type)}\n\n"
            f"🎯 Выпало: **{number} {result['emoji']}**!\n\n"            f"🎉 **ВЫИГРЫШ!** +{win_amount:,}\n"
            f"💎 Баланс: {new_balance:,}"
        )
    else:
        add_balance(user_id, -bet_amount)
        new_balance = get_balance(user_id)
        update_roulette_stats(user_id, bet_amount, 0)
        
        response = (
            f"🎡 **РУЛЕТКА!**\n\n"
            f"💰 Ставка: {bet_amount:,} на {get_bet_name(bet_type)}\n\n"
            f"🎯 Выпало: **{number} {result['emoji']}**!\n\n"
            f"😭 **ПРОИГРЫШ** -{bet_amount:,}\n"
            f"💎 Баланс: {new_balance:,}"
        )
    
    bot.send_message(message.chat.id, response, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if is_banned(user_id):
        bot.answer_callback_query(call.id, "🔨 Бан!", show_alert=True)
        return
    
    data = call.data
    
    if data == "top_money":
        bot.delete_message(user_id, call.message.message_id)
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT first_name, username, custom_name, balance FROM users ORDER BY balance DESC LIMIT 10')
            top = cursor.fetchall()
            conn.close()
            
            msg = "💰 **ТОП ПО ДЕНЬГАМ**\n\n"
            for i, (first_name, username, custom_name, balance) in enumerate(top, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                
                if custom_name:
                    display_name = custom_name
                elif username and username != "NoUsername":
                    display_name = f"@{username}"
                else:
                    display_name = first_name
                
                msg += f"{medal} {display_name}: {balance:,}\n"
                        bot.send_message(user_id, msg, parse_mode="Markdown")
        except:
            bot.send_message(user_id, "❌ Ошибка")
        bot.answer_callback_query(call.id)
        return
    
    elif data == "top_exp":
        bot.delete_message(user_id, call.message.message_id)
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT first_name, username, custom_name, exp FROM users ORDER BY exp DESC LIMIT 10')
            top = cursor.fetchall()
            conn.close()
            
            msg = "⭐ **ТОП ПО ОПЫТУ**\n\n"
            for i, (first_name, username, custom_name, exp) in enumerate(top, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                
                if custom_name:
                    display_name = custom_name
                elif username and username != "NoUsername":
                    display_name = f"@{username}"
                else:
                    display_name = first_name
                
                msg += f"{medal} {display_name}: {exp:,}\n"
            
            bot.send_message(user_id, msg, parse_mode="Markdown")
        except:
            bot.send_message(user_id, "❌ Ошибка")
        bot.answer_callback_query(call.id)
        return
    
    elif data.startswith("courier_"):
        parts = data.split("_")
        if len(parts) >= 3:
            is_correct = parts[1]
            route_time = int(parts[2])
            result = check_courier_choice(user_id, is_correct, route_time)
            
            if result:
                if result['win']:
                    jobs = get_available_jobs(user_id)
                    job = [j for j in jobs if "Курьер" in j[0]]
                    reward = random.randint(job[0][2], job[0][3]) if job else 10000
                    exp_reward = job[0][4] if job else 30
                    
                    add_balance(user_id, reward)
                    add_exp(user_id, exp_reward)                    set_cooldown(user_id, "📦 Курьер")
                    
                    conn = get_db()
                    cursor = conn.cursor()
                    cursor.execute('UPDATE users SET work_count = work_count + 1 WHERE user_id = ?', (user_id,))
                    conn.commit()
                    conn.close()
                    
                    bot.edit_message_text(
                        f"✅ **ДОСТАВИЛ!**\n\n"
                        f"💰 {reward:,}\n"
                        f"⭐ +{exp_reward}\n\n"
                        f"⏳ Жди 7 сек",
                        chat_id=user_id,
                        message_id=call.message.message_id
                    )
                else:
                    bot.edit_message_text("❌ **НЕВЕРНО!**", chat_id=user_id, message_id=call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    
    elif data.startswith("shop_page_"):
        page = int(data.split("_")[2])
        clothes, current_page, total = get_clothes_page(page)
        
        if clothes:
            caption = f"👕 *{clothes['name']}*\n\n💰 {clothes['price']:,}\n\n🛍️ Всего: {total}"
            
            try:
                bot.edit_message_media(
                    types.InputMediaPhoto(media=clothes['photo_url'], caption=caption, parse_mode="Markdown"),
                    chat_id=user_id,
                    message_id=call.message.message_id,
                    reply_markup=get_clothes_navigation_keyboard(current_page, total)
                )
            except:
                bot.send_photo(user_id, clothes['photo_url'], caption=caption, parse_mode="Markdown", reply_markup=get_clothes_navigation_keyboard(current_page, total))
                bot.delete_message(user_id, call.message.message_id)
        
        bot.answer_callback_query(call.id)
        return
    
    elif data.startswith("shop_buy_"):
        page = int(data.split("_")[2])
        clothes, current_page, total = get_clothes_page(page)
        
        if clothes:
            success, message_text = buy_clothes(user_id, clothes['id'])
            bot.answer_callback_query(call.id, message_text, show_alert=True)
        return    
    elif data.startswith("cars_page_"):
        page = int(data.split("_")[2])
        car, current_page, total = get_cars_page(page)
        
        if car:
            user_car = get_user_car(user_id)
            caption = f"🚗 *{car['name']}*\n\n💰 {car['price']:,}\n⚡ {car['speed']} км/ч\n\n🛍️ Всего: {total}"
            
            if user_car:
                caption += f"\n\n🚗 Твоя: {user_car['name']}"
            
            try:
                bot.edit_message_media(
                    types.InputMediaPhoto(media=car['photo_url'], caption=caption, parse_mode="Markdown"),
                    chat_id=user_id,
                    message_id=call.message.message_id,
                    reply_markup=get_cars_navigation_keyboard(current_page, total, 'cars')
                )
            except:
                bot.send_photo(user_id, car['photo_url'], caption=caption, parse_mode="Markdown", reply_markup=get_cars_navigation_keyboard(current_page, total, 'cars'))
                bot.delete_message(user_id, call.message.message_id)
        
        bot.answer_callback_query(call.id)
        return
    
    elif data.startswith("cars_buy_"):
        page = int(data.split("_")[2])
        car, current_page, total = get_cars_page(page)
        
        if car:
            success, message_text = buy_car(user_id, car['id'])
            bot.answer_callback_query(call.id, message_text, show_alert=True)
        return
    
    elif data.startswith("planes_page_"):
        page = int(data.split("_")[2])
        plane, current_page, total = get_planes_page(page)
        
        if plane:
            user_plane = get_user_plane(user_id)
            caption = f"✈️ *{plane['name']}*\n\n💰 {plane['price']:,}\n⚡ {plane['speed']} км/ч\n\n🛍️ Всего: {total}"
            
            if user_plane:
                caption += f"\n\n✈️ Твой: {user_plane['name']}"
            
            try:
                bot.edit_message_media(
                    types.InputMediaPhoto(media=plane['photo_url'], caption=caption, parse_mode="Markdown"),
                    chat_id=user_id,                    message_id=call.message.message_id,
                    reply_markup=get_cars_navigation_keyboard(current_page, total, 'planes')
                )
            except:
                bot.send_photo(user_id, plane['photo_url'], caption=caption, parse_mode="Markdown", reply_markup=get_cars_navigation_keyboard(current_page, total, 'planes'))
                bot.delete_message(user_id, call.message.message_id)
        
        bot.answer_callback_query(call.id)
        return
    
    elif data.startswith("planes_buy_"):
        page = int(data.split("_")[2])
        plane, current_page, total = get_planes_page(page)
        
        if plane:
            success, message_text = buy_plane(user_id, plane['id'])
            bot.answer_callback_query(call.id, message_text, show_alert=True)
        return
    
    elif data.startswith("houses_page_"):
        page = int(data.split("_")[2])
        house, current_page, total = get_houses_page(page)
        
        if house:
            caption = f"🏠 *{house['name']}*\n\n💰 {house['price']:,}\n🏡 Комфорт: {house['comfort']}\n\n🛍️ Всего: {total}"
            
            try:
                bot.edit_message_media(
                    types.InputMediaPhoto(media=house['photo_url'], caption=caption, parse_mode="Markdown"),
                    chat_id=user_id,
                    message_id=call.message.message_id,
                    reply_markup=get_houses_navigation_keyboard(current_page, total, 'houses')
                )
            except:
                bot.send_photo(user_id, house['photo_url'], caption=caption, parse_mode="Markdown", reply_markup=get_houses_navigation_keyboard(current_page, total, 'houses'))
                bot.delete_message(user_id, call.message.message_id)
        
        bot.answer_callback_query(call.id)
        return
    
    elif data.startswith("houses_buy_"):
        page = int(data.split("_")[2])
        house, current_page, total = get_houses_page(page)
        
        if house:
            success, message_text = buy_house(user_id, house['id'])
            bot.answer_callback_query(call.id, message_text, show_alert=True)
        return
    
    elif data.startswith("closet_page_"):        page = int(data.split("_")[2])
        clothes = get_user_closet(user_id)
        stats = get_user_wardrobe_stats(user_id)
        if stats:
            msg = f"👕 **ШКАФ**\n{len(clothes)}/{stats['closet_slots']}\n💰 Слот: {stats['next_slot_price']:,}"
            bot.edit_message_text(msg, user_id, call.message.message_id, reply_markup=get_closet_navigation_keyboard(clothes, page))
        bot.answer_callback_query(call.id)
        return
    
    elif data.startswith("closet_equip_"):
        user_clothes_id = int(data.split("_")[2])
        ok, msg = equip_clothes(user_id, user_clothes_id)
        bot.answer_callback_query(call.id, msg, show_alert=True)
        return
    
    elif data == "closet_buy_slot":
        ok, msg = buy_closet_slot(user_id)
        bot.answer_callback_query(call.id, msg, show_alert=True)
        return
    
    elif data == "closet_back":
        house_data = get_user_house(user_id)
        if house_
            house = house_data['house']
            msg = f"🏠 **{house['name']}**\n\n💰 {house_data['price']:,}\n📍 {house_data['city']}"
            bot.edit_message_media(
                types.InputMediaPhoto(media=house['photo_url'], caption=msg, parse_mode="Markdown"),
                user_id, call.message.message_id,
                reply_markup=house_menu_keyboard()
            )
        else:
            bot.delete_message(user_id, call.message.message_id)
            send_main_menu_with_profile(user_id)
        bot.answer_callback_query(call.id)
        return
    
    elif data.startswith("buy_business_"):
        business_name = data.replace("buy_business_", "")
        
        if get_user_business(user_id):
            bot.answer_callback_query(call.id, "❌ Уже есть бизнес!", show_alert=True)
            return
        
        data_b = get_business_data(business_name)
        if not data_b:
            bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)
            return
        
        balance = get_balance(user_id)
        if balance < data_b['price']:            bot.answer_callback_query(call.id, f"❌ Не хватает!", show_alert=True)
            return
        
        if add_balance(user_id, -data_b['price']):
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO businesses (user_id, business_name, level, raw_material, raw_in_delivery, raw_spent, total_invested, stored_profit, last_update)
                VALUES (?, ?, 1, 0, 0, 0, 0, 0, ?)
            ''', (user_id, business_name, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            
            bot.delete_message(user_id, call.message.message_id)
            bot.send_message(user_id, f"✅ Купил {business_name}!")
            bot.answer_callback_query(call.id, "✅ Успех!")
        else:
            bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)
        return
    
    elif data == "cancel_buy_business":
        bot.delete_message(user_id, call.message.message_id)
        bot.send_message(user_id, "Выбери бизнес:", reply_markup=buy_business_keyboard())
        bot.answer_callback_query(call.id)
        return
    
    elif data == "shop_close":
        bot.delete_message(user_id, call.message.message_id)
        send_main_menu_with_profile(user_id)
        bot.answer_callback_query(call.id)
        return
    
    elif data == "noop":
        bot.answer_callback_query(call.id)
        return

@bot.message_handler(func=lambda message: True)
def handle(message):
    user_id = message.from_user.id
    text = message.text
    
    if is_banned(user_id):
        bot.reply_to(message, "🔨 Бан!")
        return
    
    user_data = get_user_profile(user_id)
    display_name = get_user_display_name(user_data) if user_data else "Игрок"
    
    if text == "💼 Работы":
        bot.send_message(user_id, "🔨 Выбери работу:", reply_markup=jobs_keyboard(user_id))    
    elif text == "🏭 Бизнесы":
        bot.send_message(user_id, "🏪 Бизнес:", reply_markup=businesses_main_keyboard())
    
    elif text in ["👕 Магазин одежды", "🚗 Магазин машин", "✈️ Магазин самолетов", "🏠 Магазин домов"]:
        current_city = get_user_city(user_id)
        city_info = get_city_info(current_city)
        
        if not city_info:
            bot.send_message(user_id, "❌ Ошибка")
            return
        
        shop_type = city_info['shop_type']
        
        if shop_type == 'clothes':
            clothes, current_page, total = get_clothes_page(0)
            if clothes:
                caption = f"👕 *{clothes['name']}*\n\n💰 {clothes['price']:,}\n\n🛍️ Всего: {total}"
                bot.send_photo(user_id, clothes['photo_url'], caption=caption, parse_mode="Markdown", reply_markup=get_clothes_navigation_keyboard(current_page, total))
            else:
                bot.send_message(user_id, "❌ Пусто")
        
        elif shop_type == 'cars':
            cars, current_page, total = get_cars_page(0)
            if cars:
                user_car = get_user_car(user_id)
                caption = f"🚗 *{cars['name']}*\n\n💰 {cars['price']:,}\n⚡ {cars['speed']} км/ч"
                if user_car:
                    caption += f"\n\n🚗 Твоя: {user_car['name']}"
                bot.send_photo(user_id, cars['photo_url'], caption=caption, parse_mode="Markdown", reply_markup=get_cars_navigation_keyboard(current_page, total, 'cars'))
            else:
                bot.send_message(user_id, "❌ Пусто")
        
        elif shop_type == 'planes':
            planes, current_page, total = get_planes_page(0)
            if planes:
                user_plane = get_user_plane(user_id)
                caption = f"✈️ *{planes['name']}*\n\n💰 {planes['price']:,}\n⚡ {planes['speed']} км/ч"
                if user_plane:
                    caption += f"\n\n✈️ Твой: {user_plane['name']}"
                bot.send_photo(user_id, planes['photo_url'], caption=caption, parse_mode="Markdown", reply_markup=get_cars_navigation_keyboard(current_page, total, 'planes'))
            else:
                bot.send_message(user_id, "❌ Пусто")
        
        elif shop_type == 'houses':
            houses, current_page, total = get_houses_page(0)
            if houses:
                caption = f"🏠 *{houses['name']}*\n\n💰 {houses['price']:,}\n🏡 Комфорт: {houses['comfort']}"
                bot.send_photo(user_id, houses['photo_url'], caption=caption, parse_mode="Markdown", reply_markup=get_houses_navigation_keyboard(current_page, total, 'houses'))
            else:                bot.send_message(user_id, "❌ Пусто")
    
    elif text == "🎁 Ежедневно":
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT last_daily FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            last = result[0] if result else None
            now = datetime.now().isoformat()
            
            if last:
                last_time = datetime.fromisoformat(last)
                if datetime.now() - last_time < timedelta(hours=24):
                    next_time = last_time + timedelta(hours=24)
                    time_left = next_time - datetime.now()
                    hours = time_left.seconds // 3600
                    minutes = (time_left.seconds % 3600) // 60
                    bot.send_message(user_id, f"⏳ Жди {hours}ч {minutes}м")
                    conn.close()
                    return
            
            bonus = random.randint(500, 2000)
            bonus_exp = random.randint(50, 200)
            cursor.execute('UPDATE users SET balance = balance + ?, exp = exp + ?, last_daily = ? WHERE user_id = ?', 
                          (bonus, bonus_exp, now, user_id))
            conn.commit()
            conn.close()
            bot.send_message(user_id, f"🎁 +{bonus} и +{bonus_exp}⭐!")
        except:
            bot.send_message(user_id, "❌ Ошибка")
    
    elif text == "🗺️ Карта":
        bot.send_message(user_id, "🗺️ **ГОРОДА**\n\n🏙️ Москва\n🏙️ Село Молочное\n🏙️ Кропоткин\n🏙️ Мурино", parse_mode="Markdown", reply_markup=cities_keyboard())
    
    elif text == "🏠 Мой дом":
        house_data = get_user_house(user_id)
        if not house_data:
            bot.send_message(user_id, "🏠 Нет дома! Купи в Мурино.")
        else:
            house = house_data['house']
            stats = get_user_wardrobe_stats(user_id)
            if stats:
                msg = f"🏠 **{house['name']}**\n\n💰 {house_data['price']:,}\n📍 {house_data['city']}\n\n👕 Слотов: {stats['closet_slots']}"
                bot.send_photo(user_id, house['photo_url'], caption=msg, parse_mode="Markdown", reply_markup=house_menu_keyboard())
    
    elif text == "👕 Шкаф":
        house_data = get_user_house(user_id)
        if not house_
            bot.send_message(user_id, "🏠 Купи дом!")            return
        
        clothes = get_user_closet(user_id)
        stats = get_user_wardrobe_stats(user_id)
        
        if stats:
            msg = f"👕 **ШКАФ**\n{len(clothes)}/{stats['closet_slots']}\n💰 Слот: {stats['next_slot_price']:,}"
            bot.send_message(user_id, msg, reply_markup=get_closet_navigation_keyboard(clothes, 0))
    
    elif text == "💰 Продать дом":
        success, msg = sell_house(user_id)
        bot.send_message(user_id, msg)
        if success:
            send_main_menu_with_profile(user_id)
    
    elif text == "⚙️ Настройки":
        bot.send_message(user_id, "🔧 **НАСТРОЙКИ**", reply_markup=settings_keyboard(), parse_mode="Markdown")
    
    elif text == "🔄":
        send_main_menu_with_profile(user_id)
    
    elif text in ["🏙️ Москва", "🏙️ Село Молочное", "🏙️ Кропоткин", "🏙️ Мурино"]:
        city_name = text.replace("🏙️ ", "")
        current_city = get_user_city(user_id)
        
        if city_name == current_city:
            city_info = get_city_info(city_name)
            bot.send_message(user_id, f"🏙️ Ты в {city_name}", reply_markup=city_shop_keyboard(city_info['shop_type']))
        else:
            bot.send_message(user_id, f"🚀 Транспорт в {city_name}:", reply_markup=transport_keyboard(city_name))
            bot.register_next_step_handler(message, process_travel, city_name)
    
    elif text == "👕 Смотреть одежду":
        clothes, current_page, total = get_clothes_page(0)
        if clothes:
            caption = f"👕 *{clothes['name']}*\n\n💰 {clothes['price']:,}"
            bot.send_photo(user_id, clothes['photo_url'], caption=caption, parse_mode="Markdown", reply_markup=get_clothes_navigation_keyboard(current_page, total))
        else:
            bot.send_message(user_id, "❌ Пусто")
    
    elif text == "🚗 Смотреть машины":
        cars, current_page, total = get_cars_page(0)
        if cars:
            user_car = get_user_car(user_id)
            caption = f"🚗 *{cars['name']}*\n\n💰 {cars['price']:,}\n⚡ {cars['speed']} км/ч"
            if user_car:
                caption += f"\n\n🚗 Твоя: {user_car['name']}"
            bot.send_photo(user_id, cars['photo_url'], caption=caption, parse_mode="Markdown", reply_markup=get_cars_navigation_keyboard(current_page, total, 'cars'))
        else:
            bot.send_message(user_id, "❌ Пусто")    
    elif text == "💰 Продать машину":
        success, msg = sell_car(user_id)
        bot.send_message(user_id, msg)
        if success:
            send_main_menu_with_profile(user_id)
    
    elif text == "✈️ Смотреть самолеты":
        planes, current_page, total = get_planes_page(0)
        if planes:
            user_plane = get_user_plane(user_id)
            caption = f"✈️ *{planes['name']}*\n\n💰 {planes['price']:,}\n⚡ {planes['speed']} км/ч"
            if user_plane:
                caption += f"\n\n✈️ Твой: {user_plane['name']}"
            bot.send_photo(user_id, planes['photo_url'], caption=caption, parse_mode="Markdown", reply_markup=get_cars_navigation_keyboard(current_page, total, 'planes'))
        else:
            bot.send_message(user_id, "❌ Пусто")
    
    elif text == "💰 Продать самолет":
        success, msg = sell_plane(user_id)
        bot.send_message(user_id, msg)
        if success:
            send_main_menu_with_profile(user_id)
    
    elif text == "🏠 Смотреть дома":
        houses, current_page, total = get_houses_page(0)
        if houses:
            caption = f"🏠 *{houses['name']}*\n\n💰 {houses['price']:,}\n🏡 Комфорт: {houses['comfort']}"
            bot.send_photo(user_id, houses['photo_url'], caption=caption, parse_mode="Markdown", reply_markup=get_houses_navigation_keyboard(current_page, total, 'houses'))
        else:
            bot.send_message(user_id, "❌ Пусто")
    
    elif text == "🏪 Купить бизнес":
        bot.send_message(user_id, "Выбери бизнес:", reply_markup=buy_business_keyboard())
    
    elif text in ["🥤 Киоск", "🍔 Фастфуд", "🏪 Минимаркет", "⛽ Заправка", "🏨 Отель"]:
        if get_user_business(user_id):
            bot.send_message(user_id, "❌ Уже есть бизнес!")
            return
        
        data = get_business_data(text)
        if not 
            bot.send_message(user_id, "❌ Не найден")
            return
        
        msg = f"{data['emoji']} **{data['name']}**\n\n💰 {data['price']:,}\n📦 Сырьё: {data['raw_cost_per_unit']:,}\n💵 Прибыль: {data['profit_per_raw']:,}"
        
        bot.send_photo(user_id, data['photo_url'], caption=msg, parse_mode="Markdown", reply_markup=get_business_buy_keyboard(text))
    
    elif any(job in text for job in ["🚚 Грузчик", "🧹 Уборщик", "📦 Курьер", "🔧 Механик", "💻 Программист", "🕵️ Детектив", "👨‍🔧 Инженер", "👨‍️ Врач", "‍🎤 Артист", "👨‍🚀 Космонавт"]):        job_name = text
        
        ok, rem = check_cooldown(user_id, job_name)
        if not ok:
            bot.send_message(user_id, f"⏳ Жди {rem} сек!")
            return
        
        if "Грузчик" in job_name:
            markup, msg = start_loader_game(user_id, job_name)
            bot.send_message(user_id, msg, reply_markup=markup)
        
        elif "Уборщик" in job_name:
            markup, msg = start_cleaner_game(user_id, job_name)
            bot.send_message(user_id, msg, reply_markup=markup)
        
        elif "Курьер" in job_name:
            markup, msg = start_courier_game(user_id, job_name)
            bot.send_message(user_id, msg, reply_markup=markup)
        
        elif "Механик" in job_name:
            markup, msg = start_mechanic_game(user_id, job_name)
            bot.send_message(user_id, msg, reply_markup=markup)
        
        elif "Программист" in job_name:
            markup, msg = start_programmer_game(user_id, job_name)
            bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=markup)
        
        elif "Детектив" in job_name:
            markup, msg = start_detective_game(user_id, job_name)
            bot.send_message(user_id, msg, reply_markup=markup)
        
        elif "Инженер" in job_name:
            markup, msg = start_engineer_game(user_id, job_name)
            bot.send_message(user_id, msg, reply_markup=markup)
        
        elif "Врач" in job_name:
            markup, msg = start_doctor_game(user_id, job_name)
            bot.send_message(user_id, msg, reply_markup=markup)
        
        elif "Артист" in job_name:
            markup, msg = start_artist_game(user_id, job_name)
            bot.send_message(user_id, msg, reply_markup=markup)
        
        elif "Космонавт" in job_name:
            markup, msg = start_cosmonaut_game(user_id, job_name)
            bot.send_message(user_id, msg, reply_markup=markup)
    
    elif text == "👥 Рефералы":
        bot_username = bot.get_me().username
        link = f"https://t.me/{bot_username}?start={user_id}"        bot.send_message(user_id, f"👥 **Твоя ссылка:**\n{link}", parse_mode="Markdown")
    
    elif text == "📊 Мой бизнес":
        business = get_user_business(user_id)
        if not business:
            bot.send_message(user_id, "📭 Нет бизнеса!")
            return
        
        data = get_business_data(business['business_name'])
        if not 
            bot.send_message(user_id, "❌ Ошибка")
            return
        
        msg = f"{data['emoji']} **{business['business_name']}**\n\n📊 Уровень: {business['level']}\n📦 На складе: {business['raw_material']}/1000\n💰 Прибыль: {business['stored_profit']:,}"
        
        if data['photo_url']:
            bot.send_photo(user_id, data['photo_url'], caption=msg, parse_mode="Markdown")
        else:
            bot.send_message(user_id, msg, parse_mode="Markdown")
    
    elif text == "💰 Собрать прибыль":
        business = get_user_business(user_id)
        if not business:
            bot.send_message(user_id, "📭 Нет бизнеса!")
            return
        
        if business['stored_profit'] <= 0:
            bot.send_message(user_id, "❌ Нет прибыли!")
            return
        
        profit = business['stored_profit']
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE businesses SET stored_profit = 0 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        add_balance(user_id, profit)
        
        bot.send_message(user_id, f"✅ +{profit:,}!")
    
    elif text == "📦 Закупить на всё":
        business = get_user_business(user_id)
        if not business:
            bot.send_message(user_id, "❌ Купи бизнес!")
            return
        
        data = get_business_data(business['business_name'])
        if not             bot.send_message(user_id, "❌ Ошибка")
            return
        
        balance = get_balance(user_id)
        raw_cost = data['raw_cost_per_unit']
        max_by_money = balance // raw_cost
        
        total_raw = business['raw_material'] + business['raw_in_delivery']
        free_space = 1000 - total_raw
        
        amount = min(max_by_money, free_space)
        
        if amount <= 0:
            bot.send_message(user_id, f"❌ Нет места или денег!")
            return
        
        total_cost = amount * raw_cost
        
        if not add_balance(user_id, -total_cost):
            bot.send_message(user_id, "❌ Ошибка")
            return
        
        if has_active_delivery(user_id):
            bot.send_message(user_id, "❌ Уже есть доставка!")
            add_balance(user_id, total_cost)
            return
        
        conn = get_db()
        cursor = conn.cursor()
        
        end_time = datetime.now() + timedelta(minutes=15)
        cursor.execute('''
            INSERT INTO deliveries (user_id, amount, end_time, delivered)
            VALUES (?, ?, ?, 0)
        ''', (user_id, amount, end_time.isoformat()))
        
        cursor.execute('''
            UPDATE businesses 
            SET raw_in_delivery = raw_in_delivery + ?,
                total_invested = total_invested + ?
            WHERE user_id = ?
        ''', (amount, total_cost, user_id))
        
        conn.commit()
        conn.close()
        
        bot.send_message(user_id, f"✅ Заказ на {amount} сырья!\n💰 {total_cost:,}\n⏱️ 15 мин")
    
    elif text == "💰 Продать бизнес":
        business = get_user_business(user_id)        if not business:
            bot.send_message(user_id, "❌ Нет бизнеса!")
            return
        
        data = get_business_data(business['business_name'])
        if not data:
            bot.send_message(user_id, "❌ Ошибка")
            return
        
        sell_price = data['price'] // 2
        if add_balance(user_id, sell_price):
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM businesses WHERE user_id = ?', (user_id,))
                cursor.execute('DELETE FROM deliveries WHERE user_id = ?', (user_id,))
                conn.commit()
                conn.close()
                bot.send_message(user_id, f"💰 Продан за {sell_price:,}!")
            except:
                bot.send_message(user_id, "❌ Ошибка")
                add_balance(user_id, -sell_price)
    
    elif text == "📋 Помощь":
        help_text = "📚 **ПОМОЩЬ**\n\n💼 Работы\n🏭 Бизнесы\n🏙️ Города\n👕 Одежда\n🚗 Машины\n✈️ Самолеты\n🏠 Дома\n🎰 Рулетка: рул крас 1000"
        bot.send_message(user_id, help_text, parse_mode="Markdown")
    
    elif text == "🔙 Назад":
        send_main_menu_with_profile(user_id)

def process_travel(message, target_city):
    user_id = message.from_user.id
    transport = message.text
    
    if transport == "🔙 Назад":
        send_main_menu_with_profile(user_id)
        return
    
    if transport not in ["🚕 Такси", "🚗 Личная машина", "✈️ Личный самолет"]:
        bot.send_message(user_id, "❌ Выбери транспорт!")
        bot.register_next_step_handler(message, process_travel, target_city)
        return
    
    conn = get_db()
    cursor = conn.cursor()
    user = cursor.execute('SELECT has_car, has_plane FROM users WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    
    if transport == "🚗 Личная машина" and (not user or user['has_car'] == 0):
        bot.send_message(user_id, "❌ Нет машины!")        bot.send_message(user_id, f"🚀 Транспорт в {target_city}:", reply_markup=transport_keyboard(target_city))
        bot.register_next_step_handler(message, process_travel, target_city)
        return
    
    if transport == "✈️ Личный самолет" and (not user or user['has_plane'] == 0):
        bot.send_message(user_id, "❌ Нет самолета!")
        bot.send_message(user_id, f"🚀 Транспорт в {target_city}:", reply_markup=transport_keyboard(target_city))
        bot.register_next_step_handler(message, process_travel, target_city)
        return
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        active = cursor.execute('SELECT id FROM travels WHERE user_id = ? AND completed = 0', (user_id,)).fetchone()
        
        if active:
            conn.close()
            bot.send_message(user_id, "❌ Уже едешь!")
            return
        
        from_city = get_user_city(user_id)
        
        base_time = random.randint(30, 60)
        
        if transport == "✈️ Личный самолет":
            plane = get_user_plane(user_id)
            if plane:
                speed_multiplier = plane['speed'] / 100
                travel_time = max(10, int(base_time / speed_multiplier))
            else:
                travel_time = base_time
        elif transport == "🚗 Личная машина":
            car = get_user_car(user_id)
            if car:
                speed_multiplier = car['speed'] / 100
                travel_time = max(15, int(base_time / speed_multiplier))
            else:
                travel_time = base_time
        else:
            travel_time = base_time
        
        end_time = datetime.now() + timedelta(seconds=travel_time)
        
        cursor.execute('''
            INSERT INTO travels (user_id, from_city, to_city, transport, end_time, completed)
            VALUES (?, ?, ?, ?, ?, 0)
        ''', (user_id, from_city, target_city, transport, end_time.isoformat()))
        
        conn.commit()        conn.close()
        
        bot.send_message(user_id, f"🚀 Поехали в {target_city}!\n⏱️ {travel_time} сек", reply_markup=types.ReplyKeyboardRemove())
    except Exception as e:
        print(f"Ошибка: {e}")
        bot.send_message(user_id, "❌ Ошибка")

def check_travels():
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            travels = cursor.execute('''
                SELECT * FROM travels 
                WHERE completed = 0 AND end_time <= ?
            ''', (datetime.now().isoformat(),)).fetchall()
            
            for t in travels:
                cursor.execute('UPDATE users SET current_city = ? WHERE user_id = ?', 
                             (t['to_city'], t['user_id']))
                cursor.execute('UPDATE travels SET completed = 1 WHERE id = ?', (t['id'],))
                
                try:
                    bot.send_message(
                        t['user_id'],
                        f"✅ Прибыл в {t['to_city']}!",
                        reply_markup=main_keyboard_for_city(t['user_id'])
                    )
                except:
                    pass
                
                conn.commit()
            
            conn.close()
            time.sleep(5)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(5)

def process_raw_material():
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()
            businesses = cursor.execute('SELECT * FROM businesses').fetchall()
            
            for b in businesses:
                if b['raw_material'] > 0:
                    data = get_business_data(b['business_name'])                    if 
                        speed_multiplier = {1: 1.0, 2: 1.2, 3: 2.0}
                        current_speed = speed_multiplier.get(b['level'], 1.0)
                        time_per_raw = data['base_time'] / current_speed
                        
                        last_update = datetime.fromisoformat(b['last_update'])
                        time_passed = (datetime.now() - last_update).total_seconds()
                        
                        units_to_process = int(time_passed / time_per_raw)
                        
                        if units_to_process > 0 and b['raw_material'] > 0:
                            process = min(units_to_process, b['raw_material'])
                            profit = process * data['profit_per_raw']
                            
                            cursor.execute('''
                                UPDATE businesses 
                                SET raw_material = raw_material - ?,
                                    raw_spent = raw_spent + ?,
                                    stored_profit = stored_profit + ?,
                                    last_update = ?
                                WHERE user_id = ?
                            ''', (process, process, profit, datetime.now().isoformat(), b['user_id']))
                            
                            total_spent = b['raw_spent'] + process
                            
                            if total_spent >= 50000 and b['level'] == 1:
                                cursor.execute('UPDATE businesses SET level = 2 WHERE user_id = ?', (b['user_id'],))
                            elif total_spent >= 200000 and b['level'] == 2:
                                cursor.execute('UPDATE businesses SET level = 3 WHERE user_id = ?', (b['user_id'],))
                            
                            conn.commit()
            conn.close()
            time.sleep(10)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(10)

def check_deliveries():
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            deliveries = cursor.execute('''
                SELECT * FROM deliveries 
                WHERE delivered = 0 AND end_time <= ?
            ''', (datetime.now().isoformat(),)).fetchall()
            
            for d in deliveries:
                cursor.execute('''                    UPDATE businesses 
                    SET raw_material = raw_material + ?,
                        raw_in_delivery = raw_in_delivery - ?
                    WHERE user_id = ?
                ''', (d['amount'], d['amount'], d['user_id']))
                
                cursor.execute('UPDATE deliveries SET delivered = 1 WHERE id = ?', (d['id'],))
                
                try:
                    business = get_user_business(d['user_id'])
                    if business:
                        total_raw = business['raw_material'] + d['amount']
                        bot.send_message(d['user_id'], f"✅ +{d['amount']} сырья!\n📦 {total_raw}/1000")
                except:
                    pass
            
            conn.commit()
            conn.close()
            time.sleep(30)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(30)

def cleanup_cooldowns():
    while True:
        try:
            now = time.time()
            to_delete = [k for k, v in job_cooldowns.items() if now - v > 60]
            for k in to_delete:
                del job_cooldowns[k]
            time.sleep(60)
        except:
            time.sleep(60)

threading.Thread(target=process_raw_material, daemon=True).start()
threading.Thread(target=check_deliveries, daemon=True).start()
threading.Thread(target=check_travels, daemon=True).start()
threading.Thread(target=cleanup_cooldowns, daemon=True).start()

app = Flask('')

@app.route('/')
def home():
    return "Бот работает!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)    t.start()

keep_alive()
print("✅ Бот запущен!")
bot.infinity_polling()
