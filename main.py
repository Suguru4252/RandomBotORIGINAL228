import os
import logging
import random
import json
import threading
import asyncio
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime, timedelta

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

# Класс трейда
class Trade:
    def __init__(self, proposer_id: int, target_id: int, game_id: int):
        self.proposer_id = proposer_id
        self.target_id = target_id
        self.game_id = game_id
        self.proposer_properties = []
        self.target_properties = []
        self.proposer_money = 0
        self.target_money = 0
        self.active = True
        self.message_id = None
        self.step = "select_players"  # Этап трейда

# Класс карты (собственности)
class Property:
    def __init__(self, name: str, price: int, color: str, rent: list, house_price: int = 50):
        self.name = name
        self.price = price
        self.color = color
        self.rent = rent
        self.house_price = house_price
        self.owner = None
        self.houses = 0
        self.hotel = False
        self.mortgaged = False
        self.position = 0
        
    def get_rent(self):
        if self.hotel:
            return self.rent[5]
        else:
            return self.rent[self.houses]
    
    def can_buy_house(self):
        if self.hotel:
            return False
        if self.houses >= 4:
            return False
        # Проверка на наличие всей цветовой группы
        if self.owner:
            same_color = [p for p in self.owner.properties if p.color == self.color and p.name != self.name]
            # Для цветных групп нужно все той же группы
            if self.color not in ["railroad", "utility", "special"]:
                # Проверяем что есть все свойства этой группы
                all_props = [p for p in self.owner.properties if p.color == self.color]
                # В стандартной монополии по 2-3 свойства в группе
                group_sizes = {"коричневый": 2, "голубой": 3, "розовый": 3, "оранжевый": 3, 
                               "красный": 3, "желтый": 3, "зеленый": 3, "синий": 2}
                needed = group_sizes.get(self.color, 2)
                if len(all_props) < needed:
                    return False
        return True
    
    def can_buy_hotel(self):
        return self.houses == 4 and not self.hotel
    
    def buy_house(self):
        if self.can_buy_house():
            self.houses += 1
            return True
        return False
    
    def buy_hotel(self):
        if self.can_buy_hotel():
            self.hotel = True
            return True
        return False

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
        self.consecutive_doubles = 0
        self.trade_offers = []
        self.last_action_time = datetime.now()  # Для таймера
        
    def update_action_time(self):
        self.last_action_time = datetime.now()
        
    def buy_property(self, property: Property) -> bool:
        if self.money >= property.price:
            self.money -= property.price
            self.properties.append(property)
            property.owner = self
            return True
        return False
    
    def buy_house(self, property: Property) -> bool:
        if self.money >= property.house_price and property.owner == self:
            self.money -= property.house_price
            property.buy_house()
            return True
        return False
    
    def buy_hotel(self, property: Property) -> bool:
        if self.money >= property.house_price and property.owner == self:
            self.money -= property.house_price
            property.buy_hotel()
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
        self.board = self.create_board()
        self.owned_properties = {}
        self.dice_rolled = False
        self.message_id = None
        self.jackpot = 0
        self.auction: Optional[Auction] = None
        self.trades: Dict[int, Trade] = {}
        self.next_trade_id = 1
        self.chat_messages = []
        self.turn_timer_task = None  # Для таймера
        
    def create_board(self):
        board = []
        properties = [
            ("Старт", 0, "special", [0], 0),
            ("Улица Победы", 60, "коричневый", [2, 10, 30, 90, 160, 250], 50),
            ("Казна", 0, "special", [0], 0),
            ("Проспект Мира", 60, "коричневый", [4, 20, 60, 180, 320, 450], 50),
            ("Налог", 200, "tax", [200], 0),
            ("Вокзал", 200, "railroad", [25, 50, 100, 200], 0),
            ("Невский проспект", 100, "голубой", [6, 30, 90, 270, 400, 550], 50),
            ("Шанс", 0, "chance", [0], 0),
            ("Улица Горького", 100, "голубой", [6, 30, 90, 270, 400, 550], 50),
            ("Улица Чехова", 120, "голубой", [8, 40, 100, 300, 450, 600], 50),
            ("Тюрьма", 0, "jail", [0], 0),
            ("Пушкинская улица", 140, "розовый", [10, 50, 150, 450, 625, 750], 100),
            ("Электростанция", 150, "utility", [0], 0),
            ("Улица Лермонтова", 140, "розовый", [10, 50, 150, 450, 625, 750], 100),
            ("Улица Толстого", 160, "розовый", [12, 60, 180, 500, 700, 900], 100),
            ("Вокзал", 200, "railroad", [25, 50, 100, 200], 0),
            ("Улица Гагарина", 180, "оранжевый", [14, 70, 200, 550, 750, 950], 100),
            ("Казна", 0, "special", [0], 0),
            ("Улица Королева", 180, "оранжевый", [14, 70, 200, 550, 750, 950], 100),
            ("Улица Циолковского", 200, "оранжевый", [16, 80, 220, 600, 800, 1000], 100),
            ("Бесплатная парковка", 0, "special", [0], 0),
            ("Арбат", 220, "красный", [18, 90, 250, 700, 875, 1050], 150),
            ("Шанс", 0, "chance", [0], 0),
            ("Тверская улица", 220, "красный", [18, 90, 250, 700, 875, 1050], 150),
            ("Кузнецкий мост", 240, "красный", [20, 100, 300, 750, 925, 1100], 150),
            ("Вокзал", 200, "railroad", [25, 50, 100, 200], 0),
            ("Проспект Вернадского", 260, "желтый", [22, 110, 330, 800, 975, 1150], 150),
            ("Проспект Ленина", 260, "желтый", [22, 110, 330, 800, 975, 1150], 150),
            ("Водопровод", 150, "utility", [0], 0),
            ("Университетская", 280, "желтый", [24, 120, 360, 850, 1025, 1200], 150),
            ("Отправляйтесь в тюрьму", 0, "jail", [0], 0),
            ("Невский проспект", 300, "зеленый", [26, 130, 390, 900, 1100, 1275], 200),
            ("Улица Рубинштейна", 300, "зеленый", [26, 130, 390, 900, 1100, 1275], 200),
            ("Казна", 0, "special", [0], 0),
            ("Лиговский проспект", 320, "зеленый", [28, 150, 450, 1000, 1200, 1400], 200),
            ("Вокзал", 200, "railroad", [25, 50, 100, 200], 0),
            ("Шанс", 0, "chance", [0], 0),
            ("Красная площадь", 350, "синий", [35, 175, 500, 1100, 1300, 1500], 200),
            ("Налог", 100, "tax", [100], 0),
            ("Кремль", 400, "синий", [50, 200, 600, 1400, 1700, 2000], 200),
        ]
        
        for i, prop_data in enumerate(properties):
            name, price, color, rent, house_price = prop_data
            prop = Property(name, price, color, rent, house_price)
            prop.position = i
            board.append(prop)
        
        return board
    
    def get_utility_rent(self, player: Player, owner: Player, dice_total: int) -> int:
        utilities = [p for p in owner.properties if p.name in ["Электростанция", "Водопровод"]]
        if len(utilities) == 1:
            return dice_total * 4
        else:
            return dice_total * 10
    
    def get_railroad_rent(self, owner: Player) -> int:
        railroads = [p for p in owner.properties if p.name == "Вокзал"]
        if not railroads:
            return 0
        rent_table = [25, 50, 100, 200]
        return rent_table[len(railroads) - 1]
    
    def add_player(self, user_id: int, username: str) -> bool:
        if len(self.players) >= self.max_players:
            return False
        if user_id not in self.players:
            self.players[user_id] = Player(user_id, username)
            return True
        return False
    
    def start_game(self):
        self.started = True
        # Устанавливаем первого игрока
        self.current_turn = list(self.players.keys())[0]
        self.dice_rolled = False
        for player in self.players.values():
            player.in_game = True
            player.update_action_time()
        logger.info(f"Игра началась. Первый ход у игрока {self.current_turn}")
    
    def next_turn(self):
        """Переход к следующему игроку"""
        # Получаем список живых игроков
        alive_players = [pid for pid, p in self.players.items() if p.alive]
        
        if len(alive_players) == 1:
            return alive_players[0]  # Победитель
        
        # Находим индекс текущего игрока
        if self.current_turn not in alive_players:
            # Если текущий игрок мертв, берем первого живого
            self.current_turn = alive_players[0]
        else:
            current_index = alive_players.index(self.current_turn)
            next_index = (current_index + 1) % len(alive_players)
            self.current_turn = alive_players[next_index]
        
        # ВАЖНО: Сбрасываем флаг броска для нового игрока
        self.dice_rolled = False
        
        # Обновляем время действия для нового игрока
        if self.current_turn in self.players:
            self.players[self.current_turn].update_action_time()
        
        logger.info(f"Следующий ход: игрок {self.current_turn}")
        
        # Проверка на тюрьму
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
        is_double = (dice1 == dice2)
        logger.info(f"Бросок: {dice1}+{dice2}={dice1+dice2}, дубль: {is_double}")
        return dice1, dice2, dice1 + dice2, is_double
    
    def get_property_at(self, position: int) -> Property:
        return self.board[position]
    
    def add_chat_message(self, user_id: int, username: str, message: str):
        self.chat_messages.append({
            'user_id': user_id,
            'username': username,
            'message': message,
            'time': len(self.chat_messages)
        })
        if len(self.chat_messages) > 50:
            self.chat_messages = self.chat_messages[-50:]
    
    def get_chat_history(self, count: int = 10) -> str:
        if not self.chat_messages:
            return "*Чат игры:*\nПока нет сообщений"
        
        recent = self.chat_messages[-count:]
        result = "*Чат игры:*\n"
        for msg in recent:
            result += f"*@{msg['username']}:* {msg['message']}\n"
        return result
    
    def handle_landing(self, player: Player, position: int, dice_total: int = 0) -> dict:
        prop = self.board[position]
        result = {
            "text": f"*{prop.name}*\n",
            "action": None,
            "data": None
        }
        
        if position == 0:
            result["text"] += "🌟 Стартовая позиция"
        
        elif position == 4 or position == 38:
            amount = 200 if position == 4 else 100
            if player.money >= amount:
                player.money -= amount
                self.jackpot += amount
                result["text"] += f"💰 Вы заплатили налог *{amount}*💰"
            else:
                player.alive = False
                result["text"] += f"💔 У вас недостаточно денег для уплаты налога!"
        
        elif position == 10:
            result["text"] += "🚓 Вы посетили тюрьму (просто отдых)"
        
        elif position == 30:
            player.in_jail = True
            player.position = 10
            result["text"] += "🚓 Вы отправились в тюрьму на 3 хода!"
        
        elif position == 20:
            if self.jackpot > 0:
                player.money += self.jackpot
                result["text"] += f"💰 Вы получили джекпот: *{self.jackpot}*💰"
                self.jackpot = 0
            else:
                result["text"] += "🅿️ Бесплатная парковка"
        
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
        
        elif prop.name == "Вокзал":
            if prop.owner is None:
                result["action"] = "buy"
                result["data"] = position
                result["text"] += f"🏠 *Свободный вокзал*\n💰 Цена: *{prop.price}*"
            elif prop.owner.user_id != player.user_id:
                rent = self.get_railroad_rent(prop.owner)
                if player.money >= rent:
                    player.money -= rent
                    prop.owner.money += rent
                    result["text"] += f"💰 Вы заплатили аренду *{rent}* @{prop.owner.username}"
                else:
                    player.alive = False
                    result["text"] += f"💔 Вы обанкротились! Все имущество переходит @{prop.owner.username}"
            else:
                result["text"] += f"🏠 Ваш вокзал"
        
        elif prop.name in ["Электростанция", "Водопровод"]:
            if prop.owner is None:
                result["action"] = "buy"
                result["data"] = position
                result["text"] += f"🏠 *Свободная коммуналка*\n💰 Цена: *{prop.price}*"
            elif prop.owner.user_id != player.user_id:
                if dice_total == 0:
                    dice_total = random.randint(2, 12)
                rent = self.get_utility_rent(player, prop.owner, dice_total)
                if player.money >= rent:
                    player.money -= rent
                    prop.owner.money += rent
                    result["text"] += f"💰 Вы заплатили аренду *{rent}* @{prop.owner.username} (бросок: {dice_total})"
                else:
                    player.alive = False
                    result["text"] += f"💔 Вы обанкротились! Все имущество переходит @{prop.owner.username}"
            else:
                result["text"] += f"🏠 Ваша коммуналка"
        
        elif prop.price > 0:
            if prop.owner is None:
                result["action"] = "buy"
                result["data"] = position
                result["text"] += f"🏠 *Свободная собственность*\n💰 Цена: *{prop.price}*\n🏷️ Цвет: *{prop.color}*\n💵 Аренда: *{prop.get_rent()}*"
                if prop.houses > 0:
                    result["text"] += f"\n🏠 Домов: {prop.houses}"
                if prop.hotel:
                    result["text"] += f"\n🏨 Отель"
            elif prop.owner.user_id != player.user_id:
                rent = prop.get_rent()
                if player.money >= rent:
                    player.money -= rent
                    prop.owner.money += rent
                    result["text"] += f"💰 Вы заплатили аренду *{rent}* @{prop.owner.username}"
                    if prop.houses > 0:
                        result["text"] += f" (домов: {prop.houses})"
                    if prop.hotel:
                        result["text"] += f" (отель)"
                else:
                    player.alive = False
                    for p in player.properties:
                        p.owner = prop.owner
                        prop.owner.properties.append(p)
                    player.properties = []
                    result["text"] += f"💔 Вы обанкротились! Все имущество переходит @{prop.owner.username}"
            else:
                result["text"] += f"🏠 Ваша собственность\n🏠 Домов: {prop.houses}\n🏨 Отель: {'Да' if prop.hotel else 'Нет'}\n💰 Аренда: {prop.get_rent()}"
        
        return result
    
    def get_chance_card(self):
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

class Auction:
    def __init__(self, property_name: str, property_price: int, game_id: int, position: int):
        self.property_name = property_name
        self.property_price = property_price
        self.game_id = game_id
        self.position = position
        self.current_bid = property_price // 2
        self.current_bidder = None
        self.bidders: Dict[int, str] = {}
        self.active = True
        self.countdown = None
        self.countdown_active = False
        self.task = None
        self.message_id = None
        self.has_bids = False

games: Dict[int, Game] = {}

# Flask для BotHost
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

def get_player_game(user_id: int) -> Optional[Game]:
    for game in games.values():
        if user_id in game.players and game.started:
            return game
    return None

# Функция для проверки таймера хода
async def check_turn_timer(game: Game, context: ContextTypes.DEFAULT_TYPE):
    """Проверка таймера хода каждую минуту"""
    while game.started:
        await asyncio.sleep(60)  # Проверяем каждую минуту
        
        if not game.started:
            break
            
        current_player = game.players.get(game.current_turn)
        if not current_player:
            continue
            
        time_since_action = datetime.now() - current_player.last_action_time
        minutes_passed = time_since_action.total_seconds() / 60
        
        if minutes_passed >= 4 and minutes_passed < 5:
            # Предупреждение за 1 минуту до кика
            await context.bot.send_message(
                chat_id=current_player.user_id,
                text="⚠️ *Внимание!* У вас осталась 1 минута, чтобы сделать ход, иначе вы будете исключены из игры!",
                parse_mode=ParseMode.MARKDOWN
            )
        elif minutes_passed >= 5:
            # Кикаем игрока
            await context.bot.send_message(
                chat_id=game.chat_id,
                text=f"❌ *@{current_player.username}* исключен из игры за бездействие (5 минут без хода)!",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Удаляем игрока
            current_player.alive = False
            
            # Проверяем победителя
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
                break
            else:
                # Переходим к следующему игроку
                game.next_turn()
                next_player = game.players.get(game.current_turn)
                if next_player:
                    await context.bot.send_message(
                        chat_id=next_player.user_id,
                        text=f"🎯 *Ваш ход!*\n"
                             f"💰 Баланс: *{next_player.money}*\n"
                             f"🏠 Собственность: *{len(next_player.properties)}*",
                        reply_markup=get_game_keyboard(),
                        parse_mode=ParseMode.MARKDOWN
                    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or f"Player_{user_id}"
    chat_id = update.effective_chat.id
    
    game = get_player_game(user_id)
    
    if game:
        # Обновляем время действия
        if user_id in game.players:
            game.players[user_id].update_action_time()
        
        if game.auction and game.auction.active:
            if text.isdigit():
                bid = int(text)
                min_bid = game.auction.current_bid + 1
                
                if bid >= min_bid and game.auction.current_bidder != user_id:
                    game.auction.current_bid = bid
                    game.auction.current_bidder = user_id
                    game.auction.has_bids = True
                    
                    if not game.auction.countdown_active:
                        game.auction.countdown_active = True
                        game.auction.countdown = 5
                        asyncio.create_task(auction_countdown(game, context))
                    else:
                        game.auction.countdown = 5
                    
                    await context.bot.send_message(
                        chat_id=game.chat_id,
                        text=f"💰 *@{username}* повысил ставку до *{bid}*!\n"
                             f"Минимальная следующая ставка: *{bid + 1}*",
                        parse_mode=ParseMode.MARKDOWN
                    )
                return
        
        if text == "🎲 Бросить кости":
            await handle_dice_roll(update, context, game, user_id)
        elif text == "🏠 Мои карты":
            await show_my_cards(update, context, game, user_id)
        elif text == "💬 Чат":
            await show_chat(update, context, game)
        elif text == "🚪 Покинуть игру":
            await leave_game(update, context, game, user_id)
        elif text.startswith('/'):
            pass
        else:
            game.add_chat_message(user_id, username, text)
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
            await update.message.reply_text(
                "✅ Сообщение отправлено в игровой чат",
                reply_markup=get_game_keyboard()
            )
    
    else:
        if chat_id == user_id:
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

async def show_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, game: Game):
    chat_history = game.get_chat_history()
    await update.message.reply_text(
        chat_history,
        reply_markup=get_game_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_dice_roll(update: Update, context: ContextTypes.DEFAULT_TYPE, game: Game, user_id: int):
    """Обработка броска костей"""
    player = game.players[user_id]
    
    # Проверка что сейчас ход этого игрока
    if user_id != game.current_turn:
        current_player = game.players.get(game.current_turn)
        current_name = current_player.username if current_player else "неизвестно"
        
        await update.message.reply_text(
            f"❌ Сейчас не ваш ход! Сейчас ходит @{current_name}",
            reply_markup=get_game_keyboard()
        )
        return
    
    # Проверка что уже бросил
    if game.dice_rolled:
        await update.message.reply_text(
            "❌ Вы уже бросили кости в этом ходу!",
            reply_markup=get_game_keyboard()
        )
        return
    
    # Бросок костей
    dice1, dice2, total, is_double = game.roll_dice()
    game.dice_rolled = True
    player.update_action_time()  # Обновляем время
    
    logger.info(f"Игрок {player.username} бросил кости: {dice1}+{dice2}={total}, дубль: {is_double}")
    
    # Проверка на 3 дубля подряд (в тюрьму)
    if is_double:
        player.consecutive_doubles += 1
        if player.consecutive_doubles >= 3:
            player.in_jail = True
            player.position = 10
            player.consecutive_doubles = 0
            game.dice_rolled = False
            
            await context.bot.send_message(
                chat_id=game.chat_id,
                text=f"🚓 *@{player.username}* выбросил 3 дубля подряд и отправился в тюрьму!",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Переходим к следующему игроку
            game.next_turn()
            
            # Уведомляем следующего игрока
            if game.current_turn in game.players:
                next_player = game.players[game.current_turn]
                await context.bot.send_message(
                    chat_id=next_player.user_id,
                    text=f"🎯 *Ваш ход!*\n"
                         f"💰 Баланс: *{next_player.money}*\n"
                         f"🏠 Собственность: *{len(next_player.properties)}*",
                    reply_markup=get_game_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
            return
    else:
        player.consecutive_doubles = 0
    
    # Проверка на тюрьму
    if player.in_jail:
        if is_double:
            player.in_jail = False
            player.jail_turns = 0
            player.consecutive_doubles = 0
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
                player.money -= 50
                await update.message.reply_text(
                    f"🚓 *@{player.username}* отсидел 3 хода и вышел из тюрьмы за 50💰",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    f"🚓 *@{player.username}* в тюрьме. Осталось ходов: {3 - player.jail_turns}\n"
                    f"Выбросите дубль чтобы выйти раньше!",
                    reply_markup=get_game_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Переходим к следующему игроку
                game.next_turn()
                
                # Уведомляем следующего игрока
                if game.current_turn in game.players:
                    next_player = game.players[game.current_turn]
                    await context.bot.send_message(
                        chat_id=next_player.user_id,
                        text=f"🎯 *Ваш ход!*\n"
                             f"💰 Баланс: *{next_player.money}*\n"
                             f"🏠 Собственность: *{len(next_player.properties)}*",
                        reply_markup=get_game_keyboard(),
                        parse_mode=ParseMode.MARKDOWN
                    )
                return
    
    # Движение
    old_position = player.position
    player.position = (player.position + total) % 40
    
    # Проверка на прохождение старта
    passed_start = False
    if player.position < old_position and not player.in_jail:
        player.money += 200
        passed_start = True
    
    # Обработка клетки
    landing_result = game.handle_landing(player, player.position, total)
    
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
    
    # Если можно купить
    if landing_result["action"] == "buy":
        position = landing_result["data"]
        prop = game.board[position]
        
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
                 f"💵 Аренда: *{prop.get_rent()}*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Проверка на банкротство
    if not player.alive:
        await handle_bankruptcy(game, context)
        return
    
    # Если дубль - еще один ход
    if is_double and not player.in_jail:
        game.dice_rolled = False
        await context.bot.send_message(
            chat_id=game.chat_id,
            text=f"🎯 *@{player.username}* выбрасывает дубль и ходит еще раз!",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Переходим к следующему игроку
    game.next_turn()
    
    # Уведомляем следующего игрока
    if game.current_turn in game.players:
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
    """Показать карты игрока с инлайн кнопками"""
    player = game.players[user_id]
    
    if not player.properties:
        await update.message.reply_text(
            "🏠 У вас пока нет собственности.",
            reply_markup=get_game_keyboard()
        )
        return
    
    # Группировка по цветам
    by_color = {}
    for prop in player.properties:
        if prop.color not in by_color:
            by_color[prop.color] = []
        by_color[prop.color].append(prop)
    
    text = f"🏠 *Карты @{player.username}*\n\n"
    text += f"💰 Баланс: *{player.money}*\n\n"
    
    # Создаем инлайн кнопки для каждого свойства
    property_buttons = []
    
    for color, props in by_color.items():
        if color not in ["railroad", "utility", "special"]:
            text += f"*{color.upper()}*\n"
            for prop in props:
                text += f"  • *{prop.name}* - {prop.get_rent()}💰"
                if prop.houses > 0:
                    text += f" [{prop.houses}🏠]"
                if prop.hotel:
                    text += f" [🏨]"
                text += f"\n"
                # Добавляем кнопку для этого свойства
                property_buttons.append([InlineKeyboardButton(f"🏠 {prop.name}", callback_data=f"manage_prop_{game.chat_id}_{prop.position}")])
        else:
            for prop in props:
                if color == "railroad":
                    text += f"*🚂 {prop.name}*\n"
                elif color == "utility":
                    text += f"*⚡ {prop.name}*\n"
                property_buttons.append([InlineKeyboardButton(f"⚡ {prop.name}", callback_data=f"manage_prop_{game.chat_id}_{prop.position}")])
    
    # Кнопки действий
    action_buttons = [
        [InlineKeyboardButton("🔄 Предложить обмен", callback_data=f"trade_start_{game.chat_id}")],
        [InlineKeyboardButton("🏠 Построить дом", callback_data=f"show_houses_{game.chat_id}")],
        [InlineKeyboardButton("🏨 Построить отель", callback_data=f"show_hotels_{game.chat_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data=f"back_to_game_{game.chat_id}")]
    ]
    
    # Объединяем все кнопки
    keyboard = property_buttons + action_buttons
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_buy_house(update: Update, context: ContextTypes.DEFAULT_TYPE, game: Game, user_id: int):
    """Покупка дома"""
    player = game.players[user_id]
    
    buyable = []
    for prop in player.properties:
        if prop.can_buy_house() and prop.color not in ["railroad", "utility", "special"]:
            buyable.append(prop)
    
    if not buyable:
        await update.message.reply_text(
            "❌ Нет свойств для постройки дома!\n"
            "Нужно иметь всю цветовую группу и не более 4 домов.",
            reply_markup=get_game_keyboard()
        )
        return
    
    text = "🏠 *Выберите свойство для постройки дома:*\n\n"
    keyboard = []
    
    for prop in buyable:
        text += f"• *{prop.name}* - {prop.houses}/4 домов, цена: {prop.house_price}💰\n"
        keyboard.append([InlineKeyboardButton(prop.name, callback_data=f"house_{game.chat_id}_{prop.position}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Отмена", callback_data=f"cancel_{game.chat_id}")])
    
    sent_message = await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Сохраняем ID сообщения для последующего редактирования
    context.user_data['last_message_id'] = sent_message.message_id

async def handle_buy_hotel(update: Update, context: ContextTypes.DEFAULT_TYPE, game: Game, user_id: int):
    """Покупка отеля"""
    player = game.players[user_id]
    
    buyable = []
    for prop in player.properties:
        if prop.can_buy_hotel():
            buyable.append(prop)
    
    if not buyable:
        await update.message.reply_text(
            "❌ Нет свойств для постройки отеля!\n"
            "Нужно иметь 4 дома на свойстве.",
            reply_markup=get_game_keyboard()
        )
        return
    
    text = "🏨 *Выберите свойство для постройки отеля:*\n\n"
    keyboard = []
    
    for prop in buyable:
        text += f"• *{prop.name}* - цена: {prop.house_price}💰\n"
        keyboard.append([InlineKeyboardButton(prop.name, callback_data=f"hotel_{game.chat_id}_{prop.position}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Отмена", callback_data=f"cancel_{game.chat_id}")])
    
    sent_message = await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    context.user_data['last_message_id'] = sent_message.message_id

async def start_trade(update: Update, context: ContextTypes.DEFAULT_TYPE, game: Game, user_id: int):
    """Начало трейда"""
    player = game.players[user_id]
    
    others = [pid for pid in game.players.keys() if pid != user_id and game.players[pid].alive]
    
    if not others:
        await update.message.reply_text(
            "❌ Нет других игроков для обмена!",
            reply_markup=get_game_keyboard()
        )
        return
    
    text = "🔄 *Выберите игрока для обмена:*\n\n"
    keyboard = []
    
    for pid in others:
        p = game.players[pid]
        text += f"• @{p.username}\n"
        keyboard.append([InlineKeyboardButton(f"@{p.username}", callback_data=f"trade_select_{game.chat_id}_{pid}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Отмена", callback_data=f"cancel_{game.chat_id}")])
    
    sent_message = await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    context.user_data['last_message_id'] = sent_message.message_id

async def leave_game(update: Update, context: ContextTypes.DEFAULT_TYPE, game: Game, user_id: int):
    """Покинуть игру"""
    if user_id == game.creator_id:
        for pid in game.players.keys():
            try:
                await context.bot.send_message(
                    chat_id=pid,
                    text=f"🛑 Игра завершена создателем.",
                    reply_markup=get_main_keyboard()
                )
            except:
                pass
        if game.chat_id in games:
            del games[game.chat_id]
    else:
        player = game.players[user_id]
        player.alive = False
        
        await update.message.reply_text(
            f"👋 Вы покинули игру.",
            reply_markup=get_main_keyboard()
        )
        
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
            if game.chat_id in games:
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
        if game.chat_id in games:
            del games[game.chat_id]
        return

async def start_auction(game: Game, property_name: str, property_price: int, position: int, context: ContextTypes.DEFAULT_TYPE):
    """Начать аукцион"""
    game.auction = Auction(property_name, property_price, game.chat_id, position)
    
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
        
        if game.auction and game.auction.message_id:
            try:
                countdown_text = f"{game.auction.countdown}..."
                if game.auction.current_bidder:
                    current_bidder_text = f"@{game.players[game.auction.current_bidder].username}"
                else:
                    current_bidder_text = "никто"
                    
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
        if game.auction.current_bidder:
            winner = game.players[game.auction.current_bidder]
            prop = game.board[game.auction.position]
            
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

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if chat_id != user_id:
        await update.message.reply_text(
            "❌ Бот работает только в личных сообщениях!\n"
            "Напишите мне в личку: @MonopolyBot"
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
        "Классическая игра в монополию с друзьями.\n\n"
        "*Новые функции:*\n"
        "• 🏠 Дома и отели - увеличивают ренту\n"
        "• 🔄 Обмен карточками между игроками\n"
        "• ⚡ Коммуналки (электростанция/водопровод)\n"
        "• 🚂 Вокзалы с прогрессивной рентой\n"
        "• ⏱️ Таймер хода - 5 минут на ход\n\n"
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
                f"💰 У всех игроков по *1500*\n"
                f"⏱️ На ход дается 5 минут"
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
            
            # Запускаем таймер
            asyncio.create_task(check_turn_timer(game, context))
            
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
    
    keyboard = [
        [
            InlineKeyboardButton("▶️ Начать игру", callback_data=f"start_{chat_id}"),
            InlineKeyboardButton("❌ Отменить игру", callback_data=f"cancel_{chat_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
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
        if game_id in games:
            game = games[game_id]
            await query.edit_message_text("✅ Действие отменено")
    
    elif action == "back":
        game_id = int(data[2]) if len(data) > 2 else None
        if game_id and game_id in games:
            game = games[game_id]
            user_id = update.effective_user.id
            if user_id in game.players:
                await show_my_cards(update, context, game, user_id)
            else:
                await query.edit_message_text("🎮 Возврат в меню")
    
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
                
                try:
                    await context.bot.send_message(
                        chat_id=requester_id,
                        text=f"✅ Вы приняты в игру *#{game_id}*!\n"
                             f"Ожидайте начала игры.",
                        reply_markup=get_main_keyboard(),
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
            f"Первый ход: *@{game.players[game.current_turn].username}*\n\n"
            f"⏱️ На ход дается 5 минут"
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
        
        # Запускаем таймер
        asyncio.create_task(check_turn_timer(game, context))
        
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
        prop = game.board[position]
        
        if player.buy_property(prop):
            await query.edit_message_text(
                f"✅ Вы купили *{prop.name}* за *{prop.price}*💰",
                parse_mode=ParseMode.MARKDOWN
            )
            player.update_action_time()
            
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
        prop = game.board[position]
        
        await query.edit_message_text(
            f"🏠 Объявлен аукцион на *{prop.name}*!",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await start_auction(game, prop.name, prop.price, position, context)
    
    elif action == "house":
        game_id = int(data[1])
        position = int(data[2])
        
        if game_id not in games:
            await query.edit_message_text("❌ Игра больше не существует!")
            return
        
        game = games[game_id]
        user_id = update.effective_user.id
        player = game.players[user_id]
        prop = game.board[position]
        
        if prop.owner != player:
            await query.edit_message_text("❌ Это не ваша собственность!")
            return
        
        if player.buy_house(prop):
            await query.edit_message_text(
                f"✅ Вы построили дом на *{prop.name}*!\n"
                f"🏠 Теперь домов: {prop.houses}\n"
                f"💰 Новая аренда: *{prop.get_rent()}*",
                parse_mode=ParseMode.MARKDOWN
            )
            player.update_action_time()
            
            for pid in game.players.keys():
                if pid != user_id:
                    try:
                        await context.bot.send_message(
                            chat_id=pid,
                            text=f"🏠 *@{player.username}* построил дом на *{prop.name}*",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except:
                        pass
        else:
            await query.edit_message_text(
                f"❌ Недостаточно денег! Нужно: *{prop.house_price}*💰\n"
                f"Убедитесь что у вас вся цветовая группа",
                parse_mode=ParseMode.MARKDOWN
            )
    
    elif action == "hotel":
        game_id = int(data[1])
        position = int(data[2])
        
        if game_id not in games:
            await query.edit_message_text("❌ Игра больше не существует!")
            return
        
        game = games[game_id]
        user_id = update.effective_user.id
        player = game.players[user_id]
        prop = game.board[position]
        
        if prop.owner != player:
            await query.edit_message_text("❌ Это не ваша собственность!")
            return
        
        if player.buy_hotel(prop):
            await query.edit_message_text(
                f"✅ Вы построили отель на *{prop.name}*!\n"
                f"🏨 Отель построен!\n"
                f"💰 Новая аренда: *{prop.get_rent()}*",
                parse_mode=ParseMode.MARKDOWN
            )
            player.update_action_time()
            
            for pid in game.players.keys():
                if pid != user_id:
                    try:
                        await context.bot.send_message(
                            chat_id=pid,
                            text=f"🏨 *@{player.username}* построил отель на *{prop.name}*",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except:
                        pass
        else:
            await query.edit_message_text(
                f"❌ Недостаточно денег! Нужно: *{prop.house_price}*💰\n"
                f"Нужно 4 дома на свойстве",
                parse_mode=ParseMode.MARKDOWN
            )
    
    elif action == "manage_prop":
        game_id = int(data[1])
        position = int(data[2])
        
        if game_id not in games:
            await query.edit_message_text("❌ Игра больше не существует!")
            return
        
        game = games[game_id]
        user_id = update.effective_user.id
        player = game.players[user_id]
        prop = game.board[position]
        
        if prop.owner != player:
            await query.edit_message_text("❌ Это не ваша собственность!")
            return
        
        text = f"🏠 *Управление {prop.name}*\n\n"
        text += f"💰 Цена покупки: {prop.price}\n"
        text += f"🏠 Домов: {prop.houses}/4\n"
        text += f"🏨 Отель: {'Да' if prop.hotel else 'Нет'}\n"
        text += f"💰 Текущая аренда: {prop.get_rent()}\n"
        text += f"🏠 Цена дома: {prop.house_price}\n\n"
        
        keyboard = []
        if prop.can_buy_house():
            keyboard.append([InlineKeyboardButton(f"🏠 Купить дом ({prop.house_price}💰)", callback_data=f"house_{game_id}_{position}")])
        if prop.can_buy_hotel():
            keyboard.append([InlineKeyboardButton(f"🏨 Купить отель ({prop.house_price}💰)", callback_data=f"hotel_{game_id}_{position}")])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"back_to_cards_{game_id}")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif action == "show_houses":
        game_id = int(data[1])
        if game_id in games:
            game = games[game_id]
            user_id = update.effective_user.id
            await handle_buy_house(update, context, game, user_id)
    
    elif action == "show_hotels":
        game_id = int(data[1])
        if game_id in games:
            game = games[game_id]
            user_id = update.effective_user.id
            await handle_buy_hotel(update, context, game, user_id)
    
    elif action == "back_to_cards":
        game_id = int(data[1])
        if game_id in games:
            game = games[game_id]
            user_id = update.effective_user.id
            await show_my_cards(update, context, game, user_id)
    
    elif action == "trade":
        game_id = int(data[1])
        if game_id in games:
            game = games[game_id]
            user_id = update.effective_user.id
            await start_trade(update, context, game, user_id)
    
    elif action == "trade_select":
        game_id = int(data[1])
        target_id = int(data[2])
        
        if game_id not in games:
            await query.edit_message_text("❌ Игра больше не существует!")
            return
        
        game = games[game_id]
        proposer_id = update.effective_user.id
        
        trade_id = game.next_trade_id
        game.next_trade_id += 1
        
        trade = Trade(proposer_id, target_id, game_id)
        game.trades[trade_id] = trade
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Принять", callback_data=f"trade_accept_{game_id}_{trade_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"trade_decline_{game_id}_{trade_id}")
            ]
        ]
        
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🔄 *@{game.players[proposer_id].username}* хочет обменяться карточками!\n\n"
                 f"Нажмите 'Принять' чтобы начать обмен.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
        await query.edit_message_text(
            f"✅ Запрос на обмен отправлен *@{game.players[target_id].username}*",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif action == "trade_accept":
        game_id = int(data[1])
        trade_id = int(data[2])
        
        if game_id not in games or trade_id not in games[game_id].trades:
            await query.edit_message_text("❌ Трейд больше не существует!")
            return
        
        game = games[game_id]
        trade = game.trades[trade_id]
        
        # Здесь будет логика трейда
        await query.edit_message_text(
            "🔄 *Функция трейда в разработке*\n\n"
            "Выберите карточки для обмена...",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif action == "trade_decline":
        game_id = int(data[1])
        trade_id = int(data[2])
        
        if game_id in games and trade_id in games[game_id].trades:
            del games[game_id].trades[trade_id]
        
        await query.edit_message_text("❌ Трейд отклонен")

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
            "🎮 *Игровые кнопки:*\n"
            "• 🎲 Бросить кости - сделать ход\n"
            "• 🏠 Мои карты - посмотреть собственность\n"
            "  → Нажмите на карточку для управления\n"
            "  → 🏠 Купить дом (после всей группы)\n"
            "  → 🏨 Купить отель (после 4 домов)\n"
            "• 💬 Чат - написать в игровой чат\n"
            "• 🚪 Покинуть игру - выйти из игры\n\n"
            "⏱️ *Таймер:*\n"
            "• На ход дается 5 минут\n"
            "• За 1 минуту до конца придет предупреждение\n"
            "• Если не сделать ход - исключение из игры",
            reply_markup=get_game_keyboard()
        )
        return
    
    help_text = (
        "🎲 *Monopoly Bot - Помощь*\n\n"
        "*Основные кнопки:*\n"
        "• 🎮 Создать игру - новая игра\n"
        "• 📋 Список игр - активные игры\n"
        "• ▶️ Начать игру - старт вашей игры\n"
        "• ❓ Помощь - это меню\n"
        "• ℹ️ О боте - информация\n\n"
        "*Новые функции:*\n"
        "🏠 *Дома и отели*\n"
        "• Можно купить после всей цветовой группы\n"
        "• Дом: 50-200💰 (в зависимости от цвета)\n"
        "• Отель: цена дома (после 4 домов)\n"
        "• Рента увеличивается с каждым домом\n\n"
        "🔄 *Обмен карточками*\n"
        "• В меню 'Мои карты' нажмите 'Предложить обмен'\n"
        "• Выберите игрока и предложите карты/деньги\n\n"
        "⚡ *Коммуналки*\n"
        "• Электростанция и Водопровод\n"
        "• Рента = сумма кубиков × 4 (1 коммуналка)\n"
        "• Рента = сумма кубиков × 10 (2 коммуналки)\n\n"
        "🚂 *Вокзалы*\n"
        "• Рента: 25, 50, 100, 200 (за 1-4 вокзала)\n\n"
        "⏱️ *Таймер хода:*\n"
        "• 5 минут на ход\n"
        "• Предупреждение за 1 минуту\n"
        "• Исключение при бездействии\n\n"
        "*Правила:*\n"
        "• В игре участвуют 2-6 игроков\n"
        "• Каждый получает 1500 в начале\n"
        "• Цель - стать последним выжившим\n"
        "• Проходя Старт, получаете 200\n"
        "• 3 дубля подряд = в тюрьму"
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
        "*Monopoly Bot v5.0*\n\n"
        "*Особенности:*\n"
        "• Полное поле Monopoly (40 клеток)\n"
        "• До *6 игроков* в одной игре\n"
        "• Система запросов на вступление\n"
        "• Покупка недвижимости\n"
        "• *Дома и отели* 🏠🏨\n"
        "• *Обмен карточками* 🔄\n"
        "• *Аукционы* с шагом 1💰\n"
        "• *Коммуналки* ⚡ (электро/вода)\n"
        "• *Вокзалы* 🚂 с прогрессивной рентой\n"
        "• *Таймер хода* ⏱️ (5 минут)\n"
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
    print("🚀 Запуск Monopoly Bot v5.0...")
    print(f"✅ Токен загружен")
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("✅ Веб-сервер Flask запущен на порту 8080")
    
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("create", create_game))
    application.add_handler(CommandHandler("join", join_game))
    application.add_handler(CommandHandler("games", list_games_command))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)

    print("✅ Бот успешно запущен и готов к работе!")
    print("🤖 Ожидание сообщений...")
    application.run_polling()

if __name__ == '__main__':
    main()
