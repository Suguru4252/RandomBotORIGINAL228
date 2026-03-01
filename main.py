import os
import logging
import random
import json
import threading
from typing import Dict, List, Optional
from enum import Enum

# Правильные импорты для python-telegram-bot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# Flask для BotHost (обязательно!)
from flask import Flask

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен из переменных окружения (как требует BotHost)
TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    logger.error("❌ ТОКЕН НЕ НАЙДЕН! Добавьте BOT_TOKEN в переменные окружения BotHost")
    print("❌ ОШИБКА: Токен не найден! Бот не может запуститься.")
    exit(1)

# Типы клеток
class CellType(Enum):
    START = "start"
    PROPERTY = "property"
    CHANCE = "chance"
    COMMUNITY_CHEST = "community_chest"
    TAX = "tax"
    JAIL = "jail"
    GO_TO_JAIL = "go_to_jail"
    FREE_PARKING = "free_parking"
    RAILROAD = "railroad"
    UTILITY = "utility"

# Класс игрока
class Player:
    def __init__(self, user_id: int, username: str):
        self.user_id = user_id
        self.username = username
        self.position = 0
        self.money = 1500
        self.properties = []
        self.in_jail = False
        self.jail_turns = 0
        self.get_out_of_jail_cards = 0
        self.alive = True

# Класс игры
class Game:
    def __init__(self, chat_id: int, creator_id: int):
        self.chat_id = chat_id
        self.creator_id = creator_id
        self.players: Dict[int, Player] = {}
        self.current_turn = 0
        self.started = False
        self.max_players = 4
        self.board = self.create_board()
        self.owned_properties = {}
        self.dice_rolled = False
        
    def create_board(self):
        """Создание игрового поля"""
        return [
            {"name": "Старт", "type": CellType.START, "price": 0},
            {"name": "Улица Победы", "type": CellType.PROPERTY, "price": 60, "rent": [2, 10, 30, 90, 160, 250], "color": "коричневый"},
            {"name": "Казна", "type": CellType.COMMUNITY_CHEST},
            {"name": "Проспект Мира", "type": CellType.PROPERTY, "price": 60, "rent": [4, 20, 60, 180, 320, 450], "color": "коричневый"},
            {"name": "Налог", "type": CellType.TAX, "amount": 200},
            {"name": "Вокзал", "type": CellType.RAILROAD, "price": 200, "rent": [25, 50, 100, 200]},
            {"name": "Невский проспект", "type": CellType.PROPERTY, "price": 100, "rent": [6, 30, 90, 270, 400, 550], "color": "голубой"},
            {"name": "Шанс", "type": CellType.CHANCE},
            {"name": "Улица Горького", "type": CellType.PROPERTY, "price": 100, "rent": [6, 30, 90, 270, 400, 550], "color": "голубой"},
            {"name": "Улица Чехова", "type": CellType.PROPERTY, "price": 120, "rent": [8, 40, 100, 300, 450, 600], "color": "голубой"},
            {"name": "Тюрьма", "type": CellType.JAIL},
            {"name": "Пушкинская улица", "type": CellType.PROPERTY, "price": 140, "rent": [10, 50, 150, 450, 625, 750], "color": "розовый"},
            {"name": "Электростанция", "type": CellType.UTILITY, "price": 150},
            {"name": "Улица Лермонтова", "type": CellType.PROPERTY, "price": 140, "rent": [10, 50, 150, 450, 625, 750], "color": "розовый"},
            {"name": "Улица Толстого", "type": CellType.PROPERTY, "price": 160, "rent": [12, 60, 180, 500, 700, 900], "color": "розовый"},
            {"name": "Вокзал", "type": CellType.RAILROAD, "price": 200, "rent": [25, 50, 100, 200]},
            {"name": "Улица Гагарина", "type": CellType.PROPERTY, "price": 180, "rent": [14, 70, 200, 550, 750, 950], "color": "оранжевый"},
            {"name": "Казна", "type": CellType.COMMUNITY_CHEST},
            {"name": "Улица Королева", "type": CellType.PROPERTY, "price": 180, "rent": [14, 70, 200, 550, 750, 950], "color": "оранжевый"},
            {"name": "Улица Циолковского", "type": CellType.PROPERTY, "price": 200, "rent": [16, 80, 220, 600, 800, 1000], "color": "оранжевый"},
            {"name": "Бесплатная парковка", "type": CellType.FREE_PARKING},
            {"name": "Арбат", "type": CellType.PROPERTY, "price": 220, "rent": [18, 90, 250, 700, 875, 1050], "color": "красный"},
            {"name": "Шанс", "type": CellType.CHANCE},
            {"name": "Тверская улица", "type": CellType.PROPERTY, "price": 220, "rent": [18, 90, 250, 700, 875, 1050], "color": "красный"},
            {"name": "Кузнецкий мост", "type": CellType.PROPERTY, "price": 240, "rent": [20, 100, 300, 750, 925, 1100], "color": "красный"},
            {"name": "Вокзал", "type": CellType.RAILROAD, "price": 200, "rent": [25, 50, 100, 200]},
            {"name": "Проспект Вернадского", "type": CellType.PROPERTY, "price": 260, "rent": [22, 110, 330, 800, 975, 1150], "color": "желтый"},
            {"name": "Проспект Ленина", "type": CellType.PROPERTY, "price": 260, "rent": [22, 110, 330, 800, 975, 1150], "color": "желтый"},
            {"name": "Водопровод", "type": CellType.UTILITY, "price": 150},
            {"name": "Университетская", "type": CellType.PROPERTY, "price": 280, "rent": [24, 120, 360, 850, 1025, 1200], "color": "желтый"},
            {"name": "Отправляйтесь в тюрьму", "type": CellType.GO_TO_JAIL},
            {"name": "Невский проспект", "type": CellType.PROPERTY, "price": 300, "rent": [26, 130, 390, 900, 1100, 1275], "color": "зеленый"},
            {"name": "Улица Рубинштейна", "type": CellType.PROPERTY, "price": 300, "rent": [26, 130, 390, 900, 1100, 1275], "color": "зеленый"},
            {"name": "Казна", "type": CellType.COMMUNITY_CHEST},
            {"name": "Лиговский проспект", "type": CellType.PROPERTY, "price": 320, "rent": [28, 150, 450, 1000, 1200, 1400], "color": "зеленый"},
            {"name": "Вокзал", "type": CellType.RAILROAD, "price": 200, "rent": [25, 50, 100, 200]},
            {"name": "Шанс", "type": CellType.CHANCE},
            {"name": "Красная площадь", "type": CellType.PROPERTY, "price": 350, "rent": [35, 175, 500, 1100, 1300, 1500], "color": "синий"},
            {"name": "Налог", "type": CellType.TAX, "amount": 100},
            {"name": "Кремль", "type": CellType.PROPERTY, "price": 400, "rent": [50, 200, 600, 1400, 1700, 2000], "color": "синий"},
        ]
    
    def add_player(self, user_id: int, username: str) -> bool:
        if len(self.players) >= self.max_players:
            return False
        if user_id not in self.players:
            self.players[user_id] = Player(user_id, username)
            return True
        return False
    
    def start_game(self):
        self.started = True
        self.current_turn = list(self.players.keys())[0]
    
    def next_turn(self):
        players_list = list(self.players.keys())
        current_index = players_list.index(self.current_turn)
        next_index = (current_index + 1) % len(players_list)
        self.current_turn = players_list[next_index]
        self.dice_rolled = False
    
    def roll_dice(self):
        dice1 = random.randint(1, 6)
        dice2 = random.randint(1, 6)
        return dice1, dice2, dice1 + dice2

# Хранилище активных игр
games: Dict[int, Game] = {}

# Flask сервер для BotHost
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Monopoly Bot is running 24/7!"

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    """Запуск Flask сервера в отдельном потоке"""
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎲 Добро пожаловать в Monopoly Bot!\n\n"
        "Команды:\n"
        "/create - Создать новую игру\n"
        "/join [код] - Присоединиться к игре\n"
        "/help - Показать помощь"
    )

# Команда /create
async def create_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or f"Player_{user_id}"
    
    if chat_id in games:
        await update.message.reply_text("❌ В этом чате уже есть активная игра!")
        return
    
    game = Game(chat_id, user_id)
    game.add_player(user_id, username)
    games[chat_id] = game
    
    keyboard = [
        [InlineKeyboardButton("✅ Присоединиться", callback_data=f"join_{chat_id}")],
        [InlineKeyboardButton("▶️ Начать игру", callback_data=f"start_{chat_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎮 Игра создана! Код игры: `{chat_id}`\n"
        f"Игроки: 1/{game.max_players}\n"
        f"Создатель: @{username}\n\n"
        f"Ожидаем игроков...",
        reply_markup=reply_markup
    )

# Команда /join
async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or f"Player_{user_id}"
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /join [код игры]")
        return
    
    try:
        game_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный код игры!")
        return
    
    if game_id not in games:
        await update.message.reply_text("❌ Игра не найдена!")
        return
    
    game = games[game_id]
    
    if game.started:
        await update.message.reply_text("❌ Игра уже началась!")
        return
    
    if game.add_player(user_id, username):
        keyboard = [
            [InlineKeyboardButton("✅ Присоединиться", callback_data=f"join_{game_id}")],
            [InlineKeyboardButton("▶️ Начать игру", callback_data=f"start_{game_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=game_id,
            text=f"✅ @{username} присоединился к игре!\n"
                 f"Игроки: {len(game.players)}/{game.max_players}",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("❌ Не удалось присоединиться к игре!")

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🎲 **Monopoly Bot - Помощь**

**Команды:**
/create - Создать новую игру
/join [код] - Присоединиться к игре
/status - Показать статус текущей игры
/leave - Покинуть игру (до начала)
/help - Показать это сообщение

**Правила:**
• В игре участвуют 2-4 игрока
• Каждый получает 1500 в начале
• Цель - стать последним выжившим игроком
• Проходя Старт, получаете 200
"""
    await update.message.reply_text(help_text)

# Команда /status
async def game_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id not in games:
        await update.message.reply_text("❌ В этом чате нет активной игры!")
        return
    
    game = games[chat_id]
    await show_game_board(chat_id, context)

# Команда /leave
async def leave_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id not in games:
        await update.message.reply_text("❌ В этом чате нет активной игры!")
        return
    
    game = games[chat_id]
    
    if game.started:
        await update.message.reply_text("❌ Нельзя покинуть игру после начала!")
        return
    
    if user_id in game.players:
        del game.players[user_id]
        await update.message.reply_text(f"✅ Вы покинули игру. Осталось игроков: {len(game.players)}")
        
        if len(game.players) == 0:
            del games[chat_id]

# Команда для теста
async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот работает исправно!")

# Обработка нажатий на кнопки
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    action = data[0]
    game_id = int(data[1])
    
    if game_id not in games:
        await query.edit_message_text("❌ Игра больше не существует!")
        return
    
    game = games[game_id]
    user_id = update.effective_user.id
    
    if action == "join":
        if game.started:
            await query.edit_message_text("❌ Игра уже началась!")
            return
        
        username = update.effective_user.username or f"Player_{user_id}"
        if game.add_player(user_id, username):
            keyboard = [
                [InlineKeyboardButton("✅ Присоединиться", callback_data=f"join_{game_id}")],
                [InlineKeyboardButton("▶️ Начать игру", callback_data=f"start_{game_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"✅ @{username} присоединился к игре!\n"
                f"Игроки: {len(game.players)}/{game.max_players}",
                reply_markup=reply_markup
            )
    
    elif action == "start":
        if user_id != game.creator_id:
            await query.edit_message_text("❌ Только создатель игры может начать!")
            return
        
        if len(game.players) < 2:
            await query.edit_message_text("❌ Нужно минимум 2 игрока для начала!")
            return
        
        game.start_game()
        
        board_text = "🏁 ИГРА НАЧАЛАСЬ!\n\n"
        for player in game.players.values():
            board_text += f"👤 @{player.username}: 💰{player.money}\n"
        
        await query.edit_message_text(board_text)
        await show_game_board(game_id, context)
    
    elif action == "roll":
        if user_id != game.current_turn:
            await query.edit_message_text("❌ Сейчас не ваш ход!")
            return
        
        player = game.players[user_id]
        dice1, dice2, total = game.roll_dice()
        
        old_position = player.position
        player.position = (player.position + total) % 40
        
        # Проверка на прохождение старта
        if player.position < old_position:
            player.money += 200
            await context.bot.send_message(
                chat_id=game_id,
                text=f"💰 @{player.username} прошел Старт и получил 200"
            )
        
        result_text = (
            f"🎲 @{player.username} бросил кости:\n"
            f"{dice1} + {dice2} = {total}\n"
            f"Новая позиция: {player.position}"
        )
        
        await context.bot.send_message(chat_id=game_id, text=result_text)
        
        game.next_turn()
        await show_game_board(game_id, context)
    
    elif action == "end":
        if user_id == game.creator_id:
            del games[game_id]
            await query.edit_message_text("🛑 Игра завершена")

async def show_game_board(game_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Показать игровое поле"""
    game = games[game_id]
    
    board_text = "🎮 **ТЕКУЩАЯ ИГРА** 🎮\n\n"
    
    for player in game.players.values():
        turn = "🎯" if player.user_id == game.current_turn else ""
        board_text += f"{turn} @{player.username}: 💰{player.money}\n"
    
    # Кнопки управления
    keyboard = []
    
    if game.started:
        keyboard.append([InlineKeyboardButton("🎲 Бросить кости", callback_data=f"roll_{game_id}")])
    
    keyboard.append([InlineKeyboardButton("🚪 Завершить игру", callback_data=f"end_{game_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=game_id,
        text=board_text,
        reply_markup=reply_markup
    )

# Обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("❌ Произошла внутренняя ошибка. Попробуйте позже.")

def main():
    """Запуск бота"""
    print("🚀 Запуск Monopoly Bot...")
    print(f"✅ Токен загружен: {TOKEN[:10]}...")
    
    # Запускаем Flask в отдельном потоке
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("✅ Веб-сервер Flask запущен на порту 8080")
    
    # Создаем приложение бота
    application = Application.builder().token(TOKEN).build()

    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("create", create_game))
    application.add_handler(CommandHandler("join", join_game))
    application.add_handler(CommandHandler("status", game_status))
    application.add_handler(CommandHandler("leave", leave_game))
    application.add_handler(CommandHandler("test", test))
    
    # Обработчик callback-запросов
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)

    # Запускаем бота
    print("✅ Бот успешно запущен и готов к работе!")
    print("🤖 Ожидание сообщений...")
    application.run_polling()

if __name__ == '__main__':
    main()
