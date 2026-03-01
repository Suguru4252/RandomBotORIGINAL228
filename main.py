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

# Flask для BotHost
from flask import Flask

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен из переменных окружения
TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    logger.error("❌ ТОКЕН НЕ НАЙДЕН! Добавьте BOT_TOKEN в переменные окружения")
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
    def __init__(self, chat_id: int, creator_id: int, creator_name: str):
        self.chat_id = chat_id
        self.creator_id = creator_id
        self.creator_name = creator_name
        self.players: Dict[int, Player] = {}
        self.pending_requests: Dict[int, str] = {}  # user_id: username для запросов на вступление
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

# Функция для создания главного меню
def get_main_menu():
    """Создает инлайн клавиатуру главного меню"""
    keyboard = [
        [InlineKeyboardButton("🎮 Создать игру", callback_data="menu_create")],
        [InlineKeyboardButton("📋 Список игр", callback_data="menu_list")],
        [InlineKeyboardButton("❓ Помощь", callback_data="menu_help")],
        [InlineKeyboardButton("ℹ️ О боте", callback_data="menu_info")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды start с главным меню"""
    welcome_text = (
        "🎲 **Добро пожаловать в Monopoly Bot!**\n\n"
        "Здесь вы можете сыграть в классическую монополию с друзьями.\n\n"
        "**Что умеет бот:**\n"
        "• Создание игровых комнат\n"
        "• До 4 игроков в одной игре\n"
        "• Покупка недвижимости\n"
        "• Случайные события\n"
        "• Полное игровое поле\n\n"
        "Выберите действие в меню ниже:"
    )
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_menu()
    )

# Обработка меню
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки главного меню"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "menu_create":
        # Создание игры
        await create_game_from_menu(update, context)
    
    elif query.data == "menu_list":
        # Показать список активных игр
        await show_games_list(update, context)
    
    elif query.data == "menu_help":
        help_text = (
            "❓ **Помощь по боту**\n\n"
            "**Как играть:**\n"
            "1. Создайте игру или присоединитесь к существующей\n"
            "2. Дождитесь пока наберется минимум 2 игрока\n"
            "3. Создатель игры нажимает 'Начать игру'\n"
            "4. Игроки по очереди бросают кости\n"
            "5. Покупайте собственность и собирайте аренду\n"
            "6. Последний выживший побеждает!\n\n"
            "**Команды:**\n"
            "/start - Главное меню\n"
            "/create - Создать игру\n"
            "/join [код] - Присоединиться по коду\n"
            "/games - Список игр\n"
            "/help - Помощь"
        )
        await query.edit_message_text(help_text, reply_markup=get_main_menu())
    
    elif query.data == "menu_info":
        info_text = (
            "ℹ️ **О боте**\n\n"
            "Версия: 2.0\n"
            "Разработчик: Monopoly Team\n"
            "Особенности:\n"
            "• Полное поле Monopoly\n"
            "• 4 игрока максимум\n"
            "• Система запросов на вступление\n"
            "• Работает 24/7\n\n"
            "Приятной игры! 🎲"
        )
        await query.edit_message_text(info_text, reply_markup=get_main_menu())

# Создание игры через меню
async def create_game_from_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создание игры из меню"""
    query = update.callback_query
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or f"Player_{user_id}"
    
    if chat_id in games:
        await query.edit_message_text(
            "❌ В этом чате уже есть активная игра!\n\n"
            "Используйте /games чтобы посмотреть другие игры.",
            reply_markup=get_main_menu()
        )
        return
    
    game = Game(chat_id, user_id, username)
    game.add_player(user_id, username)
    games[chat_id] = game
    
    success_text = (
        f"✅ **Игра успешно создана!**\n\n"
        f"📋 **Код игры:** `{chat_id}`\n"
        f"👑 **Создатель:** @{username}\n"
        f"👥 **Игроки:** 1/{game.max_players}\n\n"
        f"Теперь другие игроки могут присоединиться:\n"
        f"• Через меню 'Список игр'\n"
        f"• По команде `/join {chat_id}`\n\n"
        f"Ожидаем игроков..."
    )
    
    await query.edit_message_text(
        success_text,
        reply_markup=get_main_menu()
    )

# Показать список активных игр
async def show_games_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список всех активных игр"""
    query = update.callback_query
    
    if not games:
        await query.edit_message_text(
            "📋 **Список активных игр**\n\n"
            "😴 Нет активных игр.\n\n"
            "Создайте свою игру через меню!",
            reply_markup=get_main_menu()
        )
        return
    
    text = "📋 **Доступные игры:**\n\n"
    keyboard = []
    
    for game_id, game in games.items():
        if not game.started and len(game.players) < game.max_players:
            text += f"🎮 **Игра #{game_id}**\n"
            text += f"👑 Создатель: @{game.creator_name}\n"
            text += f"👥 Игроки: {len(game.players)}/{game.max_players}\n"
            text += f"➖➖➖➖➖➖➖➖➖\n"
            
            # Кнопка для присоединения
            keyboard.append([InlineKeyboardButton(
                f"📌 Присоединиться к игре #{game_id}",
                callback_data=f"join_request_{game_id}"
            )])
    
    if not keyboard:
        text += "Нет доступных игр для присоединения.\n"
        text += "Создайте свою игру через меню!"
    
    keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Запрос на присоединение к игре
async def join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик запроса на присоединение к игре"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    game_id = int(data[2])
    
    if game_id not in games:
        await query.edit_message_text(
            "❌ Игра больше не существует!",
            reply_markup=get_main_menu()
        )
        return
    
    game = games[game_id]
    user_id = update.effective_user.id
    username = update.effective_user.username or f"Player_{user_id}"
    
    # Проверки
    if game.started:
        await query.edit_message_text(
            "❌ Игра уже началась!",
            reply_markup=get_main_menu()
        )
        return
    
    if len(game.players) >= game.max_players:
        await query.edit_message_text(
            "❌ В игре уже максимальное количество игроков!",
            reply_markup=get_main_menu()
        )
        return
    
    if user_id in game.players:
        await query.edit_message_text(
            "❌ Вы уже в этой игре!",
            reply_markup=get_main_menu()
        )
        return
    
    # Отправляем запрос создателю
    game.pending_requests[user_id] = username
    
    # Кнопки для создателя
    keyboard = [
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"accept_{game_id}_{user_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{game_id}_{user_id}")
        ]
    ]
    
    try:
        await context.bot.send_message(
            chat_id=game.creator_id,
            text=f"👋 @{username} хочет присоединиться к вашей игре!\n\n"
                 f"Игрок: @{username}\n"
                 f"ID: {user_id}\n\n"
                 f"Принять запрос?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        await query.edit_message_text(
            f"✅ Запрос отправлен создателю игры @{game.creator_name}!\n"
            f"Ожидайте ответа...",
            reply_markup=get_main_menu()
        )
    except:
        await query.edit_message_text(
            "❌ Не удалось отправить запрос создателю игры.",
            reply_markup=get_main_menu()
        )

# Обработка принятия/отклонения запроса
async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик принятия или отклонения запроса на вступление"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    action = data[0]
    game_id = int(data[1])
    requester_id = int(data[2])
    
    if game_id not in games:
        await query.edit_message_text("❌ Игра больше не существует!")
        return
    
    game = games[game_id]
    
    if action == "accept":
        # Принимаем игрока
        username = game.pending_requests.get(requester_id, f"Player_{requester_id}")
        
        if game.add_player(requester_id, username):
            await query.edit_message_text(
                f"✅ Игрок @{username} принят в игру!"
            )
            
            # Уведомляем игрока
            try:
                await context.bot.send_message(
                    chat_id=requester_id,
                    text=f"✅ Ваш запрос на вступление в игру #{game_id} принят!\n"
                         f"Создатель: @{game.creator_name}\n\n"
                         f"Ожидайте начала игры."
                )
            except:
                pass
        else:
            await query.edit_message_text(
                "❌ Не удалось добавить игрока. Возможно, игра уже заполнена."
            )
    
    elif action == "reject":
        # Отклоняем игрока
        username = game.pending_requests.get(requester_id, f"Player_{requester_id}")
        
        await query.edit_message_text(
            f"❌ Запрос от @{username} отклонен."
        )
        
        # Уведомляем игрока
        try:
            await context.bot.send_message(
                chat_id=requester_id,
                text=f"❌ Ваш запрос на вступление в игру #{game_id} был отклонен создателем."
            )
        except:
            pass
    
    # Удаляем из pending
    if requester_id in game.pending_requests:
        del game.pending_requests[requester_id]

# Команда /create
async def create_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or f"Player_{user_id}"
    
    if chat_id in games:
        await update.message.reply_text(
            "❌ В этом чате уже есть активная игра!",
            reply_markup=get_main_menu()
        )
        return
    
    game = Game(chat_id, user_id, username)
    game.add_player(user_id, username)
    games[chat_id] = game
    
    await update.message.reply_text(
        f"✅ **Игра создана!**\n\n"
        f"📋 **Код игры:** `{chat_id}`\n"
        f"👥 **Игроки:** 1/{game.max_players}\n\n"
        f"Другие игроки могут присоединиться:\n"
        f"• По команде `/join {chat_id}`\n"
        f"• Через меню 'Список игр'",
        reply_markup=get_main_menu()
    )

# Команда /join
async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or f"Player_{user_id}"
    
    if not context.args:
        await update.message.reply_text(
            "❌ Использование: /join [код игры]\n"
            "Например: `/join 123456789`",
            reply_markup=get_main_menu()
        )
        return
    
    try:
        game_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный код игры! Код должен быть числом.",
            reply_markup=get_main_menu()
        )
        return
    
    if game_id not in games:
        await update.message.reply_text(
            "❌ Игра с таким кодом не найдена!\n"
            "Проверьте код или посмотрите список доступных игр через меню.",
            reply_markup=get_main_menu()
        )
        return
    
    game = games[game_id]
    
    if game.started:
        await update.message.reply_text(
            "❌ Игра уже началась!",
            reply_markup=get_main_menu()
        )
        return
    
    if len(game.players) >= game.max_players:
        await update.message.reply_text(
            "❌ В игре уже максимальное количество игроков!",
            reply_markup=get_main_menu()
        )
        return
    
    if user_id in game.players:
        await update.message.reply_text(
            "❌ Вы уже в этой игре!",
            reply_markup=get_main_menu()
        )
        return
    
    # Отправляем запрос создателю
    game.pending_requests[user_id] = username
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"accept_{game_id}_{user_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{game_id}_{user_id}")
        ]
    ]
    
    try:
        await context.bot.send_message(
            chat_id=game.creator_id,
            text=f"👋 @{username} хочет присоединиться к вашей игре!\n\n"
                 f"Игрок: @{username}\n"
                 f"ID: {user_id}\n\n"
                 f"Принять запрос?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        await update.message.reply_text(
            f"✅ Запрос отправлен создателю игры @{game.creator_name}!\n"
            f"Ожидайте ответа...",
            reply_markup=get_main_menu()
        )
    except:
        await update.message.reply_text(
            "❌ Не удалось отправить запрос создателю игры.",
            reply_markup=get_main_menu()
        )

# Команда /games
async def list_games_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для показа списка игр"""
    if not games:
        await update.message.reply_text(
            "📋 **Список активных игр**\n\n"
            "😴 Нет активных игр.\n\n"
            "Создайте свою игру через /create или меню!",
            reply_markup=get_main_menu()
        )
        return
    
    text = "📋 **Доступные игры:**\n\n"
    
    for game_id, game in games.items():
        if not game.started and len(game.players) < game.max_players:
            text += f"🎮 **Игра #{game_id}**\n"
            text += f"👑 Создатель: @{game.creator_name}\n"
            text += f"👥 Игроки: {len(game.players)}/{game.max_players}\n"
            text += f"➖➖➖➖➖➖➖➖➖\n"
    
    text += "\nЧтобы присоединиться, используйте:\n"
    text += "`/join [код игры]`"
    
    await update.message.reply_text(text, reply_markup=get_main_menu())

# Обработка нажатий на кнопки игры
async def game_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик игровых кнопок"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    action = data[0]
    
    if action == "back":
        await query.edit_message_text(
            "🎲 **Главное меню**\n\nВыберите действие:",
            reply_markup=get_main_menu()
        )
        return
    
    if action in ["accept", "reject"]:
        await handle_join_request(update, context)
        return
    
    if action in ["join", "request"]:
        if action == "join_request":
            await join_request(update, context)
        return
    
    if action == "menu":
        await menu_callback(update, context)
        return
    
    # Игровые действия (start, roll, end и т.д.)
    game_id = int(data[1])
    
    if game_id not in games:
        await query.edit_message_text(
            "❌ Игра больше не существует!",
            reply_markup=get_main_menu()
        )
        return
    
    game = games[game_id]
    user_id = update.effective_user.id
    
    if action == "start":
        if user_id != game.creator_id:
            await query.edit_message_text("❌ Только создатель игры может начать!")
            return
        
        if len(game.players) < 2:
            await query.edit_message_text("❌ Нужно минимум 2 игрока для начала!")
            return
        
        game.start_game()
        
        # Уведомляем всех игроков о начале
        for player_id in game.players.keys():
            try:
                await context.bot.send_message(
                    chat_id=player_id,
                    text=f"🎮 **Игра #{game_id} началась!**\n\n"
                         f"Первый ход: @{game.players[game.current_turn].username}"
                )
            except:
                pass
        
        await show_game_board(game_id, context, query.message.chat_id)
    
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
        
        # Уведомляем всех о результате хода
        for player_id in game.players.keys():
            try:
                await context.bot.send_message(
                    chat_id=player_id,
                    text=f"🎲 @{player.username} бросил кости:\n"
                         f"{dice1} + {dice2} = {total}\n"
                         f"Новая позиция: {player.position}"
                )
            except:
                pass
        
        game.next_turn()
        
        # Уведомляем следующего игрока о его ходе
        next_player = game.players[game.current_turn]
        await context.bot.send_message(
            chat_id=next_player.user_id,
            text=f"🎯 **Ваш ход!**\n\n"
                 f"Игра #{game_id}\n"
                 f"Баланс: {next_player.money}\n\n"
                 f"Нажмите кнопку 'Бросить кости' в игре!"
        )
        
        await show_game_board(game_id, context, query.message.chat_id)
    
    elif action == "end":
        if user_id == game.creator_id:
            # Уведомляем всех о завершении
            for player_id in game.players.keys():
                try:
                    await context.bot.send_message(
                        chat_id=player_id,
                        text=f"🛑 Игра #{game_id} завершена создателем."
                    )
                except:
                    pass
            
            del games[game_id]
            await query.edit_message_text(
                "🛑 Игра завершена",
                reply_markup=get_main_menu()
            )

async def show_game_board(game_id: int, context: ContextTypes.DEFAULT_TYPE, chat_id: int = None):
    """Показать игровое поле"""
    game = games[game_id]
    
    board_text = "🎮 **ТЕКУЩАЯ ИГРА** 🎮\n\n"
    
    for player in game.players.values():
        turn = "🎯" if player.user_id == game.current_turn else "⏳"
        board_text += f"{turn} @{player.username}: 💰{player.money}\n"
    
    # Кнопки управления
    keyboard = []
    
    if game.started:
        keyboard.append([InlineKeyboardButton("🎲 Бросить кости", callback_data=f"roll_{game_id}")])
    
    keyboard.append([InlineKeyboardButton("🚪 Завершить игру", callback_data=f"end_{game_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем всем игрокам
    for player_id in game.players.keys():
        try:
            await context.bot.send_message(
                chat_id=player_id,
                text=board_text,
                reply_markup=reply_markup
            )
        except:
            pass

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ **Помощь по боту**\n\n"
        "**Основные команды:**\n"
        "/start - Главное меню\n"
        "/create - Создать новую игру\n"
        "/join [код] - Присоединиться к игре\n"
        "/games - Список активных игр\n"
        "/help - Показать помощь\n\n"
        "**Как играть:**\n"
        "1. Создайте игру или присоединитесь к существующей\n"
        "2. Дождитесь пока создатель начнет игру\n"
        "3. Когда ваш ход - нажимайте 'Бросить кости'\n"
        "4. Покупайте собственность и богатейте!\n\n"
        "Приятной игры! 🎲",
        reply_markup=get_main_menu()
    )

# Команда для теста
async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Бот работает исправно!",
        reply_markup=get_main_menu()
    )

# Обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла внутренняя ошибка. Попробуйте позже.",
            reply_markup=get_main_menu()
        )

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
    application.add_handler(CommandHandler("games", list_games_command))
    application.add_handler(CommandHandler("test", test))
    
    # Обработчики callback-запросов
    application.add_handler(CallbackQueryHandler(game_button_callback, pattern="^(start|roll|end|accept|reject|join_request|back|menu)_"))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_"))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)

    # Запускаем бота
    print("✅ Бот успешно запущен и готов к работе!")
    print("🤖 Ожидание сообщений...")
    application.run_polling()

if __name__ == '__main__':
    main()
