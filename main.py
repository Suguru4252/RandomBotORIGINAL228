import telebot
import sqlite3
import random
import os
from datetime import datetime, timedelta
from telebot import types
import threading
import time

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

# ========== АДМИНЫ ==========
ADMINS = {
    5596589260: 4
}

# ========== БАНЫ И ВАРНЫ ==========
BANS = {}
WARNS = {}
MAX_WARNS = 3
BAN_WARN_DAYS = 30

def get_admin_level(user_id):
    return ADMINS.get(user_id, 0)

def is_admin(user_id, required_level=1):
    return get_admin_level(user_id) >= required_level

def add_admin(user_id, level):
    if user_id in ADMINS:
        return False, "❌ Пользователь уже админ"
    ADMINS[user_id] = level
    return True, f"✅ Пользователь назначен админом {level} уровня"

def is_banned(user_id):
    if user_id in BANS:
        ban_info = BANS[user_id]
        if ban_info['until'] == 0:
            return True
        elif datetime.now().timestamp() < ban_info['until']:
            return True
        else:
            del BANS[user_id]
    return False

def add_warn(user_id):
    global WARNS
    current = WARNS.get(user_id, 0) + 1
    WARNS[user_id] = current
    
    if current >= MAX_WARNS:
        ban_time = datetime.now() + timedelta(days=30)
        BANS[user_id] = {'reason': 'warn', 'until': ban_time.timestamp()}
        WARNS[user_id] = 0
        return True, f"❌ Получен 3 варн! Бан на 30 дней."
    
    return False, f"⚠️ Варн {current}/{MAX_WARNS}"

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
            current_city TEXT DEFAULT 'Село Молочное',
            has_car INTEGER DEFAULT 0,
            has_plane INTEGER DEFAULT 0,
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
            base_time INTEGER
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
            equipped INTEGER DEFAULT 1,
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (clothes_id) REFERENCES shop_clothes(id)
        )
    ''')
    
    # ========== НОВЫЕ ТАБЛИЦЫ ДЛЯ ГОРОДОВ ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT,
            has_clothes_shop INTEGER DEFAULT 1,
            has_house_shop INTEGER DEFAULT 0,
            has_plane_shop INTEGER DEFAULT 0
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
    
    # Заполняем города
    cursor.execute('SELECT COUNT(*) FROM cities')
    if cursor.fetchone()[0] == 0:
        cities_data = [
            ("Кропоткин", "Промышленный город с развитой инфраструктурой", 1, 1, 0),
            ("Москва", "Столица! Здесь есть всё", 1, 0, 1),
            ("Мурино", "Молодежный спальный район", 1, 1, 0),
            ("Село Молочное", "Уютное село, отличное место для старта", 1, 0, 0)
        ]
        cursor.executemany('''
            INSERT INTO cities (name, description, has_clothes_shop, has_house_shop, has_plane_shop)
            VALUES (?, ?, ?, ?, ?)
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
    
    businesses_data = [
        ("🥤 Киоск", 500_000, "🥤", 1_000, 2_000, 60),
        ("🍔 Фастфуд", 5_000_000, "🍔", 2_500, 5_000, 60),
        ("🏪 Минимаркет", 15_000_000, "🏪", 30_000, 60_000, 60),
        ("⛽ Заправка", 50_000_000, "⛽", 200_000, 400_000, 60),
        ("🏨 Отель", 1_000_000_000, "🏨", 1_000_000, 2_000_000, 120)
    ]
    
    for bd in businesses_data:
        cursor.execute('''
            INSERT OR IGNORE INTO business_data (name, price, emoji, raw_cost_per_unit, profit_per_raw, base_time)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', bd)
    
    jobs_data = [
        ("🚚 Грузчик", 0, 10, 50, 5, "🚚"),
        ("🧹 Уборщик", 50, 15, 70, 7, "🧹"),
        ("📦 Курьер", 150, 20, 100, 10, "📦"),
        ("🔧 Механик", 300, 30, 150, 12, "🔧"),
        ("💻 Программист", 500, 50, 300, 15, "💻"),
        ("🕵️ Детектив", 800, 100, 500, 20, "🕵️"),
        ("👨‍🔧 Инженер", 1200, 200, 800, 25, "👨‍🔧"),
        ("👨‍⚕️ Врач", 1700, 300, 1200, 30, "👨‍⚕️"),
        ("👨‍🎤 Артист", 2300, 500, 2000, 35, "👨‍🎤"),
        ("👨‍🚀 Космонавт", 3000, 1000, 5000, 50, "👨‍🚀")
    ]
    
    for job in jobs_data:
        cursor.execute('''
            INSERT OR IGNORE INTO jobs (job_name, min_exp, min_reward, max_reward, exp_reward, emoji)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', job)
    
    conn.commit()
    conn.close()
    print("✅ База данных проверена/создана")
    print("🏙️ Система городов активирована!")
    print("👕 Магазин одежды загружен с 16 комплектами!")

init_db()

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

def get_user_by_username(username):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, first_name, username, custom_name, warns FROM users WHERE username = ?', (username,))
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
    if not user_data:
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

def set_custom_name(user_id, name):
    try:
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
        data = cursor.fetchone()
        conn.close()
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

def find_user_by_input(input_str):
    if input_str.startswith('@'):
        username = input_str[1:]
        return get_user_by_username(username)
    else:
        return get_user_by_custom_name(input_str)

# ========== НОВЫЕ ФУНКЦИИ ДЛЯ ГОРОДОВ ==========

def get_user_city(user_id):
    """Получает текущий город пользователя"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT current_city FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else "Село Молочное"
    except:
        return "Село Молочное"

def set_user_city(user_id, city):
    """Устанавливает город пользователя"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET current_city = ? WHERE user_id = ?', (city, user_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def get_city_info(city_name):
    """Получает информацию о городе"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM cities WHERE name = ?', (city_name,))
        city = cursor.fetchone()
        conn.close()
        return city
    except:
        return None

def start_travel(user_id, to_city, transport):
    """Начинает поездку в другой город"""
    try:
        # Проверяем, нет ли уже активной поездки
        conn = get_db()
        cursor = conn.cursor()
        active = cursor.execute('''
            SELECT id FROM travels 
            WHERE user_id = ? AND completed = 0
        ''', (user_id,)).fetchone()
        
        if active:
            conn.close()
            return False, "❌ У тебя уже есть активная поездка!"
        
        from_city = get_user_city(user_id)
        
        # Время поездки: рандом 30-60 секунд
        travel_time = random.randint(30, 60)
        end_time = datetime.now() + timedelta(seconds=travel_time)
        
        cursor.execute('''
            INSERT INTO travels (user_id, from_city, to_city, transport, end_time, completed)
            VALUES (?, ?, ?, ?, ?, 0)
        ''', (user_id, from_city, to_city, transport, end_time.isoformat()))
        
        conn.commit()
        conn.close()
        
        return True, f"🚀 Ты отправился в {to_city} на {transport}! Время в пути: {travel_time} сек."
    except Exception as e:
        print(f"Ошибка поездки: {e}")
        return False, "❌ Ошибка при начале поездки"

def get_active_travel(user_id):
    """Получает активную поездку пользователя"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        travel = cursor.execute('''
            SELECT * FROM travels 
            WHERE user_id = ? AND completed = 0
        ''', (user_id,)).fetchone()
        conn.close()
        return travel
    except:
        return None

def complete_travel(travel_id, user_id):
    """Завершает поездку"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        travel = cursor.execute('SELECT * FROM travels WHERE id = ?', (travel_id,)).fetchone()
        
        if travel:
            # Меняем город пользователя
            cursor.execute('UPDATE users SET current_city = ? WHERE user_id = ?', 
                         (travel['to_city'], user_id))
            cursor.execute('UPDATE travels SET completed = 1 WHERE id = ?', (travel_id,))
            conn.commit()
            
            # Отправляем уведомление
            bot.send_message(
                user_id,
                f"✅ Вы прибыли в {travel['to_city']}!\n"
                f"Транспорт: {travel['transport']}"
            )
        
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка завершения поездки: {e}")
        return False

# ========== ФУНКЦИИ ДЛЯ МАГАЗИНА И ПРОФИЛЯ ==========

def get_user_equipped_clothes(user_id):
    """Получает надетую одежду пользователя"""
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
    """Возвращает фото для профиля пользователя"""
    equipped = get_user_equipped_clothes(user_id)
    if equipped and equipped['photo_url']:
        return equipped['photo_url']
    return "https://iimg.su/i/waxabI"  # Стандартное фото

def send_main_menu_with_profile(user_id, chat_id=None):
    """Отправляет главное меню с фото профиля и городом"""
    if not chat_id:
        chat_id = user_id
    
    # Получаем данные пользователя
    user_data = get_user_profile(user_id)
    if not user_data:
        return
    
    balance = get_balance(user_id)
    display_name = get_user_display_name(user_data)
    current_city = get_user_city(user_id)
    
    # Формируем подпись с городом
    caption = (f"👤 *{display_name}*\n\n"
               f"💰 Баланс: {balance:,} {CURRENCY}\n"
               f"📍 Город: {current_city}")
    
    # Получаем фото профиля
    photo_url = get_user_profile_photo(user_id)
    
    # Отправляем фото с подписью и клавиатурой
    bot.send_photo(
        chat_id,
        photo_url,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

def buy_clothes(user_id, clothes_id):
    """Покупает одежду и сразу надевает её"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Получаем информацию о товаре
        clothes = cursor.execute('SELECT * FROM shop_clothes WHERE id = ?', (clothes_id,)).fetchone()
        if not clothes:
            conn.close()
            return False, "❌ Товар не найден"
        
        # Проверяем баланс
        user = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if not user or user['balance'] < clothes['price']:
            conn.close()
            return False, f"❌ Недостаточно средств! Нужно {clothes['price']:,} {CURRENCY}"
        
        # Снимаем деньги
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (clothes['price'], user_id))
        
        # Снимаем старую одежду (если была)
        cursor.execute('UPDATE user_clothes SET equipped = 0 WHERE user_id = ?', (user_id,))
        
        # Добавляем новую покупку (сразу надетую)
        cursor.execute('''
            INSERT INTO user_clothes (user_id, clothes_id, equipped)
            VALUES (?, ?, 1)
        ''', (user_id, clothes_id))
        
        # Обновляем equipped_clothes в users
        cursor.execute('UPDATE users SET equipped_clothes = ? WHERE user_id = ?', (clothes_id, user_id))
        
        conn.commit()
        conn.close()
        return True, f"✅ Поздравляем! Ты купил комплект {clothes['name']} и сразу надел его!"
    except Exception as e:
        print(f"Ошибка при покупке: {e}")
        return False, "❌ Ошибка при покупке"

def get_clothes_page(page=0):
    """Получает страницу товаров (по 1 товару на страницу)"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM shop_clothes WHERE in_shop = 1 ORDER BY id')
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

def get_clothes_navigation_keyboard(current_page, total_items):
    """Создает клавиатуру для навигации по магазину"""
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

# ========== АДМИН КОМАНДЫ ==========
@bot.message_handler(commands=['adminhelp'])
def admin_help(message):
    user_id = message.from_user.id
    level = get_admin_level(user_id)
    
    if level == 0:
        bot.reply_to(message, "❌ Эта команда только для администраторов!")
        return
    
    help_text = f"👑 **АДМИН ПАНЕЛЬ (Уровень {level})**\n\n"
    
    help_text += "**Уровень 1:**\n"
    help_text += "  /giveme [сумма] - выдать деньги себе\n"
    help_text += "  /addexpm [количество] - выдать опыт себе\n\n"
    
    if level >= 2:
        help_text += "**Уровень 2:**\n"
        help_text += "  /give [@user или ник] [сумма] - выдать деньги\n"
        help_text += "  /addexp [@user или ник] [количество] - выдать опыт\n"
        help_text += "  /profile [@user или ник] - посмотреть профиль\n\n"
    
    if level >= 3:
        help_text += "**Уровень 3:**\n"
        help_text += "  /addadmin [@user или ник] [уровень] - назначить админа\n"
        help_text += "  /adminlist - список админов\n"
        help_text += "  /reset [@user или ник] - обнулить аккаунт\n"
        help_text += "  /wipe [@user или ник] - стереть баланс и опыт\n\n"
    
    if level >= 4:
        help_text += "**Уровень 4:**\n"
        help_text += "  /removeadmin [@user или ник] - снять админа\n"
        help_text += "  /setadminlevel [@user или ник] [уровень] - изменить уровень\n"
        help_text += "  /ban [@user или ник] [часы] - забанить (0 = навсегда)\n"
        help_text += "  /unban [@user или ник] - разбанить\n"
        help_text += "  /warn [@user или ник] - выдать варн\n"
        help_text += "  /warns [@user или ник] - показать варны\n"
    
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['giveme'])
def give_me(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 1):
        bot.reply_to(message, "❌ У тебя нет прав администратора 1 уровня!")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "❌ Формат: /giveme [сумма]")
            return
        
        amount = int(parts[1])
        
        if add_balance(user_id, amount):
            new_balance = get_balance(user_id)
            bot.reply_to(message, f"✅ Выдано {amount} {CURRENCY} себе\nНовый баланс: {new_balance}")
        else:
            bot.reply_to(message, "❌ Ошибка при выдаче денег")
            
    except ValueError:
        bot.reply_to(message, "❌ Сумма должна быть числом")

@bot.message_handler(commands=['addexpm'])
def add_exp_me(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 1):
        bot.reply_to(message, "❌ У тебя нет прав администратора 1 уровня!")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "❌ Формат: /addexpm [количество]")
            return
        
        amount = int(parts[1])
        
        if add_exp(user_id, amount):
            new_stats = get_user_stats(user_id)
            bot.reply_to(message, f"✅ Выдано {amount}⭐ опыта себе\nТеперь опыта: {new_stats[0]}, уровень: {new_stats[1]}")
        else:
            bot.reply_to(message, "❌ Ошибка при выдаче опыта")
            
    except ValueError:
        bot.reply_to(message, "❌ Количество должно быть числом")

@bot.message_handler(commands=['give'])
def give_money(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 2):
        bot.reply_to(message, "❌ У тебя нет прав администратора 2 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) == 2:
            amount = int(parts[1])
            if add_balance(user_id, amount):
                new_balance = get_balance(user_id)
                bot.reply_to(message, f"✅ Выдано {amount} {CURRENCY} себе\nНовый баланс: {new_balance}")
            else:
                bot.reply_to(message, "❌ Ошибка при выдаче денег")
        
        elif len(parts) == 3:
            target_input = parts[1]
            amount = int(parts[2])
            
            user_data = find_user_by_input(target_input)
            
            if not user_data:
                bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
                return
            
            target_id = user_data[0]
            display_name = get_user_display_name(user_data)
            
            if add_balance(target_id, amount):
                new_balance = get_balance(target_id)
                bot.send_message(target_id, f"💰 Админ выдал тебе {amount} {CURRENCY}!\nБаланс: {new_balance}")
                bot.reply_to(message, f"✅ Выдано {amount} {CURRENCY} {display_name}\nНовый баланс: {new_balance}")
            else:
                bot.reply_to(message, "❌ Ошибка при выдаче денег")
        
        else:
            bot.reply_to(message, "❌ Формат: /give [сумма] - себе\n/give [@user или ник] [сумма] - другому")
            
    except ValueError:
        bot.reply_to(message, "❌ Сумма должна быть числом")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['addexp'])
def add_exp_command(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 2):
        bot.reply_to(message, "❌ У тебя нет прав администратора 2 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) == 2:
            amount = int(parts[1])
            if add_exp(user_id, amount):
                new_stats = get_user_stats(user_id)
                bot.reply_to(message, f"✅ Выдано {amount}⭐ опыта себе\nТеперь опыта: {new_stats[0]}, уровень: {new_stats[1]}")
            else:
                bot.reply_to(message, "❌ Ошибка при выдаче опыта")
        
        elif len(parts) == 3:
            target_input = parts[1]
            amount = int(parts[2])
            
            user_data = find_user_by_input(target_input)
            
            if not user_data:
                bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
                return
            
            target_id = user_data[0]
            display_name = get_user_display_name(user_data)
            
            if add_exp(target_id, amount):
                new_stats = get_user_stats(target_id)
                bot.send_message(target_id, f"⭐ Админ выдал тебе {amount} опыта!")
                bot.reply_to(message, f"✅ Выдано {amount}⭐ опыта {display_name}\nТеперь опыта: {new_stats[0]}, уровень: {new_stats[1]}")
            else:
                bot.reply_to(message, "❌ Ошибка при выдаче опыта")
        
        else:
            bot.reply_to(message, "❌ Формат: /addexp [количество] - себе\n/addexp [@user или ник] [количество] - другому")
            
    except ValueError:
        bot.reply_to(message, "❌ Количество опыта должно быть числом")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['profile'])
def profile_command(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 2):
        bot.reply_to(message, "❌ У тебя нет прав администратора 2 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) != 2:
            bot.reply_to(message, "❌ Формат: /profile [@user или ник]")
            return
        
        target_input = parts[1]
        
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        target_name = user_data[1]
        target_username = user_data[2]
        custom_name = user_data[3]
        warns = user_data[4] or 0
        
        stats = get_user_stats(target_id)
        exp, level, work_count, total = stats
        balance = get_balance(target_id)
        
        business = get_user_business(target_id)
        business_info = "Нет" if not business else f"{business['business_name']} (ур.{business['level']})"
        
        # Получаем надетую одежду
        equipped_clothes = get_user_equipped_clothes(target_id)
        clothes_info = "Нет" if not equipped_clothes else f"{equipped_clothes['name']}"
        
        # Получаем город
        current_city = get_user_city(target_id)
        
        display_name = get_user_display_name(user_data)
        
        msg = f"👤 **ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ**\n\n"
        msg += f"👤 Отображается как: {display_name}\n"
        msg += f"🆔 ID: `{target_id}`\n"
        msg += f"⚠️ Варны: {warns}/3\n"
        msg += f"👕 Одежда: {clothes_info}\n"
        msg += f"📍 Город: {current_city}\n\n"
        msg += f"💰 Баланс: {balance:,} {CURRENCY}\n"
        msg += f"⭐ Опыт: {exp}\n"
        msg += f"📈 Уровень: {level}\n"
        msg += f"🔨 Работ: {work_count}\n"
        msg += f"💵 Всего заработано: {total:,}\n"
        msg += f"🏭 Бизнес: {business_info}\n"
        
        if business:
            msg += f"📦 Сырье: {business['raw_material']}/1000\n"
            msg += f"🚚 В доставке: {business['raw_in_delivery']}\n"
            msg += f"💵 Вложено: {business['total_invested']:,}\n"
            msg += f"💎 Прибыль на складе: {business['stored_profit']:,}"
        
        bot.reply_to(message, msg, parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['addadmin'])
def add_admin_command(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 3):
        bot.reply_to(message, "❌ У тебя нет прав администратора 3 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) != 3:
            bot.reply_to(message, "❌ Формат: /addadmin [@user или ник] [уровень]")
            return
        
        target_input = parts[1]
        level = int(parts[2])
        
        if level < 1 or level > 3:
            bot.reply_to(message, "❌ Уровень должен быть от 1 до 3")
            return
        
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        
        success, msg_text = add_admin(target_id, level)
        if success:
            bot.send_message(target_id, f"👑 Вам выданы права администратора {level} уровня!\n/adminhelp - список команд")
            bot.reply_to(message, f"✅ Пользователь {display_name} теперь администратор {level} уровня!")
        else:
            bot.reply_to(message, msg_text)
            
    except ValueError:
        bot.reply_to(message, "❌ Уровень должен быть числом")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['adminlist'])
def admin_list(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 3):
        bot.reply_to(message, "❌ У тебя нет прав администратора 3 уровня!")
        return
    
    admins_info = []
    for admin_id, level in ADMINS.items():
        try:
            user_data = get_user_profile(admin_id)
            if user_data:
                display = get_user_display_name((user_data[0], user_data[1], user_data[2], user_data[3], 0))
                admins_info.append(f"• {display} - уровень {level} (`{admin_id}`)")
            else:
                admins_info.append(f"• Админ с ID: `{admin_id}` - уровень {level}")
        except:
            admins_info.append(f"• Админ с ID: `{admin_id}` - уровень {level}")
    
    msg = "👑 **СПИСОК АДМИНИСТРАТОРОВ**\n\n" + "\n".join(admins_info)
    bot.reply_to(message, msg, parse_mode="Markdown")

@bot.message_handler(commands=['reset'])
def reset_account(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 3):
        bot.reply_to(message, "❌ У тебя нет прав администратора 3 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) != 2:
            bot.reply_to(message, "❌ Формат: /reset [@user или ник]")
            return
        
        target_input = parts[1]
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM businesses WHERE user_id = ?', (target_id,))
        cursor.execute('DELETE FROM deliveries WHERE user_id = ?', (target_id,))
        cursor.execute('DELETE FROM user_clothes WHERE user_id = ?', (target_id,))
        cursor.execute('DELETE FROM travels WHERE user_id = ?', (target_id,))
        
        cursor.execute('''
            UPDATE users 
            SET balance = 0, exp = 0, level = 1, work_count = 0, 
                total_earned = 0, custom_name = NULL, equipped_clothes = NULL,
                current_city = 'Село Молочное', has_car = 0, has_plane = 0
            WHERE user_id = ?
        ''', (target_id,))
        
        conn.commit()
        conn.close()
        
        bot.send_message(target_id, "♻️ Ваш аккаунт был полностью сброшен администратором.")
        bot.reply_to(message, f"✅ Аккаунт {display_name} полностью обнулен")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['wipe'])
def wipe_account(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 3):
        bot.reply_to(message, "❌ У тебя нет прав администратора 3 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) != 2:
            bot.reply_to(message, "❌ Формат: /wipe [@user или ник]")
            return
        
        target_input = parts[1]
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE users SET balance = 0, exp = 0, level = 1 WHERE user_id = ?', (target_id,))
        
        conn.commit()
        conn.close()
        
        bot.send_message(target_id, "🧹 Ваши баланс и опыт были обнулены администратором.")
        bot.reply_to(message, f"✅ Баланс и опыт {display_name} обнулены")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['ban'])
def ban_user(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 4):
        bot.reply_to(message, "❌ У тебя нет прав администратора 4 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) not in [2, 3]:
            bot.reply_to(message, "❌ Формат: /ban [@user или ник] [часы]\n/ban [@user или ник] 0 - навсегда")
            return
        
        target_input = parts[1]
        hours = int(parts[2]) if len(parts) == 3 else 0
        
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        
        if hours == 0:
            BANS[target_id] = {'reason': 'admin', 'until': 0}
            ban_text = "навсегда"
        else:
            ban_time = datetime.now() + timedelta(hours=hours)
            BANS[target_id] = {'reason': 'admin', 'until': ban_time.timestamp()}
            ban_text = f"на {hours} ч."
        
        bot.send_message(target_id, f"🔨 Вы забанены администратором {ban_text}")
        bot.reply_to(message, f"✅ Пользователь {display_name} забанен {ban_text}")
        
    except ValueError:
        bot.reply_to(message, "❌ Часы должны быть числом")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['unban'])
def unban_user(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 4):
        bot.reply_to(message, "❌ У тебя нет прав администратора 4 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) != 2:
            bot.reply_to(message, "❌ Формат: /unban [@user или ник]")
            return
        
        target_input = parts[1]
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        
        if target_id in BANS:
            del BANS[target_id]
            bot.send_message(target_id, "✅ Вы разбанены администратором")
            bot.reply_to(message, f"✅ Пользователь {display_name} разбанен")
        else:
            bot.reply_to(message, f"❌ Пользователь не в бане")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['warn'])
def warn_user(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 4):
        bot.reply_to(message, "❌ У тебя нет прав администратора 4 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) != 2:
            bot.reply_to(message, "❌ Формат: /warn [@user или ник]")
            return
        
        target_input = parts[1]
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        
        banned, msg = add_warn(target_id)
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET warns = ? WHERE user_id = ?', (WARNS.get(target_id, 0), target_id))
        
        if banned:
            ban_until = datetime.fromtimestamp(BANS[target_id]['until']).isoformat() if BANS[target_id]['until'] != 0 else "forever"
            cursor.execute('UPDATE users SET banned_until = ? WHERE user_id = ?', (ban_until, target_id))
        
        conn.commit()
        conn.close()
        
        bot.send_message(target_id, msg)
        bot.reply_to(message, f"✅ Варн выдан {display_name}\n{msg}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['warns'])
def show_warns(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 4):
        bot.reply_to(message, "❌ У тебя нет прав администратора 4 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) != 2:
            bot.reply_to(message, "❌ Формат: /warns [@user или ник]")
            return
        
        target_input = parts[1]
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        warns = user_data[4] or 0
        
        bot.reply_to(message, f"⚠️ У {display_name} {warns}/3 варнов")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['removeadmin'])
def remove_admin_command(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 4):
        bot.reply_to(message, "❌ У тебя нет прав администратора 4 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) != 2:
            bot.reply_to(message, "❌ Формат: /removeadmin [@user или ник]")
            return
        
        target_input = parts[1]
        
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        
        if target_id == 5596589260:
            bot.reply_to(message, "❌ Нельзя снять права с главного администратора!")
            return
        
        if target_id in ADMINS:
            del ADMINS[target_id]
            bot.send_message(target_id, "👑 Ваши права администратора были сняты")
            bot.reply_to(message, f"✅ Права администратора сняты с {display_name}")
        else:
            bot.reply_to(message, f"❌ Пользователь не является администратором")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['setadminlevel'])
def set_admin_level_command(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 4):
        bot.reply_to(message, "❌ У тебя нет прав администратора 4 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) != 3:
            bot.reply_to(message, "❌ Формат: /setadminlevel [@user или ник] [уровень]")
            return
        
        target_input = parts[1]
        level = int(parts[2])
        
        if level < 1 or level > 4:
            bot.reply_to(message, "❌ Уровень должен быть от 1 до 4")
            return
        
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        
        if target_id == 5596589260:
            bot.reply_to(message, "❌ Нельзя изменить уровень главного администратора!")
            return
        
        if target_id in ADMINS:
            ADMINS[target_id] = level
            bot.send_message(target_id, f"👑 Ваш уровень администратора изменен на {level}")
            bot.reply_to(message, f"✅ Уровень администратора {display_name} изменен на {level}")
        else:
            bot.reply_to(message, f"❌ Пользователь не является администратором")
            
    except ValueError:
        bot.reply_to(message, "❌ Уровень должен быть числом")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# ========== КОМАНДА ТОП ==========
@bot.message_handler(commands=['top'])
def top_command(message):
    user_id = message.from_user.id
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💰 Топ по деньгам", callback_data="top_money"),
        types.InlineKeyboardButton("⭐ Топ по опыту", callback_data="top_exp")
    )
    
    bot.send_message(
        user_id,
        "🏆 **ВЫБЕРИ ТОП**\n\n"
        "По какому показателю показать рейтинг?",
        parse_mode="Markdown",
        reply_markup=markup
    )

def send_top_by_type(user_id, top_type):
    """Отправляет топ по указанному типу"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        if top_type == "money":
            cursor.execute('''
                SELECT first_name, username, custom_name, balance 
                FROM users 
                ORDER BY balance DESC 
                LIMIT 10
            ''')
            title = "💰 ТОП 10 ПО ДЕНЬГАМ"
            value_name = "Баланс"
        else:  # exp
            cursor.execute('''
                SELECT first_name, username, custom_name, exp 
                FROM users 
                ORDER BY exp DESC 
                LIMIT 10
            ''')
            title = "⭐ ТОП 10 ПО ОПЫТУ"
            value_name = "Опыт"
        
        top = cursor.fetchall()
        conn.close()
        
        if not top:
            bot.send_message(user_id, "❌ В топе пока никого нет!")
            return
        
        msg = f"🏆 **{title}**\n\n"
        for i, (first_name, username, custom_name, value) in enumerate(top, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            if custom_name:
                display_name = custom_name
            elif username and username != "NoUsername":
                display_name = f"@{username}"
            else:
                display_name = first_name
            
            msg += f"{medal} {display_name}: {value:,}\n"
        
        bot.send_message(user_id, msg, parse_mode="Markdown")
        
    except Exception as e:
        print(f"Ошибка топа: {e}")
        bot.send_message(user_id, "❌ Ошибка загрузки топа")

# ========== КЛАВИАТУРЫ ==========
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(
        types.KeyboardButton("💼 Работы"),
        types.KeyboardButton("🏭 Бизнесы")
    )
    markup.row(
        types.KeyboardButton("📊 Статистика"),
        types.KeyboardButton("🏙️ ГОРОДА")  # Вместо рефералов
    )
    markup.row(
        types.KeyboardButton("🎁 Ежедневно"),
        types.KeyboardButton("⚙️ Настройки")
    )
    markup.row(
        types.KeyboardButton("👕 МАГАЗИН ОДЕЖДЫ"),
        types.KeyboardButton("🔄")
    )
    return markup

def cities_keyboard():
    """Клавиатура выбора города"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(
        types.KeyboardButton("🏙️ Кропоткин"),
        types.KeyboardButton("🏙️ Москва")
    )
    markup.row(
        types.KeyboardButton("🏙️ Мурино"),
        types.KeyboardButton("🏙️ Село Молочное")
    )
    markup.row(types.KeyboardButton("🔙 Назад"))
    return markup

def transport_keyboard(city):
    """Клавиатура выбора транспорта"""
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

def city_menu_keyboard(city_name):
    """Клавиатура меню города"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    city_info = get_city_info(city_name)
    
    # Базовые кнопки для всех городов
    markup.row(
        types.KeyboardButton("💼 Работы"),
        types.KeyboardButton("🏭 Бизнесы")
    )
    markup.row(
        types.KeyboardButton("📊 Статистика"),
        types.KeyboardButton("👕 Магазин одежды")
    )
    
    # Дополнительные кнопки в зависимости от города
    extra_buttons = []
    if city_info and city_info['has_house_shop']:
        extra_buttons.append("🏠 Магазин домов")
    if city_info and city_info['has_plane_shop']:
        extra_buttons.append("✈️ Магазин самолетов")
    
    if extra_buttons:
        markup.row(*[types.KeyboardButton(btn) for btn in extra_buttons])
    
    markup.row(
        types.KeyboardButton("🎁 Ежедневно"),
        types.KeyboardButton("⚙️ Настройки")
    )
    markup.row(
        types.KeyboardButton("🔙 Назад"),
        types.KeyboardButton("🔄")
    )
    return markup

def jobs_keyboard(user_id):
    jobs = get_available_jobs(user_id)
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    for job in jobs:
        markup.add(types.KeyboardButton(f"{job[5]} {job[0]}"))
    
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
        types.KeyboardButton("✏️ Сменить никнейм")
    )
    markup.row(
        types.KeyboardButton("📋 Помощь")
    )
    markup.row(
        types.KeyboardButton("🔙 Назад")
    )
    return markup

# ========== СТАРТ ==========
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    
    if is_banned(user_id):
        ban_info = BANS.get(user_id, {})
        if ban_info.get('until') == 0:
            bot.reply_to(message, "🔨 Вы забанены навсегда.")
        else:
            until = datetime.fromtimestamp(ban_info['until'])
            bot.reply_to(message, f"🔨 Вы забанены до {until.strftime('%d.%m.%Y %H:%M')}")
        return
    
    username = message.from_user.username or "NoUsername"
    first_name = message.from_user.first_name
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, balance, exp, level, work_count, total_earned, current_city)
            VALUES (?, ?, ?, 0, 0, 1, 0, 0, 'Село Молочное')
        ''', (user_id, username, first_name))
        conn.commit()
        conn.close()
        
        welcome_text = (
            "🌟 **ДОБРО ПОЖАЛОВАТЬ В МИР SuguruCoins!** 🌟\n\n"
            f"👋 Рады видеть тебя, {first_name}!\n\n"
            "🎮 Здесь ты сможешь:\n"
            "💼 **Работать** и зарабатывать деньги\n"
            "🏭 **Покупать бизнесы** и получать пассивный доход\n"
            "🏙️ **Путешествовать по городам** и открывать новые магазины\n"
            "👕 **Покупать крутую одежду** и менять свой стиль\n"
            "🏆 **Соревноваться** с другими игроками (/top)\n\n"
            "✨ Но сначала выбери себе игровой никнейм!\n"
            "Он будет отображаться в топе и в игре."
        )
        
        bot.send_message(user_id, welcome_text, parse_mode="Markdown")
        
        markup = types.ForceReply(selective=True)
        msg = bot.send_message(
            user_id, 
            "🔤 **Напиши свой игровой никнейм:**\n\n"
            "📝 Он может быть любым (буквы, цифры, символы)\n"
            "✨ Например: `DarkKnight`, `КиберПанк`, `SuguruKing`\n\n"
            "⚠️ **Важно:** Никнейм должен быть **уникальным**!",
            parse_mode="Markdown",
            reply_markup=markup
        )
        
        bot.register_next_step_handler(msg, process_name_step)
        
    else:
        conn.close()
        level = get_admin_level(user_id)
        
        welcome_text = f"👋 С возвращением, {first_name}!"
        
        if level > 0:
            welcome_text += f"\n\n👑 У вас права администратора {level} уровня!\n/adminhelp - список команд админа"
        
        bot.send_message(user_id, welcome_text)
        send_main_menu_with_profile(user_id)

def process_name_step(message):
    user_id = message.from_user.id
    custom_name = message.text.strip()
    
    if len(custom_name) < 2 or len(custom_name) > 30:
        bot.send_message(
            user_id, 
            "❌ Никнейм должен быть от 2 до 30 символов!\n\nПопробуй еще раз:"
        )
        bot.register_next_step_handler(message, process_name_step)
        return
    
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_ -!@#$%^&*()")
    if not all(c in allowed_chars for c in custom_name):
        bot.send_message(
            user_id,
            "❌ Никнейм содержит недопустимые символы!\n\n"
            "Разрешены: буквы, цифры, пробел и символы _ - ! @ # $ % ^ & * ( )\n\nПопробуй еще раз:"
        )
        bot.register_next_step_handler(message, process_name_step)
        return
    
    existing_user = get_user_by_custom_name(custom_name)
    if existing_user:
        bot.send_message(
            user_id,
            f"❌ Никнейм **{custom_name}** уже занят другим игроком!\n\n"
            "Пожалуйста, выбери другой никнейм:",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(message, process_name_step)
        return
    
    if set_custom_name(user_id, custom_name):
        success_text = (
            f"✅ **Отлично!** Твой никнейм `{custom_name}` сохранен!\n\n"
            "🎉 Теперь ты готов к приключениям!\n"
            "💰 У тебя 0 монет, но это временно.\n"
            "💪 Работай, зарабатывай, покупай бизнесы и путешествуй по городам!\n"
            "👕 Загляни в **МАГАЗИН ОДЕЖДЫ** - там есть очень крутые комплекты!\n\n"
            "👇 Твоё главное меню с фото профиля:"
        )
        bot.send_message(user_id, success_text, parse_mode="Markdown")
        send_main_menu_with_profile(user_id)
    else:
        bot.send_message(
            user_id,
            "❌ Произошла ошибка при сохранении ника. Попробуй еще раз /start"
        )

def change_nickname_step(message):
    user_id = message.from_user.id
    new_nickname = message.text.strip()
    
    if len(new_nickname) < 2 or len(new_nickname) > 30:
        bot.send_message(
            user_id, 
            "❌ Никнейм должен быть от 2 до 30 символов!\n\nПопробуй еще раз:"
        )
        bot.register_next_step_handler(message, change_nickname_step)
        return
    
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_ -!@#$%^&*()")
    if not all(c in allowed_chars for c in new_nickname):
        bot.send_message(
            user_id,
            "❌ Никнейм содержит недопустимые символы!\n\n"
            "Разрешены: буквы, цифры, пробел и символы _ - ! @ # $ % ^ & * ( )\n\nПопробуй еще раз:"
        )
        bot.register_next_step_handler(message, change_nickname_step)
        return
    
    existing_user = get_user_by_custom_name(new_nickname)
    if existing_user:
        bot.send_message(
            user_id,
            f"❌ Никнейм **{new_nickname}** уже занят другим игроком!\n\n"
            "Пожалуйста, выбери другой никнейм:",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(message, change_nickname_step)
        return
    
    user_data = get_user_profile(user_id)
    old_nickname = user_data[3] if user_data and user_data[3] else "Не установлен"
    
    if set_custom_name(user_id, new_nickname):
        success_text = (
            f"✅ **Никнейм успешно изменен!**\n\n"
            f"🔄 Старый ник: `{old_nickname}`\n"
            f"✨ Новый ник: `{new_nickname}`\n\n"
            f"Теперь ты будешь отображаться в игре под новым именем!"
        )
        bot.send_message(user_id, success_text, parse_mode="Markdown", reply_markup=settings_keyboard())
    else:
        bot.send_message(
            user_id,
            "❌ Произошла ошибка при сохранении ника. Попробуй еще раз."
        )
        bot.register_next_step_handler(message, change_nickname_step)

# ========== ОБРАБОТЧИК КОЛБЭКОВ ==========
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if is_banned(user_id):
        bot.answer_callback_query(call.id, "🔨 Вы забанены!", show_alert=True)
        return
    
    data = call.data
    
    # Обработка топов
    if data == "top_money":
        bot.delete_message(user_id, call.message.message_id)
        send_top_by_type(user_id, "money")
        bot.answer_callback_query(call.id)
    
    elif data == "top_exp":
        bot.delete_message(user_id, call.message.message_id)
        send_top_by_type(user_id, "exp")
        bot.answer_callback_query(call.id)
    
    # Навигация по магазину
    elif data.startswith("shop_page_"):
        page = int(data.split("_")[2])
        clothes, current_page, total = get_clothes_page(page)
        
        if clothes:
            caption = (f"👕 *{clothes['name']}*\n\n"
                      f"💰 Цена: {clothes['price']:,} {CURRENCY}\n\n"
                      f"🛍️ Всего комплектов: {total}")
            
            try:
                bot.edit_message_media(
                    types.InputMediaPhoto(media=clothes['photo_url'], caption=caption, parse_mode="Markdown"),
                    chat_id=user_id,
                    message_id=call.message.message_id,
                    reply_markup=get_clothes_navigation_keyboard(current_page, total)
                )
            except:
                bot.send_photo(
                    user_id,
                    clothes['photo_url'],
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=get_clothes_navigation_keyboard(current_page, total)
                )
                bot.delete_message(user_id, call.message.message_id)
        
        bot.answer_callback_query(call.id)
    
    # Покупка
    elif data.startswith("shop_buy_"):
        page = int(data.split("_")[2])
        clothes, current_page, total = get_clothes_page(page)
        
        if clothes:
            # Проверяем, не куплена ли уже эта одежда
            conn = get_db()
            cursor = conn.cursor()
            existing = cursor.execute('''
                SELECT id FROM user_clothes 
                WHERE user_id = ? AND clothes_id = ?
            ''', (user_id, clothes['id'])).fetchone()
            
            if existing:
                conn.close()
                bot.answer_callback_query(call.id, "❌ У тебя уже есть этот комплект!", show_alert=True)
                return
            
            conn.close()
            
            # Пытаемся купить
            success, message_text = buy_clothes(user_id, clothes['id'])
            
            if success:
                # Обновляем сообщение
                caption = (f"👕 *{clothes['name']}*\n\n"
                          f"💰 Цена: {clothes['price']:,} {CURRENCY}\n\n"
                          f"✅ *КУПЛЕНО!* Комплект надет на тебя!")
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("◀️ В магазин", callback_data=f"shop_page_{current_page}"))
                markup.add(types.InlineKeyboardButton("❌ Закрыть", callback_data="shop_close"))
                
                try:
                    bot.edit_message_media(
                        types.InputMediaPhoto(media=clothes['photo_url'], caption=caption, parse_mode="Markdown"),
                        chat_id=user_id,
                        message_id=call.message.message_id,
                        reply_markup=markup
                    )
                except:
                    pass
                
                bot.answer_callback_query(call.id, "✅ Покупка успешна!", show_alert=True)
            else:
                bot.answer_callback_query(call.id, message_text, show_alert=True)
    
    # Закрыть магазин
    elif data == "shop_close":
        bot.delete_message(user_id, call.message.message_id)
        send_main_menu_with_profile(user_id)
        bot.answer_callback_query(call.id)
    
    # Заглушка для неактивных кнопок
    elif data == "noop":
        bot.answer_callback_query(call.id)

# ========== ОСНОВНОЙ ОБРАБОТЧИК ==========
@bot.message_handler(func=lambda message: True)
def handle(message):
    user_id = message.from_user.id
    text = message.text
    
    if is_banned(user_id):
        ban_info = BANS.get(user_id, {})
        if ban_info.get('until') == 0:
            bot.reply_to(message, "🔨 Вы забанены навсегда.")
        else:
            until = datetime.fromtimestamp(ban_info['until'])
            bot.reply_to(message, f"🔨 Вы забанены до {until.strftime('%d.%m.%Y %H:%M')}")
        return
    
    print(f"Получено сообщение: {text} от {user_id}")
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
        conn.commit()
        conn.close()
    except:
        pass
    
    user_data = get_user_profile(user_id)
    display_name = get_user_display_name(user_data) if user_data else "Игрок"
    
    # Проверяем, нет ли активной поездки
    active_travel = get_active_travel(user_id)
    if active_travel:
        # Проверяем, не пора ли прибыть
        end_time = datetime.fromisoformat(active_travel['end_time'])
        if datetime.now() >= end_time:
            complete_travel(active_travel['id'], user_id)
            # После завершения показываем меню города прибытия
            current_city = get_user_city(user_id)
            bot.send_message(
                user_id,
                f"🏙️ Ты находишься в городе {current_city}",
                reply_markup=city_menu_keyboard(current_city)
            )
            return
    
    # ===== ГОРОДА =====
    if text == "🏙️ ГОРОДА":
        markup = cities_keyboard()
        bot.send_message(
            user_id,
            "🏙️ **ВЫБЕРИ ГОРОД**\n\n"
            "Куда хочешь отправиться?",
            parse_mode="Markdown",
            reply_markup=markup
        )
    
    # Выбор конкретного города
    elif text in ["🏙️ Кропоткин", "🏙️ Москва", "🏙️ Мурино", "🏙️ Село Молочное"]:
        city_name = text.replace("🏙️ ", "")
        current_city = get_user_city(user_id)
        
        if city_name == current_city:
            # Если уже в этом городе - сразу показываем меню
            bot.send_message(
                user_id,
                f"🏙️ Ты уже находишься в городе {city_name}",
                reply_markup=city_menu_keyboard(city_name)
            )
        else:
            # Если в другом - предлагаем выбрать транспорт
            bot.send_message(
                user_id,
                f"🚀 Выбери транспорт для поездки в {city_name}:",
                reply_markup=transport_keyboard(city_name)
            )
            # Сохраняем выбранный город в контексте (через следующий шаг)
            bot.register_next_step_handler(message, process_travel, city_name)
    
    # ===== ТРАНСПОРТ =====
    elif text in ["🚕 Такси", "🚗 Личная машина", "✈️ Личный самолет"]:
        # Этот случай обрабатывается в process_travel
        pass
    
    # ===== МЕНЮ ГОРОДА =====
    elif text == "👕 Магазин одежды":
        # Магазин одежды (работает в любом городе)
        clothes, current_page, total = get_clothes_page(0)
        
        if clothes:
            welcome_text = ("🛍️ **ДОБРО ПОЖАЛОВАТЬ В МАГАЗИН ОДЕЖДЫ!**\n\n"
                           "Мы подобрали самые лучшие и красивые комплекты одежды.\n"
                           "Выберите какой вам понравится и нажмите купить!\n\n"
                           "👉 При покупке комплект сразу надевается на тебя!")
            
            bot.send_message(user_id, welcome_text, parse_mode="Markdown")
            
            caption = (f"👕 *{clothes['name']}*\n\n"
                      f"💰 Цена: {clothes['price']:,} {CURRENCY}\n\n"
                      f"🛍️ Всего комплектов: {total}")
            
            bot.send_photo(
                user_id,
                clothes['photo_url'],
                caption=caption,
                parse_mode="Markdown",
                reply_markup=get_clothes_navigation_keyboard(current_page, total)
            )
        else:
            bot.send_message(user_id, "❌ В магазине пока нет товаров!")
    
    elif text == "🏠 Магазин домов":
        bot.send_message(user_id, "🏠 Магазин домов скоро откроется! Следи за обновлениями!")
    
    elif text == "✈️ Магазин самолетов":
        bot.send_message(user_id, "✈️ Магазин самолетов скоро откроется! Следи за обновлениями!")
    
    # ===== КНОПКА ОБНОВЛЕНИЯ =====
    elif text == "🔄":
        current_city = get_user_city(user_id)
        send_main_menu_with_profile(user_id)
    
    # ===== РАБОТЫ =====
    elif text == "💼 Работы":
        bot.send_message(user_id, "🔨 Выбери работу:", reply_markup=jobs_keyboard(user_id))
    
    # ===== БИЗНЕСЫ =====
    elif text == "🏭 Бизнесы":
        bot.send_message(user_id, "🏪 Управление бизнесом:", reply_markup=businesses_main_keyboard())
    
    # ===== СТАТИСТИКА =====
    elif text == "📊 Статистика":
        exp, level, work_count, total = get_user_stats(user_id)
        equipped = get_user_equipped_clothes(user_id)
        clothes_info = f", одет: {equipped['name']}" if equipped else ""
        current_city = get_user_city(user_id)
        
        msg = f"📊 **СТАТИСТИКА**\n\n"
        msg += f"👤 Игрок: {display_name}{clothes_info}\n"
        msg += f"📍 Город: {current_city}\n"
        msg += f"⭐ Опыт: {exp}\n"
        msg += f"📈 Уровень: {level}\n"
        msg += f"🔨 Работ: {work_count}\n"
        msg += f"💰 Всего заработано: {total:,}"
        bot.send_message(user_id, msg, parse_mode="Markdown")
    
    # ===== ЕЖЕДНЕВНО =====
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
                    bot.send_message(user_id, f"⏳ След. бонус через {hours}ч {minutes}м")
                    conn.close()
                    return
            
            bonus = random.randint(500, 2000)
            bonus_exp = random.randint(50, 200)
            cursor.execute('UPDATE users SET balance = balance + ?, exp = exp + ?, last_daily = ? WHERE user_id = ?', 
                          (bonus, bonus_exp, now, user_id))
            conn.commit()
            conn.close()
            bot.send_message(user_id, f"🎁 Бонус: +{bonus} {CURRENCY} и +{bonus_exp}⭐!")
        except Exception as e:
            print(f"Ошибка daily: {e}")
            bot.send_message(user_id, "❌ Ошибка")
    
    # ===== НАСТРОЙКИ =====
    elif text == "⚙️ Настройки":
        bot.send_message(user_id, "🔧 **НАСТРОЙКИ**\n\nВыбери что хочешь изменить:", reply_markup=settings_keyboard(), parse_mode="Markdown")
    
    elif text == "✏️ Сменить никнейм":
        current_nick = display_name if display_name != "Игрок" else "Не установлен"
        msg = bot.send_message(
            user_id,
            f"🎮 **СМЕНА ИГРОВОГО НИКНЕЙМА**\n\n"
            f"Текущий ник: `{current_nick}`\n\n"
            f"🔤 **Напиши новый никнейм:**\n\n"
            f"📝 Он может быть любым (буквы, цифры, символы)\n"
            f"✨ Например: `DarkKnight`, `КиберПанк`, `SuguruKing`\n\n"
            f"⚠️ **Важно:** Никнейм должен быть **уникальным**!",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, change_nickname_step)
    
    elif text == "📋 Помощь":
        help_text = (
            "📚 **ПОЛНОЕ РУКОВОДСТВО ПО ИГРЕ** 📚\n\n"
            "💼 **РАБОТЫ**\n"
            "• Доступно 10 видов работ\n"
            "• Каждая работа дает деньги и опыт\n"
            "• Чем выше опыт - тем круче работы открываются\n"
            "• Работы можно выполнять бесконечно\n\n"
            "🏭 **БИЗНЕСЫ**\n"
            "• Можно купить только один бизнес\n"
            "• 5 видов бизнеса\n"
            "• У каждого бизнеса 3 уровня прокачки\n"
            "• Склад вмещает максимум 1000 сырья\n"
            "• Доставка сырья - 15 минут\n"
            "• Прибыль накапливается на складе, нужно собирать вручную\n\n"
            "📊 **ДАННЫЕ БИЗНЕСОВ**\n"
            "🥤 Киоск - 500к | 1 сырьё = 1.000💰 | профит 2.000💰\n"
            "🍔 Фастфуд - 5M | 1 сырьё = 2.500💰 | профит 5.000💰\n"
            "🏪 Минимаркет - 15M | 1 сырьё = 30.000💰 | профит 60.000💰\n"
            "⛽ Заправка - 50M | 1 сырьё = 200.000💰 | профит 400.000💰\n"
            "🏨 Отель - 1B | 1 сырьё = 1.000.000💰 | профит 2.000.000💰\n\n"
            "🏙️ **ГОРОДА**\n"
            "• Можно путешествовать между 4 городами\n"
            "• В каждом городе свои магазины\n"
            "• Время в пути: 30-60 секунд\n"
            "• Транспорт: Такси, Личная машина, Личный самолет\n\n"
            "👕 **МАГАЗИН ОДЕЖДЫ**\n"
            "• Покупай крутые комплекты одежды\n"
            "• При покупке комплект сразу надевается\n"
            "• Одежда видна в главном меню и статистике\n\n"
            "🏆 **ТОП 10** (команда /top)\n"
            "• Можно выбрать топ по деньгам или по опыту\n"
            "• Соревнуйся с другими игроками\n\n"
            "🎁 **ЕЖЕДНЕВНЫЙ БОНУС**\n"
            "• Получай бонус раз в 24 часа\n"
            "• Рандомный бонус от 500 до 2000💰\n"
            "• Дополнительно 50-200⭐ опыта"
        )
        bot.send_message(user_id, help_text, parse_mode="Markdown")
    
    elif text == "❓ Помощь":
        help_text = "🤖 **ПОМОЩЬ**\n\n"
        help_text += "💼 Работы - зарабатывай деньги и опыт (открываются с опытом)\n"
        help_text += "🏭 Бизнесы - управление бизнесом\n"
        help_text += "🏙️ Города - путешествуй между городами\n"
        help_text += "👕 Магазин одежды - покупай крутые комплекты\n"
        help_text += "📊 Статистика - твои показатели\n"
        help_text += "🏆 Топ 10 - лучшие игроки (команда /top)\n"
        help_text += "🎁 Ежедневно - бонус каждый день\n"
        help_text += "⚙️ Настройки - изменить никнейм и полная помощь\n"
        help_text += "🔄 - обновить главное меню с фото профиля"
        
        level = get_admin_level(user_id)
        if level > 0:
            help_text += f"\n\n👑 У вас права администратора {level} уровня!\n/adminhelp - список команд админа"
        
        bot.send_message(user_id, help_text, parse_mode="Markdown")
    
    # ===== РАБОТЫ =====
    elif any(job in text for job in ["🚚 Грузчик", "🧹 Уборщик", "📦 Курьер", "🔧 Механик", "💻 Программист", "🕵️ Детектив", "👨‍🔧 Инженер", "👨‍⚕️ Врач", "👨‍🎤 Артист", "👨‍🚀 Космонавт"]):
        rewards = {
            "🚚 Грузчик": (10, 50, 5),
            "🧹 Уборщик": (15, 70, 7),
            "📦 Курьер": (20, 100, 10),
            "🔧 Механик": (30, 150, 12),
            "💻 Программист": (50, 300, 15),
            "🕵️ Детектив": (100, 500, 20),
            "👨‍🔧 Инженер": (200, 800, 25),
            "👨‍⚕️ Врач": (300, 1200, 30),
            "👨‍🎤 Артист": (500, 2000, 35),
            "👨‍🚀 Космонавт": (1000, 5000, 50)
        }
        
        job_name = None
        for name in rewards.keys():
            if name in text:
                job_name = name
                break
        
        if job_name:
            min_r, max_r, exp_r = rewards[job_name]
            earn = random.randint(min_r, max_r)
            
            if add_balance(user_id, earn) and add_exp(user_id, exp_r):
                bot.send_message(user_id, f"✅ {job_name}\n💰 +{earn}\n⭐ +{exp_r} опыта")
            else:
                bot.send_message(user_id, "❌ Ошибка, попробуй позже")
    
    # ===== УПРАВЛЕНИЕ БИЗНЕСОМ =====
    elif text == "📊 Мой бизнес":
        business = get_user_business(user_id)
        if not business:
            bot.send_message(user_id, "📭 У тебя еще нет бизнеса!")
            return
        
        data = get_business_data(business['business_name'])
        if not data:
            bot.send_message(user_id, "❌ Ошибка загрузки данных бизнеса")
            return
        
        speed_multiplier = {1: 1.0, 2: 1.2, 3: 2.0}
        current_speed = speed_multiplier.get(business['level'], 1.0)
        time_per_raw = data['base_time'] / current_speed
        
        total_raw = business['raw_material'] + business['raw_in_delivery']
        total_potential = business['raw_material'] * data['profit_per_raw']
        
        msg = f"{data['emoji']} **{business['business_name']}**\n\n"
        msg += f"📊 Уровень: {business['level']}\n"
        msg += f"⏱️ Время на 1 сырье: {time_per_raw:.0f} сек\n"
        msg += f"📦 На складе: {business['raw_material']}/1000 сырья\n"
        msg += f"🚚 В доставке: {business['raw_in_delivery']} сырья\n"
        msg += f"📊 Всего: {total_raw}/1000\n"
        msg += f"💰 Прибыль на складе: {business['stored_profit']:,} {CURRENCY}\n"
        msg += f"💵 Всего вложено: {business['total_invested']:,} {CURRENCY}\n"
        msg += f"🎯 Потенциальная прибыль: {total_potential:,} {CURRENCY}"
        
        bot.send_message(user_id, msg, parse_mode="Markdown")
    
    elif text == "💰 Собрать прибыль":
        business = get_user_business(user_id)
        if not business:
            bot.send_message(user_id, "📭 У тебя еще нет бизнеса!")
            return
        
        if business['stored_profit'] <= 0:
            bot.send_message(user_id, "❌ На складе нет прибыли! Сырье еще перерабатывается.")
            return
        
        profit = business['stored_profit']
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE businesses SET stored_profit = 0 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        add_balance(user_id, profit)
        
        bot.send_message(user_id, f"✅ Ты собрал {profit:,} {CURRENCY} прибыли с бизнеса!")
    
    elif text == "📦 Закупить на всё":
        business = get_user_business(user_id)
        if not business:
            bot.send_message(user_id, "❌ Сначала купи бизнес!")
            return
        
        data = get_business_data(business['business_name'])
        if not data:
            bot.send_message(user_id, "❌ Ошибка загрузки данных бизнеса")
            return
        
        balance = get_balance(user_id)
        raw_cost = data['raw_cost_per_unit']
        max_by_money = balance // raw_cost
        
        total_raw = business['raw_material'] + business['raw_in_delivery']
        free_space = 1000 - total_raw
        
        amount = min(max_by_money, free_space)
        
        if amount <= 0:
            if free_space <= 0:
                bot.send_message(user_id, f"❌ Склад переполнен! Свободно места: 0/1000")
            else:
                bot.send_message(user_id, f"❌ У тебя недостаточно денег! Нужно минимум {raw_cost:,} {CURRENCY}")
            return
        
        total_cost = amount * raw_cost
        
        if not add_balance(user_id, -total_cost):
            bot.send_message(user_id, "❌ Ошибка при списании денег")
            return
        
        if has_active_delivery(user_id):
            bot.send_message(user_id, "❌ У тебя уже есть активная доставка! Дождись её завершения.")
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
        
        new_total = total_raw + amount
        bot.send_message(user_id, f"✅ Заказ на {amount} сырья оформлен!\n💰 Стоимость: {total_cost:,} {CURRENCY}\n📦 Будет: {new_total}/1000\n⏱️ Доставка через 15 минут")
    
    elif text == "🏪 Купить бизнес":
        bot.send_message(user_id, "Выбери бизнес для покупки:", reply_markup=buy_business_keyboard())
    
    elif text == "💰 Продать бизнес":
        business = get_user_business(user_id)
        if not business:
            bot.send_message(user_id, "❌ У тебя нет бизнеса!")
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
                bot.send_message(user_id, f"💰 Бизнес продан за {sell_price:,} {CURRENCY}!")
            except Exception as e:
                print(f"Ошибка при продаже: {e}")
                bot.send_message(user_id, "❌ Ошибка при продаже")
                add_balance(user_id, -sell_price)
    
    # ===== ПОКУПКА БИЗНЕСА =====
    elif text in ["🥤 Киоск", "🍔 Фастфуд", "🏪 Минимаркет", "⛽ Заправка", "🏨 Отель"]:
        
        if get_user_business(user_id):
            bot.send_message(user_id, "❌ У тебя уже есть бизнес!")
            return
        
        data = get_business_data(text)
        if not data:
            bot.send_message(user_id, "❌ Бизнес не найден")
            return
        
        price = data['price']
        balance = get_balance(user_id)
        
        if balance < price:
            bot.send_message(user_id, f"❌ Не хватает {price - balance:,}💰")
            return
        
        if add_balance(user_id, -price):
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO businesses (user_id, business_name, level, raw_material, raw_in_delivery, raw_spent, total_invested, stored_profit, last_update)
                    VALUES (?, ?, 1, 0, 0, 0, 0, 0, ?)
                ''', (user_id, text, datetime.now().isoformat()))
                conn.commit()
                conn.close()
                bot.send_message(user_id, f"✅ Ты купил {text} за {price:,}💰!")
            except Exception as e:
                print(f"Ошибка при покупке: {e}")
                bot.send_message(user_id, "❌ Ошибка при покупке")
                add_balance(user_id, price)
    
    # ===== ВОЗВРАЩЕНИЕ В ГЛАВНОЕ МЕНЮ =====
    elif text == "🔙 Назад":
        # Проверяем, откуда вернулись
        if "🏙️" in text or "🚕" in text or "🚗" in text or "✈️" in text:
            # Если из городов - показываем главное меню
            send_main_menu_with_profile(user_id)
        else:
            # Если из других разделов - показываем меню текущего города
            current_city = get_user_city(user_id)
            bot.send_message(
                user_id,
                f"🏙️ Ты в городе {current_city}",
                reply_markup=city_menu_keyboard(current_city)
            )

def process_travel(message, target_city):
    """Обрабатывает выбор транспорта и начинает поездку"""
    user_id = message.from_user.id
    transport = message.text
    
    if transport not in ["🚕 Такси", "🚗 Личная машина", "✈️ Личный самолет"]:
        bot.send_message(user_id, "❌ Пожалуйста, выбери транспорт из предложенных!")
        bot.register_next_step_handler(message, process_travel, target_city)
        return
    
    if transport == "🔙 Назад":
        send_main_menu_with_profile(user_id)
        return
    
    # Начинаем поездку
    success, msg = start_travel(user_id, target_city, transport)
    
    if success:
        bot.send_message(user_id, msg)
        # Показываем ожидание (главное меню с городом откуда уехали)
        current_city = get_user_city(user_id)
        bot.send_message(
            user_id,
            f"⏳ Ты в пути... Прибудешь через некоторое время.\n"
            f"📍 Текущий город: {current_city}",
            reply_markup=main_keyboard()
        )
    else:
        bot.send_message(user_id, msg)
        # Возвращаем в меню городов
        bot.send_message(
            user_id,
            "🏙️ Выбери город:",
            reply_markup=cities_keyboard()
        )

# ========== ФОНОВАЯ ПРОВЕРКА ПОЕЗДОК ==========
def check_travels():
    """Проверяет завершенные поездки"""
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            travels = cursor.execute('''
                SELECT * FROM travels 
                WHERE completed = 0 AND end_time <= ?
            ''', (datetime.now().isoformat(),)).fetchall()
            
            for t in travels:
                # Завершаем поездку
                cursor.execute('UPDATE users SET current_city = ? WHERE user_id = ?', 
                             (t['to_city'], t['user_id']))
                cursor.execute('UPDATE travels SET completed = 1 WHERE id = ?', (t['id'],))
                
                try:
                    bot.send_message(
                        t['user_id'],
                        f"✅ Вы прибыли в {t['to_city']}!\n"
                        f"Транспорт: {t['transport']}",
                        reply_markup=city_menu_keyboard(t['to_city'])
                    )
                except:
                    pass
                
                conn.commit()
            
            conn.close()
            time.sleep(5)  # Проверяем каждые 5 секунд
        except Exception as e:
            print(f"Ошибка проверки поездок: {e}")
            time.sleep(5)

# ========== ФОНОВАЯ ПЕРЕРАБОТКА СЫРЬЯ ==========
def process_raw_material():
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()
            businesses = cursor.execute('SELECT * FROM businesses').fetchall()
            
            for b in businesses:
                if b['raw_material'] > 0:
                    data = get_business_data(b['business_name'])
                    if data:
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
                                try:
                                    bot.send_message(b['user_id'], "🎉 Твой бизнес достиг 2 уровня! Скорость +20%!")
                                except:
                                    pass
                            elif total_spent >= 200000 and b['level'] == 2:
                                cursor.execute('UPDATE businesses SET level = 3 WHERE user_id = ?', (b['user_id'],))
                                try:
                                    bot.send_message(b['user_id'], "🎉 Твой бизнес достиг 3 уровня! Скорость +100%!")
                                except:
                                    pass
                            
                            conn.commit()
            
            conn.close()
            time.sleep(10)
        except Exception as e:
            print(f"Ошибка переработки: {e}")
            time.sleep(10)

# ========== ФОНОВАЯ ПРОВЕРКА ДОСТАВОК ==========
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
                cursor.execute('''
                    UPDATE businesses 
                    SET raw_material = raw_material + ?,
                        raw_in_delivery = raw_in_delivery - ?
                    WHERE user_id = ?
                ''', (d['amount'], d['amount'], d['user_id']))
                
                cursor.execute('UPDATE deliveries SET delivered = 1 WHERE id = ?', (d['id'],))
                
                try:
                    business = get_user_business(d['user_id'])
                    if business:
                        total_raw = business['raw_material'] + d['amount']
                        bot.send_message(
                            d['user_id'],
                            f"✅ Сырье доставлено на склад!\n📦 +{d['amount']} сырья\n📦 Теперь на складе: {total_raw}/1000"
                        )
                except:
                    pass
            
            conn.commit()
            conn.close()
            time.sleep(30)
        except Exception as e:
            print(f"Ошибка в доставках: {e}")
            time.sleep(30)

# Запускаем фоновые потоки
threading.Thread(target=process_raw_material, daemon=True).start()
threading.Thread(target=check_deliveries, daemon=True).start()
threading.Thread(target=check_travels, daemon=True).start()

# ========== ЗАПУСК ==========
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Бот работает!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()
print("✅ Бот запущен!")
print(f"👑 Главный админ ID: 5596589260 (уровень 4)")
print("🏙️ Система городов активна! 4 города ждут путешественников!")
print("👕 Магазин одежды загружен с 16 комплектами!")
print("📌 Админ команды: /adminhelp")
bot.infinity_polling()
