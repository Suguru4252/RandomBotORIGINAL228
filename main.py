import os
import logging
import random
import json
import threading
import asyncio
from typing import Dict, List, Optional
from enum import Enum

# Правильные импорты для python-telegram-bot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
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

# Класс аукциона
class Auction:
    def __init__(self, property_name: str, property_price: int, game_id: int, position: int):
        self.property_name = property_name
        self.property_price = property_price
        self.game_id = game_id
        self.position = position
        self.current_bid = property_price // 2  # Стартовая цена - половина
        self.current_bidder = None
        self.bidders: Dict[int, str] = {}
        self.active = True
        self.countdown = None  # Сначала None - отсчет не идет
        self.countdown_active = False  # Флаг, что отсчет запущен
        self.task = None
        self.message_id = None
        self.has_bids = False  # Были ли ставки

# Класс карты (собственности)
class Property:
    def __init__(self, name: str, price: int, color: str, rent: list):
        self.name = name
        self.price = price
        self.color = color
        self.rent = rent
        self.owner = None
        self.houses = 0
        self.hotel = False
        self.mortgaged = False

# Класс игрока
class Player:
    def __init__(self, user_id: int, username: str):
        self.user_id = user_id
        self.username = username
        self.position = 0
        self.money = 1500
        self.properties: List[Property] = []
        self.in_jail = False
        self.jail_turns = 0
        self.get_out_of_jail_cards = 0
        self.alive = True
        self.in_game = False
        self.double_count = 0

    def buy_property(self, property: Property) -> bool:
        if self.money >= property.price:
            self.money -= property.price
            self.properties.append(property)
            property.owner = self
            return True
        return False

    def pay_rent(self, amount: int, owner) -> bool:
        if self.money >= amount:
            self.money -= amount
            owner.money += amount
            return True
        else:
            self.alive = False
            for prop in self.properties:
                prop.owner = owner
                owner.properties.append(prop)
            self.properties = []
            return False

# Класс игры
class Game:
    def __init__(self, chat_id: int, creator_id: int, creator_name: str):
        self.chat_id = chat_id
        self.creator_id = creator_id
        self.creator_name = creator_name
        self.players: Dict[int, Player] = {}
        self.pending_requests: Dict[int, str] = {}
        self.current_turn = 0
        self.started = False
        self.max_players = 6
        self.properties = self.create_properties()
        self.owned_properties = {}
        self.dice_rolled = False
        self.message_id = None
        self.jackpot = 0
        self.auction: Optional[Auction] = None
        self.chat_messages = []  # История чата
        self.is_public_chat = False  # Флаг для публичного чата

    def create_properties(self):
        """Создание всей собственности на поле"""
        return [
            Property("Старт", 0, "special", [0]),
            Property("Улица Победы", 60, "коричневый", [2, 10, 30, 90, 160, 250]),
            Property("Казна", 0, "special", [0]),
            Property("Проспект Мира", 60, "коричневый", [4, 20, 60, 180, 320, 450]),
            Property("Налог", 200, "tax", [200]),
            Property("Вокзал", 200, "railroad", [25, 50, 100, 200]),
            Property("Невский проспект", 100, "голубой", [6, 30, 90, 270, 400, 550]),
            Property("Шанс", 0, "chance", [0]),
            Property("Улица Горького", 100, "голубой", [6, 30, 90, 270, 400, 550]),
            Property("Улица Чехова", 120, "голубой", [8, 40, 100, 300, 450, 600]),
            Property("Тюрьма", 0, "jail", [0]),
            Property("Пушкинская улица", 140, "розовый", [10, 50, 150, 450, 625, 750]),
            Property("Электростанция", 150, "utility", [0]),
            Property("Улица Лермонтова", 140, "розовый", [10, 50, 150, 450, 625, 750]),
            Property("Улица Толстого", 160, "розовый", [12, 60, 180, 500, 700, 900]),
            Property("Вокзал", 200, "railroad", [25, 50, 100, 200]),
            Property("Улица Гагарина", 180, "оранжевый", [14, 70, 200, 550, 750, 950]),
            Property("Казна", 0, "special", [0]),
            Property("Улица Королева", 180, "оранжевый", [14, 70, 200, 550, 750, 950]),
            Property("Улица Циолковского", 200, "оранжевый", [16, 80, 220, 600, 800, 1000]),
            Property("Бесплатная парковка", 0, "special", [0]),
            Property("Арбат", 220, "красный", [18, 90, 250, 700, 875, 1050]),
            Property("Шанс", 0, "chance", [0]),
            Property("Тверская улица", 220, "красный", [18, 90, 250, 700, 875, 1050]),
            Property("Кузнецкий мост", 240, "красный", [20, 100, 300, 750, 925, 1100]),
            Property("Вокзал", 200, "railroad", [25, 50, 100, 200]),
            Property("Проспект Вернадского", 260, "желтый", [22, 110, 330, 800, 975, 1150]),
            Property("Проспект Ленина", 260, "желтый", [22, 110, 330, 800, 975, 1150]),
            Property("Водопровод", 150, "utility", [0]),
            Property("Университетская", 280, "желтый", [24, 120, 360, 850, 1025, 1200]),
            Property("Отправляйтесь в тюрьму", 0, "jail", [0]),
            Property("Невский проспект", 300, "зеленый", [26, 130, 390, 900, 1100, 1275]),
            Property("Улица Рубинштейна", 300, "зеленый", [26, 130, 390, 900, 1100, 1275]),
            Property("Казна", 0, "special", [0]),
            Property("Лиговский проспект", 320, "зеленый", [28, 150, 450, 1000, 1200, 1400]),
            Property("Вокзал", 200, "railroad", [25, 50, 100, 200]),
            Property("Шанс", 0, "chance", [0]),
            Property("Красная площадь", 350, "синий", [35, 175, 500, 1100, 1300, 1500]),
            Property("Налог", 100, "tax", [100]),
            Property("Кремль", 400, "синий", [50, 200, 600, 1400, 1700, 2000]),
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
        for player in self.players.values():
            player.in_game = True

    def next_turn(self):
        alive_players = [p for p in self.players.values() if p.alive]
        if len(alive_players) == 1:
            return alive_players[0]

        players_list = [pid for pid, p in self.players.items() if p.alive]
        current_index = players_list.index(self.current_turn)
        next_index = (current_index + 1) % len(players_list)
        self.current_turn = players_list[next_index]
        self.dice_rolled = False

        current_player = self.players[self.current_turn]
        if current_player.in_jail:
            current_player.jail_turns += 1
            if current_player.jail_turns >= 3:
                current_player.in_jail = False
                current_player.jail_turns = 0
                return f"🚓 *@{current_player.username}* вышел из тюрьмы!"
        return None

    def roll_dice(self):
        dice1 = random.randint(1, 6)
        dice2 = random.randint(1, 6)
        return dice1, dice2, dice1 + dice2, dice1 == dice2

    def get_property_at(self, position: int) -> Property:
        return self.properties[position]

    def add_chat_message(self, user_id: int, username: str, message: str):
        """Добавить сообщение в чат игры"""
        self.chat_messages.append({
            'user_id': user_id,
            'username': username,
            'message': message,
            'time': len(self.chat_messages)
        })
        # Храним только последние 50 сообщений
        if len(self.chat_messages) > 50:
            self.chat_messages = self.chat_messages[-50:]

    def get_chat_history(self, count: int = 10) -> str:
        """Получить историю чата"""
        if not self.chat_messages:
            return "*Чат игры:*\nПока нет сообщений"

        recent = self.chat_messages[-count:]
        result = "*Чат игры:*\n"
        for msg in recent:
            result += f"*@{msg['username']}:* {msg['message']}\n"
        return result

    def handle_landing(self, player: Player, position: int) -> dict:
        """Обработка попадания на клетку"""
        prop = self.properties[position]
        result = {
            "text": f"*{prop.name}*\n",
            "action": None,
            "data": None
        }

        # Старт
        if position == 0:
            result["text"] += "🌟 Стартовая позиция"

        # Налог
        elif prop.name == "Налог":
            amount = 200 if position == 4 else 100
            if player.money >= amount:
                player.money -= amount
                self.jackpot += amount
                result["text"] += f"💰 Вы заплатили налог *{amount}*💰"
            else:
                player.alive = False
                result["text"] += f"💔 У вас недостаточно денег для уплаты налога!"

        # Тюрьма (посещение)
        elif position == 10:
            result["text"] += "🚓 Вы посетили тюрьму (просто отдых)"

        # Отправляйтесь в тюрьму
        elif position == 30:
            player.in_jail = True
            player.position = 10
            result["text"] += "🚓 Вы отправились в тюрьму на 3 хода!"

        # Бесплатная парковка
        elif position == 20:
            if self.jackpot > 0:
                player.money += self.jackpot
                result["text"] += f"💰 Вы получили джекпот: *{self.jackpot}*💰"
                self.jackpot = 0
            else:
                result["text"] += "🅿️ Бесплатная парковка"

        # Шанс
        elif prop.name == "Шанс":
            chance = self.get_chance_card()
            result["text"] += f"🎲 *Шанс:* {chance['text']}"
            if chance["money"] != 0:
                player.money += chance["money"]
                if chance["money"] > 0:
                    result["text"] += f" (+{chance['money']}💰)"
                else:
                    result["text"] += f" ({chance['money']}💰)"
            if chance["position"] is not None:
                player.position = chance["position"]
                result["text"] += f" Перемещение на клетку *{chance['position']}*"

        # Казна
        elif prop.name == "Казна":
            chest = self.get_community_chest()
            result["text"] += f"📦 *Казна:* {chest['text']}"
            if chest["money"] != 0:
                player.money += chest["money"]
                if chest["money"] > 0:
                    result["text"] += f" (+{chest['money']}💰)"
                else:
                    result["text"] += f" ({chest['money']}💰)"
            if chest["position"] is not None:
                player.position = chest["position"]
                result["text"] += f" Перемещение на клетку *{chest['position']}*"

        # Собственность
        elif prop.price > 0 and prop.name not in ["Налог", "Вокзал", "Электростанция", "Водопровод"]:
            if prop.owner is None:
                result["action"] = "buy"
                result["data"] = position
                result["text"] += f"🏠 *Свободная собственность*\n"
                result["text"] += f"💰 Цена: *{prop.price}*\n"
                result["text"] += f"🏷️ Цвет: *{prop.color}*\n"
                result["text"] += f"💵 Аренда: *{prop.rent[0]}*"
            elif prop.owner.user_id != player.user_id:
                rent = prop.rent[0] * (prop.houses * 2 if prop.houses > 0 else 1)
                if prop.name in ["Вокзал", "Электростанция", "Водопровод"]:
                    owner_railroads = len([p for p in prop.owner.properties if p.name == "Вокзал"])
                    if prop.name == "Вокзал":
                        rent = [25, 50, 100, 200][owner_railroads - 1]
                    else:
                        dice1, dice2, total, _ = self.roll_dice()
                        rent = total * 4 if owner_railroads == 2 else total * 10

                if player.money >= rent:
                    player.money -= rent
                    prop.owner.money += rent
                    result["text"] += f"💰 Вы заплатили аренду *{rent}* @{prop.owner.username}"
                else:
                    player.alive = False
                    for p in player.properties:
                        p.owner = prop.owner
                        prop.owner.properties.append(p)
                    player.properties = []
                    result["text"] += f"💔 Вы обанкротились! Все имущество переходит @{prop.owner.username}"
            else:
                result["text"] += f"🏠 Ваша собственность"

        return result

    def get_chance_card(self):
        """Случайная карточка шанса"""
        cards = [
            {"text": "Выходите из тюрьмы бесплатно", "money": 0, "position": None, "jail_card": True},
            {"text": "Отправляйтесь на Вокзал", "money": 0, "position": 5, "jail_card": False},
            {"text": "Получите дивиденды 50", "money": 50, "position": None, "jail_card": False},
            {"text": "Штраф за превышение скорости 15", "money": -15, "position": None, "jail_card": False},
            {"text": "Отправляйтесь в тюрьму", "money": 0, "position": 10, "jail_card": False},
            {"text": "Вы выиграли в лотерею 100", "money": 100, "position": None, "jail_card": False},
            {"text": "Платите страховку 50", "money": -50, "position": None, "jail_card": False},
            {"text": "Отправляйтесь на Старт", "money": 200, "position": 0, "jail_card": False},
        ]
        return random.choice(cards)

    def get_community_chest(self):
        """Случайная карточка казны"""
        cards = [
            {"text": "Банковская ошибка в вашу пользу 200", "money": 200, "position": None},
            {"text": "Платеж за лечение 100", "money": -100, "position": None},
            {"text": "Вы нашли деньги 50", "money": 50, "position": None},
            {"text": "Рождественский подарок 100", "money": 100, "position": None},
            {"text": "Штраф за неуплату налогов 50", "money": -50, "position": None},
            {"text": "Вы получили наследство 200", "money": 200, "position": None},
            {"text": "Отправляйтесь на Старт", "money": 200, "position": 0},
        ]
        return random.choice(cards)

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
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# Функции для создания клавиатур
def get_main_keyboard():
    keyboard = [
        ["🎮 Создать игру", "📋 Список игр"],
        ["▶️ Начать игру", "❓ Помощь"],
        ["ℹ️ О боте"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_game_keyboard():
    keyboard = [
        ["🎲 Бросить кости", "🏠 Мои карты"],
        ["💬 Чат", "🚪 Покинуть игру"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_games_keyboard():
    keyboard = [
        ["🔍 Присоединиться к игре"],
        ["◀️ Вернуться в главное меню"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_empty_keyboard():
    return ReplyKeyboardMarkup([[]], resize_keyboard=True)

# Проверка, находится ли игрок в игре
def get_player_game(user_id: int) -> Optional[Game]:
    for game in games.values():
        if user_id in game.players and game.started:
            return game
    return None

# Обработчик текстовых сообщений
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or f"Player_{user_id}"
    chat_id = update.effective_chat.id

    # Получаем игру игрока
    game = get_player_game(user_id)

    if game:
        # ИГРОК В ИГРЕ - обрабатываем игровые действия
        # Проверка на аукцион
        if game.auction and game.auction.active:
            if text.isdigit():
                bid = int(text)
                # Минимальная ставка: текущая ставка + 1
                min_bid = game.auction.current_bid + 1

                if bid >= min_bid and game.auction.current_bidder != user_id:
                    game.auction.current_bid = bid
                    game.auction.current_bidder = user_id
                    game.auction.has_bids = True

                    # Если это первая ставка - запускаем отсчет
                    if not game.auction.countdown_active:
                        game.auction.countdown_active = True
                        game.auction.countdown = 5
                        # Запускаем обратный отсчет
                        asyncio.create_task(auction_countdown(game, context))
                    else:
                        # Сброс отсчета до 5 секунд
                        game.auction.countdown = 5

                    # Отправляем сообщение о новой ставке
                    await context.bot.send_message(
                        chat_id=game.chat_id,
                        text=f"💰 *@{username}* повысил ставку до *{bid}*!\n"
                             f"Минимальная следующая ставка: *{bid + 1}*",
                        parse_mode=ParseMode.MARKDOWN
                    )

                    # Обновляем сообщение аукциона
                    if game.auction.message_id:
                        try:
                            countdown_text = f"5..." if game.auction.countdown == 5 else f"{game.auction.countdown}..."
                            current_bidder_text = f"@{game.players[game.auction.current_bidder].username}"
                            await context.bot.edit_message_text(
                                chat_id=game.chat_id,
                                message_id=game.auction.message_id,
                                text=f"🏠 *АУКЦИОН!*\n\n"
                                     f"Продается: *{game.auction.property_name}*\n"
                                     f"Текущая ставка: *{game.auction.current_bid}*💰 от {current_bidder_text}\n"
                                     f"Минимальная следующая ставка: *{game.auction.current_bid + 1}*💰\n\n"
                                     f"Обратный отсчет: {countdown_text}",
                                parse_mode=ParseMode.MARKDOWN
                            )
                        except:
                            pass
                else:
                    await update.message.reply_text(
                        f"❌ Ставка должна быть больше текущей! Минимум: *{min_bid}*",
                        parse_mode=ParseMode.MARKDOWN
                    )
                return

        # Обработка игровых кнопок
        if text == "🎲 Бросить кости":
            await handle_dice_roll(update, context, game, user_id)
        elif text == "🏠 Мои карты":
            await show_my_cards(update, context, game, user_id)
        elif text == "💬 Чат":
            await show_chat(update, context, game)
        elif text == "🚪 Покинуть игру":
            await leave_game(update, context, game, user_id)
        elif text.startswith('/'):
            # Игнорируем команды
            pass
        else:
            # Обычное сообщение - отправляем в чат игры
            game.add_chat_message(user_id, username, text)

            # Отправляем сообщение всем игрокам игры
            for pid in game.players.keys():
                if pid != user_id:
                    try:
                        await context.bot.send_message(
                            chat_id=pid,
                            text=f"💬 *@{username}:* {text}",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except:
                        pass

            # Подтверждение отправителю
            await update.message.reply_text(
                "✅ Сообщение отправлено в игровой чат",
                reply_markup=get_game_keyboard()
            )

    else:
        # ИГРОК НЕ В ИГРЕ - обрабатываем меню (только в приватном чате)
        if chat_id == user_id:  # Проверяем что это приватный чат
            if text == "🎮 Создать игру":
                await create_game(update, context)
            elif text == "📋 Список игр":
                await update.message.reply_text(
                    "📋 *Список активных игр*\n\nВведите код игры чтобы присоединиться:",
                    reply_markup=get_games_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
                await list_games_command(update, context)
            elif text == "▶️ Начать игру":
                await start_game_from_button(update, context)
            elif text == "❓ Помощь":
                await help_command(update, context)
            elif text == "ℹ️ О боте":
                await info_command(update, context)
            elif text == "🔍 Присоединиться к игре":
                await update.message.reply_text(
                    "🔍 Введите код игры в формате:\n/join 123456789",
                    parse_mode=ParseMode.MARKDOWN
                )
            elif text == "◀️ Вернуться в главное меню":
                await start(update, context)
            else:
                await update.message.reply_text(
                    "Используйте кнопки ниже для навигации:",
                    reply_markup=get_main_keyboard()
                )
        else:
            # Сообщение из публичного чата - игнорируем
            pass

async def show_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, game: Game):
    """Показать историю чата"""
    chat_history = game.get_chat_history()
    await update.message.reply_text(
        chat_history,
        reply_markup=get_game_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def start_auction(game: Game, property_name: str, property_price: int, position: int, context: ContextTypes.DEFAULT_TYPE):
    """Начать аукцион"""
    game.auction = Auction(property_name, property_price, game.chat_id, position)

    # Убираем клавиатуры у всех игроков
    for player_id in game.players.keys():
        try:
            await context.bot.send_message(
                chat_id=player_id,
                text=f"🏠 *АУКЦИОН НАЧАЛСЯ!*\n\n"
                     f"Продается: *{property_name}*\n"
                     f"Стартовая цена: *{game.auction.current_bid}*💰\n\n"
                     f"*Правила:*\n"
                     f"• Пишите в чат число больше текущей ставки\n"
                     f"• Минимальное повышение: *+1*💰\n"
                     f"• Отсчет 5 секунд начнется после первой ставки\n"
                     f"• После каждой ставки отсчет сбрасывается до 5 секунд",
                reply_markup=get_empty_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass

    message = await context.bot.send_message(
        chat_id=game.chat_id,
        text=f"🏠 *АУКЦИОН!*\n\n"
             f"Продается: *{property_name}*\n"
             f"Стартовая цена: *{game.auction.current_bid}*💰\n\n"
             f"*Ожидание первой ставки...*",
        parse_mode=ParseMode.MARKDOWN
    )

    game.auction.message_id = message.message_id

async def auction_countdown(game: Game, context: ContextTypes.DEFAULT_TYPE):
    """Обратный отсчет для аукциона"""
    while game.auction and game.auction.active and game.auction.countdown > 0:
        await asyncio.sleep(1)
        game.auction.countdown -= 1

        # Обновляем сообщение с отсчетом
        if game.auction and game.auction.message_id:
            try:
                countdown_text = f"{game.auction.countdown}..."
                current_bidder_text = f"@{game.players[game.auction.current_bidder].username}"
                await context.bot.edit_message_text(
                    chat_id=game.chat_id,
                    message_id=game.auction.message_id,
                    text=f"🏠 *АУКЦИОН!*\n\n"
                         f"Продается: *{game.auction.property_name}*\n"
                         f"Текущая ставка: *{game.auction.current_bid}*💰 от {current_bidder_text}\n"
                         f"Минимальная следующая ставка: *{game.auction.current_bid + 1}*💰\n\n"
                         f"Обратный отсчет: {countdown_text}",
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass

    if game.auction and game.auction.active:
        # Аукцион завершен
        if game.auction.current_bidder:
            winner = game.players[game.auction.current_bidder]
            prop = game.properties[game.auction.position]

            if winner.money >= game.auction.current_bid:
                winner.money -= game.auction.current_bid
                winner.properties.append(prop)
                prop.owner = winner

                await context.bot.send_message(
                    chat_id=game.chat_id,
                    text=f"🎉 *АУКЦИОН ЗАВЕРШЕН!*\n\n"
                         f"*@{winner.username}* побеждает со ставкой *{game.auction.current_bid}*💰\n"
                         f"И получает *{game.auction.property_name}*!",
                    parse_mode=ParseMode.MARKDOWN
                )

                # Возвращаем клавиатуры всем игрокам
                for pid in game.players.keys():
                    try:
                        await context.bot.send_message(
                            chat_id=pid,
                            text="🎮 Игра продолжается!",
                            reply_markup=get_game_keyboard()
                        )
                    except:
                        pass
            else:
                await context.bot.send_message(
                    chat_id=game.chat_id,
                    text=f"❌ Победитель не может оплатить ставку!\n"
                         f"Аукцион отменяется.",
                    parse_mode=ParseMode.MARKDOWN
                )

                # Возвращаем клавиатуры
                for pid in game.players.keys():
                    try:
                        await context.bot.send_message(
                            chat_id=pid,
                            text="🎮 Игра продолжается!",
                            reply_markup=get_game_keyboard()
                        )
                    except:
                        pass
        else:
            await context.bot.send_message(
                chat_id=game.chat_id,
                text=f"❌ Аукцион завершен без ставок.\n"
                     f"*{game.auction.property_name}* остается непроданным.",
                parse_mode=ParseMode.MARKDOWN
            )

            # Возвращаем клавиатуры
            for pid in game.players.keys():
                try:
                    await context.bot.send_message(
                        chat_id=pid,
                        text="🎮 Игра продолжается!",
                        reply_markup=get_game_keyboard()
                    )
                except:
                    pass

        game.auction = None

async def handle_dice_roll(update: Update, context: ContextTypes.DEFAULT_TYPE, game: Game, user_id: int):
    """Обработка броска костей"""
    player = game.players[user_id]

    if user_id != game.current_turn:
        await update.message.reply_text(
            "❌ Сейчас не ваш ход!",
            reply_markup=get_game_keyboard()
        )
        return

    if game.dice_rolled:
        await update.message.reply_text(
            "❌ Вы уже бросили кости в этом ходу!",
            reply_markup=get_game_keyboard()
        )
        return

    dice1, dice2, total, is_double = game.roll_dice()
    game.dice_rolled = True

    if player.in_jail:
        if is_double:
            player.in_jail = False
            player.jail_turns = 0
            await update.message.reply_text(
                f"🚓 *@{player.username}* выбросил дубль и вышел из тюрьмы!\n"
                f"🎲 {dice1} + {dice2} = {total}",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            player.jail_turns += 1
            if player.jail_turns >= 3:
                player.in_jail = False
                player.jail_turns = 0
                await update.message.reply_text(
                    f"🚓 *@{player.username}* отсидел 3 хода и вышел из тюрьмы!",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    f"🚓 *@{player.username}* в тюрьме. Осталось ходов: {3 - player.jail_turns}",
                    reply_markup=get_game_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
                game.next_turn()
                return

    old_position = player.position
    player.position = (player.position + total) % 40

    passed_start = False
    if player.position < old_position:
        player.money += 200
        passed_start = True

    landing_result = game.handle_landing(player, player.position)

    result_text = (
        f"🎲 *@{player.username}* бросает кости:\n"
        f"*{dice1}* + *{dice2}* = *{total}*\n"
        f"📍 *{old_position}* → *{player.position}*\n\n"
    )

    if passed_start:
        result_text += f"💰 Проход через Старт: *+200*💰\n\n"

    result_text += landing_result["text"]

    # Отправляем результат всем игрокам
    for pid in game.players.keys():
        try:
            await context.bot.send_message(
                chat_id=pid,
                text=result_text,
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass

    if landing_result["action"] == "buy":
        position = landing_result["data"]
        prop = game.properties[position]

        keyboard = [
            [
                InlineKeyboardButton(f"💰 Купить за {prop.price}", callback_data=f"buy_{game.chat_id}_{position}"),
                InlineKeyboardButton(f"🏠 Аукцион", callback_data=f"auction_{game.chat_id}_{position}")
            ]
        ]

        await context.bot.send_message(
            chat_id=user_id,
            text=f"🏠 Хотите купить *{prop.name}*?\n"
                 f"💰 Цена: *{prop.price}*\n"
                 f"💵 Аренда: *{prop.rent[0]}*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

    if not player.alive:
        await handle_bankruptcy(game, context)
        return

    next_result = game.next_turn()
    if next_result:
        await context.bot.send_message(
            chat_id=game.chat_id,
            text=next_result,
            parse_mode=ParseMode.MARKDOWN
        )

    next_player = game.players[game.current_turn]
    await context.bot.send_message(
        chat_id=next_player.user_id,
        text=f"🎯 *Ваш ход!*\n"
             f"💰 Баланс: *{next_player.money}*\n"
             f"🏠 Собственность: *{len(next_player.properties)}*",
        reply_markup=get_game_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def show_my_cards(update: Update, context: ContextTypes.DEFAULT_TYPE, game: Game, user_id: int):
    """Показать карты игрока"""
    player = game.players[user_id]

    if not player.properties:
        await update.message.reply_text(
            "🏠 У вас пока нет собственности.",
            reply_markup=get_game_keyboard()
        )
        return

    text = f"🏠 *Карты @{player.username}*\n\n"
    text += f"💰 Баланс: *{player.money}*\n\n"
    text += "*Собственность:*\n"

    for prop in player.properties:
        if prop.name not in ["Вокзал", "Электростанция", "Водопровод"]:
            text += f"• *{prop.name}* ({prop.color})\n"
            text += f"  Аренда: *{prop.rent[0]}* | Дома: *{prop.houses}*\n"
        else:
            text += f"• *{prop.name}*\n"

    await update.message.reply_text(
        text,
        reply_markup=get_game_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def leave_game(update: Update, context: ContextTypes.DEFAULT_TYPE, game: Game, user_id: int):
    """Покинуть игру"""
    if user_id == game.creator_id:
        # Создатель завершает игру для всех
        for pid in game.players.keys():
            try:
                await context.bot.send_message(
                    chat_id=pid,
                    text=f"🛑 Игра завершена создателем.",
                    reply_markup=get_main_keyboard()
                )
            except:
                pass
        del games[game.chat_id]
    else:
        # Игрок выходит
        player = game.players[user_id]
        player.alive = False

        await update.message.reply_text(
            f"👋 Вы покинули игру.",
            reply_markup=get_main_keyboard()
        )

        # Уведомляем остальных
        for pid in game.players.keys():
            if pid != user_id:
                try:
                    await context.bot.send_message(
                        chat_id=pid,
                        text=f"👋 *@{player.username}* покинул игру.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass

        # Проверка на победителя
        alive_players = [p for p in game.players.values() if p.alive]
        if len(alive_players) == 1:
            winner = alive_players[0]
            for pid in game.players.keys():
                try:
                    await context.bot.send_message(
                        chat_id=pid,
                        text=f"🏆 *@{winner.username}* победил в игре!",
                        reply_markup=get_main_keyboard(),
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
            del games[game.chat_id]

async def handle_bankruptcy(game: Game, context: ContextTypes.DEFAULT_TYPE):
    """Обработка банкротства"""
    alive_players = [p for p in game.players.values() if p.alive]

    if len(alive_players) == 1:
        winner = alive_players[0]
        for pid in game.players.keys():
            try:
                await context.bot.send_message(
                    chat_id=pid,
                    text=f"🏆 *@{winner.username}* победил в игре!",
                    reply_markup=get_main_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
        del games[game.chat_id]
        return

    # Обновляем очередь ходов
    if game.current_turn not in [p.user_id for p in alive_players]:
        game.current_turn = alive_players[0].user_id

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Проверяем что это приватный чат
    if chat_id != user_id:
        await update.message.reply_text(
            "❌ Бот работает только в личных сообщениях!\n"
            "Напишите мне в личку: @MonopolyGameBot"
        )
        return

    if get_player_game(user_id):
        await update.message.reply_text(
            "🎮 Вы сейчас в игре!",
            reply_markup=get_game_keyboard()
        )
        return

    welcome_text = (
        "🎲 *Добро пожаловать в Monopoly Bot!*\n\n"
        "Здесь вы можете сыграть в классическую монополию с друзьями.\n\n"
        "*Используйте кнопки ниже для навигации:*"
    )
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

# Начать игру из кнопки
async def start_game_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    for game_id, game in games.items():
        if game.creator_id == user_id and not game.started:
            if len(game.players) < 2:
                await update.message.reply_text(
                    f"❌ Нужно минимум 2 игрока для начала игры!\n"
                    f"Сейчас игроков: *{len(game.players)}*",
                    reply_markup=get_main_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            game.start_game()

            await update_game_message(game, context)

            start_msg = (
                f"🎮 *Игра #{game_id} началась!*\n\n"
                f"Первый ход: *@{game.players[game.current_turn].username}*\n\n"
                f"💰 У всех игроков по *1500*"
            )

            for player_id in game.players.keys():
                try:
                    await context.bot.send_message(
                        chat_id=player_id,
                        text=start_msg,
                        reply_markup=get_game_keyboard(),
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass

            await update.message.reply_text(
                "✅ Игра началась!",
                reply_markup=get_game_keyboard()
            )
            return

    await update.message.reply_text(
        "❌ У вас нет созданных игр!\n"
        "Сначала создайте игру через кнопку '🎮 Создать игру'.",
        reply_markup=get_main_keyboard()
    )

# Создание игры
async def create_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or f"Player_{user_id}"

    # Проверяем что это приватный чат
    if chat_id != user_id:
        await update.message.reply_text("❌ Игры создаются только в личных сообщениях!")
        return

    if get_player_game(user_id):
        await update.message.reply_text(
            "❌ Вы не можете создать игру, так как уже находитесь в другой игре!"
        )
        return

    if chat_id in games:
        await update.message.reply_text(
            "❌ У вас уже есть активная игра!"
        )
        return

    game = Game(chat_id, user_id, username)
    game.add_player(user_id, username)
    games[chat_id] = game

    # Инлайн кнопки для создателя
    keyboard = [
        [
            InlineKeyboardButton("▶️ Начать игру", callback_data=f"start_{chat_id}"),
            InlineKeyboardButton("❌ Отменить игру", callback_data=f"cancel_{chat_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем сообщение
    message = await update.message.reply_text(
        f"✅ *Игра успешно создана!*\n\n"
        f"📋 *Код игры:* `{chat_id}`\n"
        f"👑 *Создатель:* @{username}\n"
        f"👥 *Игроки:* 1/{game.max_players}\n\n"
        f"🔗 *Нажмите на код чтобы скопировать:* `{chat_id}`\n\n"
        f"Ожидаем игроков...",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

    game.message_id = message.message_id

# Команда /join
async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or f"Player_{user_id}"
    chat_id = update.effective_chat.id

    # Проверяем что это приватный чат
    if chat_id != user_id:
        await update.message.reply_text("❌ Присоединяться к играм можно только в личных сообщениях!")
        return

    if get_player_game(user_id):
        await update.message.reply_text(
            "❌ Вы не можете присоединиться к игре, так как уже находитесь в другой игре!"
        )
        return

    if not context.args:
        await update.message.reply_text(
            "❌ Использование: /join [код игры]\n"
            "Например: `/join 123456789`",
            reply_markup=get_games_keyboard()
        )
        return

    try:
        game_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный код игры! Код должен быть числом.",
            reply_markup=get_games_keyboard()
        )
        return

    if game_id not in games:
        await update.message.reply_text(
            "❌ Игра с таким кодом не найдена!\n"
            "Проверьте код или посмотрите список доступных игр.",
            reply_markup=get_games_keyboard()
        )
        return

    game = games[game_id]

    if game.started:
        await update.message.reply_text(
            "❌ Игра уже началась!",
            reply_markup=get_games_keyboard()
        )
        return

    if len(game.players) >= game.max_players:
        await update.message.reply_text(
            f"❌ В игре уже максимальное количество игроков (*{game.max_players}*)!",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if user_id in game.players:
        await update.message.reply_text(
            "❌ Вы уже в этой игре!",
            reply_markup=get_games_keyboard()
        )
        return

    if user_id == game.creator_id:
        await update.message.reply_text(
            "❌ Вы создатель этой игры!",
            reply_markup=get_games_keyboard()
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
            text=f"👋 *@{username}* хочет присоединиться к вашей игре!\n\n"
                 f"Игрок: *@{username}*\n\n"
                 f"Принять запрос?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

        await update.message.reply_text(
            f"✅ Запрос отправлен создателю игры *@{game.creator_name}*!\n"
            f"Ожидайте ответа...",
            reply_markup=get_games_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        await update.message.reply_text(
            "❌ Не удалось отправить запрос создателю игры."
        )

# Список игр
async def list_games_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список всех активных игр"""
    user_id = update.effective_user.id

    if get_player_game(user_id):
        return

    if not games:
        await update.message.reply_text(
            "📋 *Список активных игр*\n\n"
            "😴 Нет активных игр.\n\n"
            "Создайте свою игру через кнопку '🎮 Создать игру'!",
            reply_markup=get_games_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    text = "📋 *Доступные игры:*\n\n"
    games_found = False

    for game_id, game in games.items():
        if not game.started and len(game.players) < game.max_players:
            games_found = True
            text += f"🎮 *Игра #{game_id}*\n"
            text += f"👑 Создатель: *@{game.creator_name}*\n"
            text += f"👥 Игроки: *{len(game.players)}/{game.max_players}*\n"
            text += f"📝 *Код:* `{game_id}`\n"
            text += f"➖➖➖➖➖➖➖➖➖\n\n"

    if not games_found:
        text += "Нет доступных игр для присоединения.\n"

    text += "\n🔍 Чтобы присоединиться, нажмите кнопку '🔍 Присоединиться к игре' и введите код."

    await update.message.reply_text(
        text,
        reply_markup=get_games_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

# Обработка инлайн кнопок
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    action = data[0]

    if action == "cancel":
        game_id = int(data[1])

        if game_id not in games:
            await query.edit_message_text("❌ Игра больше не существует!")
            return

        game = games[game_id]
        user_id = update.effective_user.id

        if user_id != game.creator_id:
            await query.edit_message_text("❌ Только создатель может отменить игру!")
            return

        del games[game_id]
        await query.edit_message_text("🛑 Игра отменена создателем.")

        await context.bot.send_message(
            chat_id=user_id,
            text="✅ Игра успешно отменена.",
            reply_markup=get_main_keyboard()
        )

    elif action == "accept" or action == "reject":
        game_id = int(data[1])
        requester_id = int(data[2])

        if game_id not in games:
            await query.edit_message_text("❌ Игра больше не существует!")
            return

        game = games[game_id]

        if action == "accept":
            username = game.pending_requests.get(requester_id, f"Player_{requester_id}")

            if game.add_player(requester_id, username):
                await query.edit_message_text(
                    f"✅ Игрок *@{username}* принят в игру!",
                    parse_mode=ParseMode.MARKDOWN
                )

                await update_game_message(game, context)

                # Отправляем игровую клавиатуру новому игроку
                try:
                    await context.bot.send_message(
                        chat_id=requester_id,
                        text=f"✅ Вы приняты в игру *#{game_id}*!\n"
                             f"Ожидайте начала игры.",
                        reply_markup=get_game_keyboard(),
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
            else:
                await query.edit_message_text(
                    f"❌ Не удалось добавить игрока. Максимум игроков: {game.max_players}"
                )

        elif action == "reject":
            username = game.pending_requests.get(requester_id, f"Player_{requester_id}")

            await query.edit_message_text(
                f"❌ Запрос от *@{username}* отклонен.",
                parse_mode=ParseMode.MARKDOWN
            )

            try:
                await context.bot.send_message(
                    chat_id=requester_id,
                    text=f"❌ Ваш запрос на вступление в игру *#{game_id}* был отклонен создателем.",
                    reply_markup=get_main_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass

        if requester_id in game.pending_requests:
            del game.pending_requests[requester_id]

    elif action == "start":
        game_id = int(data[1])

        if game_id not in games:
            await query.edit_message_text("❌ Игра больше не существует!")
            return

        game = games[game_id]
        user_id = update.effective_user.id

        if user_id != game.creator_id:
            await query.edit_message_text("❌ Только создатель игры может начать!")
            return

        if len(game.players) < 2:
            await query.edit_message_text("❌ Нужно минимум 2 игрока для начала!")
            return

        game.start_game()

        await update_game_message(game, context)

        start_msg = (
            f"🎮 *Игра #{game_id} началась!*\n\n"
            f"Первый ход: *@{game.players[game.current_turn].username}*"
        )

        for player_id in game.players.keys():
            try:
                await context.bot.send_message(
                    chat_id=player_id,
                    text=start_msg,
                    reply_markup=get_game_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass

        await query.edit_message_text("✅ Игра началась!")

    elif action == "buy":
        game_id = int(data[1])
        position = int(data[2])

        if game_id not in games:
            await query.edit_message_text("❌ Игра больше не существует!")
            return

        game = games[game_id]
        user_id = update.effective_user.id
        player = game.players[user_id]
        prop = game.properties[position]

        if player.buy_property(prop):
            await query.edit_message_text(
                f"✅ Вы купили *{prop.name}* за *{prop.price}*💰",
                parse_mode=ParseMode.MARKDOWN
            )

            # Уведомляем всех
            for pid in game.players.keys():
                if pid != user_id:
                    try:
                        await context.bot.send_message(
                            chat_id=pid,
                            text=f"🏠 *@{player.username}* купил *{prop.name}*",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except:
                        pass
        else:
            await query.edit_message_text(
                f"❌ У вас недостаточно денег! Нужно: *{prop.price}*💰",
                parse_mode=ParseMode.MARKDOWN
            )

    elif action == "auction":
        game_id = int(data[1])
        position = int(data[2])

        if game_id not in games:
            await query.edit_message_text("❌ Игра больше не существует!")
            return

        game = games[game_id]
        prop = game.properties[position]

        await query.edit_message_text(
            f"🏠 Объявлен аукцион на *{prop.name}*!",
            parse_mode=ParseMode.MARKDOWN
        )

        await start_auction(game, prop.name, prop.price, position, context)

async def update_game_message(game: Game, context: ContextTypes.DEFAULT_TYPE):
    """Обновляет сообщение с игрой"""
    if not game.message_id:
        return

    players_list = "\n".join([f"• *@{p.username}*" for p in game.players.values()])

    keyboard = [
        [
            InlineKeyboardButton("▶️ Начать игру", callback_data=f"start_{game.chat_id}"),
            InlineKeyboardButton("❌ Отменить игру", callback_data=f"cancel_{game.chat_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.edit_message_text(
            chat_id=game.chat_id,
            message_id=game.message_id,
            text=f"✅ *Игра #{game.chat_id}*\n\n"
                 f"👑 *Создатель:* @{game.creator_name}\n"
                 f"👥 *Игроки ({len(game.players)}/{game.max_players}):*\n{players_list}\n\n"
                 f"🔗 *Код игры:* `{game.chat_id}`\n\n"
                 f"Ожидаем игроков...",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass

# Помощь
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if get_player_game(user_id):
        await update.message.reply_text(
            "🎮 Используйте игровые кнопки:\n"
            "• 🎲 Бросить кости - сделать ход\n"
            "• 🏠 Мои карты - показать вашу собственность\n"
            "• 💬 Чат - написать в игровой чат\n"
            "• 🚪 Покинуть игру - выйти из игры",
            reply_markup=get_game_keyboard()
        )
        return

    help_text = (
        "❓ *Помощь по боту*\n\n"
        "*Основные кнопки:*\n"
        "• 🎮 Создать игру - создать новую игру\n"
        "• 📋 Список игр - показать активные игры\n"
        "• ▶️ Начать игру - начать вашу созданную игру\n"
        "• ❓ Помощь - это меню\n"
        "• ℹ️ О боте - информация\n\n"
        "*Как играть:*\n"
        "1. Создайте игру или присоединитесь к существующей\n"
        "2. Дождитесь пока наберется минимум 2 игрока\n"
        "3. Создатель начинает игру\n"
        "4. В свой ход бросайте кости\n"
        "5. Покупайте собственность или участвуйте в аукционе\n"
        "6. Собирайте аренду с других игроков\n"
        "7. Побеждает последний выживший!\n\n"
        "*Аукцион:*\n"
        "• Если не хотите покупать за полную цену - объявляется аукцион\n"
        "• Все игроки могут делать ставки числами в чат\n"
        "• Минимальное повышение: *+1*💰\n"
        "• Отсчет 5 секунд начинается после первой ставки\n"
        "• После каждой ставки отсчет сбрасывается до 5 секунд\n"
        "• Кто предложит больше всех - забирает собственность\n\n"
        "*Чат:*\n"
        "• Игроки могут общаться в игровом чате\n"
        "• Сообщения видят все участники игры\n\n"
        "*Максимум игроков:* 6"
    )
    await update.message.reply_text(
        help_text,
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

# Информация о боте
async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if get_player_game(user_id):
        return

    info_text = (
        "ℹ️ *О боте*\n\n"
        "*Monopoly Bot v4.0*\n\n"
        "*Особенности:*\n"
        "• Полное поле Monopoly (40 клеток)\n"
        "• До *6 игроков* в одной игре\n"
        "• Система запросов на вступление\n"
        "• Покупка недвижимости\n"
        "• *Аукционы* с шагом 1💰\n"
        "• *Игровой чат* для общения\n"
        "• Случайные события (Шанс/Казна)\n"
        "• Тюрьма и налоги\n"
        "• Джекпот на бесплатной парковке\n"
        "• Работает 24/7\n\n"
        "*Разработчик:* Monopoly Team\n"
        "*Платформа:* BotHost\n\n"
        "Играйте с друзьями и получайте удовольствие! 🎉"
    )
    await update.message.reply_text(
        info_text,
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

# Обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла внутренняя ошибка. Попробуйте позже.",
            reply_markup=get_main_keyboard()
        )

def main():
    """Запуск бота"""
    print("🚀 Запуск Monopoly Bot v4.0...")
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

    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

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
