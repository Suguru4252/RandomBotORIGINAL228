#!/usr/bin/env python3
"""
ZveroBot — виртуальный питомец в Telegram
С поддержкой прокси для обхода блокировок
"""

import asyncio
import logging
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = "8323291713:AAFzA2TccSzbRCYvzxxtaFjpIVNlfuskQgI"

# ПРОКСИ - ВЫБЕРИ ОДИН ИЗ НИХ (раскомментируй нужный)
# HTTP прокси:
PROXY_URL = "http://45.137.116.170:3128"  # Тестовый
# PROXY_URL = "http://188.166.3.244:80"
# PROXY_URL = "http://45.77.174.217:3128"

# SOCKS5 прокси (нужна библиотека aiohttp-socks):
# PROXY_URL = "socks5://45.86.93.145:1080"

# Если прокси не нужен - закомментируй PROXY_URL и раскомментируй строку ниже
# PROXY_URL = None

# ==================== СОЗДАНИЕ БОТА С ПРОКСИ ====================
if PROXY_URL:
    try:
        session = AiohttpSession(proxy=PROXY_URL)
        bot = Bot(token=BOT_TOKEN, session=session)
        print(f"✅ Бот запущен с прокси: {PROXY_URL}")
    except Exception as e:
        print(f"❌ Ошибка прокси: {e}")
        print("⚠️ Запускаю без прокси...")
        bot = Bot(token=BOT_TOKEN)
else:
    bot = Bot(token=BOT_TOKEN)
    print("✅ Бот запущен без прокси")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

dp = Dispatcher(storage=MemoryStorage())

# ==================== БАЗА ДАННЫХ (SQLite) ====================
class Database:
    def __init__(self):
        self.conn = None
        
    async def connect(self):
        self.conn = sqlite3.connect('zverobot.db')
        self.conn.row_factory = sqlite3.Row
        await self._create_tables()
        logger.info("База данных подключена")
    
    async def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                pet_type TEXT DEFAULT 'fox',
                pet_stage INTEGER DEFAULT 0,
                hunger INTEGER DEFAULT 100,
                mood INTEGER DEFAULT 100,
                last_feed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_pet TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                coins INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
    
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    async def create_user(self, user_id: int, username: str, pet_type: str):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, username, pet_type)
            VALUES (?, ?, ?)
        """, (user_id, username, pet_type))
        self.conn.commit()
    
    async def update_hunger(self, user_id: int, hunger: int):
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE users SET hunger = ?, last_feed = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (min(100, hunger), user_id))
        self.conn.commit()
    
    async def update_mood(self, user_id: int, mood: int):
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE users SET mood = ?, last_pet = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (min(100, mood), user_id))
        self.conn.commit()
    
    async def add_coins(self, user_id: int, amount: int):
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE users SET coins = coins + ? WHERE user_id = ?
        """, (amount, user_id))
        self.conn.commit()
    
    async def update_stage(self, user_id: int, stage: int):
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE users SET pet_stage = ? WHERE user_id = ?
        """, (stage, user_id))
        self.conn.commit()
    
    async def get_all_users(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, hunger, mood, last_feed FROM users")
        return cursor.fetchall()

db = Database()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def get_pet_emoji(pet_type: str, stage: int) -> str:
    emojis = {
        'fox': ['🥚', '🦊', '🦊✨', '🦊👑'],
        'cat': ['🥚', '🐱', '🐱🌟', '🐱💎'],
        'dragon': ['🥚', '🐉', '🐉🔥', '🐉👑'],
        'owl': ['🥚', '🦉', '🦉✨', '🦉📚']
    }
    return emojis.get(pet_type, ['🐾'])[min(stage, 3)]

def get_stage_name(stage: int) -> str:
    stages = ['🥚 Яйцо', '🐣 Детёныш', '🌟 Юный', '👑 Взрослый']
    return stages[min(stage, 3)]

def should_evolve(user_data) -> bool:
    if user_data['pet_stage'] >= 3:
        return False
    created_at = datetime.strptime(user_data['created_at'], '%Y-%m-%d %H:%M:%S')
    days_old = (datetime.now() - created_at).days
    required_days = (user_data['pet_stage'] + 1) * 5
    return days_old >= required_days

def get_hunger_decline(last_feed_str) -> int:
    last_feed = datetime.strptime(last_feed_str, '%Y-%m-%d %H:%M:%S')
    hours_since = (datetime.now() - last_feed).total_seconds() / 3600
    decline = int(hours_since / 24 * 20)
    return min(100, decline)

# ==================== КЛАВИАТУРЫ ====================
def get_main_keyboard(user_data):
    pet_emoji = get_pet_emoji(user_data['pet_type'], user_data['pet_stage'])
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"🍖 Покормить ({user_data['hunger']}%)", callback_data="feed"),
            InlineKeyboardButton(text=f"😊 Погладить ({user_data['mood']}%)", callback_data="pet")
        ],
        [
            InlineKeyboardButton(text="📊 Мой питомец", callback_data="stats"),
            InlineKeyboardButton(text="👥 Пригласить друга", callback_data="invite")
        ]
    ])

def get_choice_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🦊 Лисёнок", callback_data="pet_fox")],
        [InlineKeyboardButton(text="🐱 Котёнок", callback_data="pet_cat")],
        [InlineKeyboardButton(text="🐉 Дракончик", callback_data="pet_dragon")],
        [InlineKeyboardButton(text="🦉 Совёнок", callback_data="pet_owl")]
    ])

# ==================== КОМАНДЫ ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if user:
        pet_emoji = get_pet_emoji(user['pet_type'], user['pet_stage'])
        await message.answer(
            f"🐾 С возвращением, {message.from_user.first_name}!\n\n"
            f"Твой питомец {pet_emoji} {get_stage_name(user['pet_stage'])} ждёт тебя!",
            reply_markup=get_main_keyboard(user)
        )
    else:
        await message.answer(
            "🌟 **Добро пожаловать в ZveroBot!** 🌟\n\n"
            "Выбери себе питомца:\n\n"
            "🦊 Лисёнок — хитрый и умный\n"
            "🐱 Котёнок — нежный и ласковый\n"
            "🐉 Дракончик — магический и сильный\n"
            "🦉 Совёнок — мудрый и спокойный",
            parse_mode="Markdown",
            reply_markup=get_choice_keyboard()
        )

@dp.callback_query(F.data.startswith("pet_"))
async def choose_pet(callback: types.CallbackQuery):
    pet_type = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    await db.create_user(user_id, callback.from_user.username, pet_type)
    user = await db.get_user(user_id)
    
    pet_emoji = get_pet_emoji(pet_type, 0)
    
    await callback.message.edit_text(
        f"🎉 Поздравляю! Твой питомец {pet_emoji} {get_stage_name(0)} вылупился!\n\n"
        f"Не забывай кормить и гладить его каждый день! 🐾",
        reply_markup=get_main_keyboard(user)
    )
    await callback.answer()

@dp.callback_query(F.data == "feed")
async def feed_pet(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Сначала создай питомца командой /start")
        return
    
    last_feed = datetime.strptime(user['last_feed'], '%Y-%m-%d %H:%M:%S')
    hours_since = (datetime.now() - last_feed).total_seconds() / 3600
    
    if hours_since < 6:
        await callback.answer(f"Питомец сыт! Подожди {int(6 - hours_since)} часа(ов)", show_alert=True)
        return
    
    new_hunger = min(100, user['hunger'] + 15)
    await db.update_hunger(user_id, new_hunger)
    await db.add_coins(user_id, 5)
    
    pet_emoji = get_pet_emoji(user['pet_type'], user['pet_stage'])
    await callback.answer(f"🍖 Ты покормил {pet_emoji}! +5 монет")
    
    updated_user = await db.get_user(user_id)
    await callback.message.edit_reply_markup(reply_markup=get_main_keyboard(updated_user))

@dp.callback_query(F.data == "pet")
async def pet_pet(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Сначала создай питомца командой /start")
        return
    
    last_pet = datetime.strptime(user['last_pet'], '%Y-%m-%d %H:%M:%S')
    hours_since = (datetime.now() - last_pet).total_seconds() / 3600
    
    if hours_since < 3:
        await callback.answer(f"Питомец счастлив! Подожди {int(3 - hours_since)} часа(ов)", show_alert=True)
        return
    
    new_mood = min(100, user['mood'] + 10)
    await db.update_mood(user_id, new_mood)
    await db.add_coins(user_id, 3)
    
    pet_emoji = get_pet_emoji(user['pet_type'], user['pet_stage'])
    await callback.answer(f"😊 Ты погладил {pet_emoji}! +3 монеты")
    
    updated_user = await db.get_user(user_id)
    await callback.message.edit_reply_markup(reply_markup=get_main_keyboard(updated_user))

@dp.callback_query(F.data == "stats")
async def show_stats(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("Сначала создай питомца командой /start")
        return
    
    pet_emoji = get_pet_emoji(user['pet_type'], user['pet_stage'])
    
    if should_evolve(user):
        new_stage = user['pet_stage'] + 1
        await db.update_stage(user['user_id'], new_stage)
        user = await db.get_user(user['user_id'])
        await callback.answer(f"🎉 УРА! Твой питомец эволюционировал! 🎉", show_alert=True)
    
    stats_text = (
        f"📊 **Статистика питомца**\n\n"
        f"{pet_emoji} **Вид:** {user['pet_type'].capitalize()}\n"
        f"📈 **Стадия:** {get_stage_name(user['pet_stage'])}\n"
        f"🍖 **Сытость:** {user['hunger']}%\n"
        f"😊 **Настроение:** {user['mood']}%\n"
        f"💰 **Монеты:** {user['coins']}\n\n"
        f"⭐ Корми и гладь питомца каждый день!"
    )
    
    await callback.message.answer(stats_text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "invite")
async def invite_friend(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("Сначала создай питомца командой /start")
        return
    
    bot_info = await bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start=ref_{callback.from_user.id}"
    
    await callback.message.answer(
        f"👥 **Пригласи друга!**\n\n"
        f"Отправь ссылку другу:\n`{invite_link}`\n\n"
        f"✨ Когда друг создаст питомца, вы оба получите **+50 монет**!",
        parse_mode="Markdown"
    )
    await callback.answer()

# ==================== ФОНОВАЯ ЗАДАЧА ====================
async def daily_decline():
    while True:
        await asyncio.sleep(3600)
        
        try:
            users = await db.get_all_users()
            for user in users:
                decline = get_hunger_decline(user['last_feed'])
                if decline > 0:
                    new_hunger = max(0, user['hunger'] - decline)
                    await db.update_hunger(user['user_id'], new_hunger)
                
                new_mood = max(0, user['mood'] - 2)
                await db.update_mood(user['user_id'], new_mood)
        except Exception as e:
            logger.error(f"Ошибка в фоновой задаче: {e}")

# ==================== ЗАПУСК ====================
async def main():
    await db.connect()
    asyncio.create_task(daily_decline())
    await dp.start_polling(bot)
    logger.info("Бот ZveroBot запущен!")

if __name__ == "__main__":
    asyncio.run(main())
