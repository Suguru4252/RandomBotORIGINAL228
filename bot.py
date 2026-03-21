import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import db
from utils import get_pet_emoji, get_stage_name, should_evolve, get_hunger_decline

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Клавиатуры
def get_main_keyboard(user_data):
    """Главная клавиатура с кнопками действий"""
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
    """Клавиатура выбора питомца при старте"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🦊 Лисёнок", callback_data="pet_fox")],
        [InlineKeyboardButton(text="🐱 Котёнок", callback_data="pet_cat")],
        [InlineKeyboardButton(text="🐉 Дракончик", callback_data="pet_dragon")],
        [InlineKeyboardButton(text="🦉 Совёнок", callback_data="pet_owl")]
    ])

# Команды
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if user:
        # У пользователя уже есть питомец
        pet_emoji = get_pet_emoji(user['pet_type'], user['pet_stage'])
        await message.answer(
            f"🐾 С возвращением, {message.from_user.first_name}!\n\n"
            f"Твой питомец {pet_emoji} {get_stage_name(user['pet_stage'])} ждёт тебя!",
            reply_markup=get_main_keyboard(user)
        )
    else:
        # Новый пользователь — выбирает питомца
        await message.answer(
            "🌟 **Добро пожаловать в ZveroBot!** 🌟\n\n"
            "Выбери себе питомца, который будет жить в твоём Telegram:\n\n"
            "* Лисёнок — хитрый и умный\n"
            "* Котёнок — нежный и ласковый\n"
            "* Дракончик — магический и сильный\n"
            "* Совёнок — мудрый и спокойный",
            parse_mode="Markdown",
            reply_markup=get_choice_keyboard()
        )

# Обработка выбора питомца
@dp.callback_query(F.data.startswith("pet_"))
async def choose_pet(callback: types.CallbackQuery):
    pet_type = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    await db.create_user(user_id, callback.from_user.username, pet_type)
    user = await db.get_user(user_id)
    
    pet_emoji = get_pet_emoji(pet_type, 0)
    
    await callback.message.edit_text(
        f"🎉 Поздравляю! Твой питомец {pet_emoji} {get_stage_name(0)} вылупился!\n\n"
        f"Не забывай кормить и гладить его каждый день, и он будет расти! 🐾",
        reply_markup=get_main_keyboard(user)
    )
    await callback.answer()

# Кормление
@dp.callback_query(F.data == "feed")
async def feed_pet(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Сначала создай питомца командой /start")
        return
    
    # Проверяем, сколько прошло времени с последнего кормления
    last_feed = user['last_feed']
    hours_since = (datetime.now() - last_feed).total_seconds() / 3600
    
    if hours_since < 6:
        await callback.answer(f"Питомец сыт! Подожди {int(6 - hours_since)} часа(ов)", show_alert=True)
        return
    
    # Увеличиваем сытость
    new_hunger = min(100, user['hunger'] + 15)
    await db.update_hunger(user_id, new_hunger)
    await db.add_coins(user_id, 5)
    
    pet_emoji = get_pet_emoji(user['pet_type'], user['pet_stage'])
    await callback.answer(f"🍖 Ты покормил {pet_emoji}! +5 монет")
    
    # Обновляем сообщение
    updated_user = await db.get_user(user_id)
    await callback.message.edit_reply_markup(reply_markup=get_main_keyboard(updated_user))

# Погладить
@dp.callback_query(F.data == "pet")
async def pet_pet(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Сначала создай питомца командой /start")
        return
    
    # Проверяем, сколько прошло времени с последнего поглаживания
    last_pet = user['last_pet']
    hours_since = (datetime.now() - last_pet).total_seconds() / 3600
    
    if hours_since < 3:
        await callback.answer(f"Питомец счастлив! Подожди {int(3 - hours_since)} часа(ов)", show_alert=True)
        return
    
    # Увеличиваем настроение
    new_mood = min(100, user['mood'] + 10)
    await db.update_mood(user_id, new_mood)
    await db.add_coins(user_id, 3)
    
    pet_emoji = get_pet_emoji(user['pet_type'], user['pet_stage'])
    await callback.answer(f"😊 Ты погладил {pet_emoji}! +3 монеты")
    
    # Обновляем сообщение
    updated_user = await db.get_user(user_id)
    await callback.message.edit_reply_markup(reply_markup=get_main_keyboard(updated_user))

# Статистика
@dp.callback_query(F.data == "stats")
async def show_stats(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("Сначала создай питомца командой /start")
        return
    
    pet_emoji = get_pet_emoji(user['pet_type'], user['pet_stage'])
    
    # Проверяем эволюцию
    if should_evolve(user):
        new_stage = user['pet_stage'] + 1
        await db.update_stage(user['user_id'], new_stage)
        user = await db.get_user(user['user_id'])  # обновляем данные
        
        await callback.answer(f"🎉 УРА! Твой питомец эволюционировал! 🎉", show_alert=True)
    
    stats_text = (
        f"📊 **Статистика питомца**\n\n"
        f"{pet_emoji} **Вид:** {user['pet_type'].capitalize()}\n"
        f"📈 **Стадия:** {get_stage_name(user['pet_stage'])}\n"
        f"🍖 **Сытость:** {user['hunger']}%\n"
        f"😊 **Настроение:** {user['mood']}%\n"
        f"💰 **Монеты:** {user['coins']}\n\n"
        f"⭐ Поднимай уровень, кормя и гладя питомца каждый день!"
    )
    
    await callback.message.answer(stats_text, parse_mode="Markdown")
    await callback.answer()

# Пригласить друга
@dp.callback_query(F.data == "invite")
async def invite_friend(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Сначала создай питомца командой /start")
        return
    
    # Создаём реферальную ссылку
    bot_info = await bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    
    await callback.message.answer(
        f"👥 **Пригласи друга!**\n\n"
        f"Отправь другу эту ссылку:\n`{invite_link}`\n\n"
        f"✨ Когда друг создаст питомца, вы оба получите **+50 монет**!",
        parse_mode="Markdown"
    )
    await callback.answer()

# Фоновая задача: автоматическое уменьшение сытости и настроения
async def daily_decline():
    """Каждый час уменьшает сытость и настроение"""
    while True:
        await asyncio.sleep(3600)  # раз в час
        
        # Получаем всех пользователей
        async with db.pool.acquire() as conn:
            users = await conn.fetch("SELECT user_id, hunger, mood, last_feed FROM users")
            
            for user in users:
                # Рассчитываем снижение голода
                decline = get_hunger_decline(user['last_feed'])
                if decline > 0:
                    new_hunger = max(0, user['hunger'] - decline)
                    await db.update_hunger(user['user_id'], new_hunger)
                
                # Настроение падает медленнее
                new_mood = max(0, user['mood'] - 2)
                await db.update_mood(user['user_id'], new_mood)

# Запуск бота
async def main():
    await db.connect()
    
    # Запускаем фоновую задачу
    asyncio.create_task(daily_decline())
    
    await dp.start_polling(bot)
    logging.info("Бот запущен!")

if __name__ == "__main__":
    asyncio.run(main())