import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import random
import json
import os
from datetime import datetime, timedelta

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8572906701:AAFpWLGbEZqvZsupPZqElr0q197f3WllvYU"  # Ваш токен
ADMIN_ID = 5596589260  # Ваш ID

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Файл для хранения данных
DATA_FILE = 'rpg_bot_data.json'

# ==================== КЛАСС ДЛЯ РАБОТЫ С ДАННЫМИ ====================
class GameDatabase:
    def __init__(self):
        self.users = {}
        self.businesses_data = {
            'farm': {'name': '🌾 Ферма', 'cost': 1000, 'income': 100, 'cooldown': 3600, 'level_req': 1, 'description': 'Приносит 100 монет в час'},
            'mine': {'name': '⛏ Шахта', 'cost': 5000, 'income': 500, 'cooldown': 7200, 'level_req': 3, 'description': 'Приносит 500 монет за 2 часа'},
            'factory': {'name': '🏭 Завод', 'cost': 15000, 'income': 2000, 'cooldown': 21600, 'level_req': 5, 'description': 'Приносит 2000 монет за 6 часов'},
            'casino': {'name': '🎰 Казино', 'cost': 50000, 'income': 10000, 'cooldown': 86400, 'level_req': 10, 'description': 'Приносит 10000 монет в день'}
        }
        self.load_data()
    
    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.users = data.get('users', {})
            except Exception as e:
                logger.error(f"Ошибка загрузки данных: {e}")
                self.users = {}
        else:
            self.users = {}
    
    def save_data(self):
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump({'users': self.users}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения данных: {e}")
    
    def get_user(self, user_id):
        user_id = str(user_id)
        if user_id not in self.users:
            self.users[user_id] = {
                'balance': 1000,
                'bank': 0,
                'inventory': {},
                'businesses': {},
                'last_work': None,
                'level': 1,
                'exp': 0,
                'daily_streak': 0,
                'last_daily': None,
                'total_earned': 0,
                'total_spent': 0,
                'games_won': 0,
                'games_lost': 0,
                'referrals': [],
                'achievements': []
            }
            self.save_data()
        return self.users[user_id]
    
    def update_balance(self, user_id, amount):
        user_id = str(user_id)
        if user_id in self.users:
            self.users[user_id]['balance'] += amount
            if amount > 0:
                self.users[user_id]['total_earned'] += amount
            else:
                self.users[user_id]['total_spent'] -= amount
            self.save_data()
            return True
        return False
    
    def add_exp(self, user_id, amount):
        user_id = str(user_id)
        if user_id in self.users:
            self.users[user_id]['exp'] += amount
            while self.users[user_id]['exp'] >= self.users[user_id]['level'] * 100:
                self.users[user_id]['exp'] -= self.users[user_id]['level'] * 100
                self.users[user_id]['level'] += 1
            self.save_data()
            return True
        return False

# Инициализация базы данных
db = GameDatabase()

# ==================== МИНИ-ИГРЫ ====================
class MiniGames:
    @staticmethod
    def roll_dice(bet):
        player_roll = random.randint(1, 6)
        bot_roll = random.randint(1, 6)
        
        if player_roll > bot_roll:
            win_amount = bet * 2
            return f"🎲 Ты выкинул: {player_roll}\n🤖 Бот выкинул: {bot_roll}\n\n✅ Ты выиграл {win_amount} монет!", win_amount, True
        elif player_roll < bot_roll:
            return f"🎲 Ты выкинул: {player_roll}\n🤖 Бот выкинул: {bot_roll}\n\n❌ Ты проиграл {bet} монет!", -bet, False
        else:
            return f"🎲 Ты выкинул: {player_roll}\n🤖 Бот выкинул: {bot_roll}\n\n🤝 Ничья! Возврат ставки.", 0, False
    
    @staticmethod
    def coin_flip(bet, choice):
        result = random.choice(['heads', 'tails'])
        
        if choice == result:
            win_amount = bet * 2
            return f"🪙 Выпало: {result}\n✅ Ты угадал! Выигрыш: {win_amount} монет!", win_amount, True
        else:
            return f"🪙 Выпало: {result}\n❌ Ты не угадал! Потеряно: {bet} монет!", -bet, False
    
    @staticmethod
    def slots(bet):
        symbols = ['🍒', '🍋', '🍊', '🍇', '💎', '7️⃣']
        results = [random.choice(symbols) for _ in range(3)]
        
        if results[0] == results[1] == results[2]:
            multiplier = 5 if results[0] == '7️⃣' else 3
            win_amount = bet * multiplier
            return f"{' '.join(results)}\n\n🎉 ДЖЕКПОТ! x{multiplier}\nВыигрыш: {win_amount} монет!", win_amount, True
        elif results[0] == results[1] or results[1] == results[2] or results[0] == results[2]:
            win_amount = bet * 2
            return f"{' '.join(results)}\n\n🎊 Две одинаковые! x2\nВыигрыш: {win_amount} монет!", win_amount, True
        else:
            return f"{' '.join(results)}\n\n💔 Ничего... Потеряно: {bet} монет!", -bet, False

# ==================== ФУНКЦИИ ДЛЯ СОЗДАНИЯ КЛАВИАТУР ====================

def get_main_keyboard():
    """Главное меню с инлайн кнопками"""
    keyboard = [
        [InlineKeyboardButton("📊 ПРОФИЛЬ", callback_data="profile"),
         InlineKeyboardButton("💰 РАБОТА", callback_data="work")],
        [InlineKeyboardButton("🏪 БИЗНЕС", callback_data="business_menu"),
         InlineKeyboardButton("🎰 КАЗИНО", callback_data="casino_menu")],
        [InlineKeyboardButton("💸 ПЕРЕВОД", callback_data="transfer_menu"),
         InlineKeyboardButton("🏆 ТОП", callback_data="top")],
        [InlineKeyboardButton("🎁 ЕЖЕДНЕВНЫЙ БОНУС", callback_data="daily"),
         InlineKeyboardButton("❓ ПОМОЩЬ", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard():
    """Кнопка назад"""
    keyboard = [[InlineKeyboardButton("🔙 НАЗАД В МЕНЮ", callback_data="main_menu")]]
    return InlineKeyboardMarkup(keyboard)

def get_casino_keyboard():
    """Меню казино"""
    keyboard = [
        [InlineKeyboardButton("🎲 Кости", callback_data="game_dice"),
         InlineKeyboardButton("🪙 Орёл/Решка", callback_data="game_coin")],
        [InlineKeyboardButton("🎰 Слоты", callback_data="game_slots"),
         InlineKeyboardButton("📊 Статистика", callback_data="game_stats")],
        [InlineKeyboardButton("🔙 В ГЛАВНОЕ МЕНЮ", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_business_keyboard(user_data):
    """Меню бизнеса"""
    keyboard = []
    
    # Кнопки для покупки бизнеса
    for biz_id, biz_data in db.businesses_data.items():
        if biz_id not in user_data['businesses'] and user_data['level'] >= biz_data['level_req']:
            keyboard.append([InlineKeyboardButton(
                f"🏪 Купить {biz_data['name']} ({biz_data['cost']}💰)",
                callback_data=f"buy_{biz_id}"
            )])
    
    # Кнопка для сбора дохода
    if user_data['businesses']:
        keyboard.append([InlineKeyboardButton("💰 СОБРАТЬ ДОХОД", callback_data="collect_business")])
    
    keyboard.append([InlineKeyboardButton("🔙 В ГЛАВНОЕ МЕНЮ", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

# ==================== ОБРАБОТЧИКИ КОМАНД ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start - главное меню"""
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    welcome_text = f"""
🌟 ДОБРО ПОЖАЛОВАТЬ В RPG БИЗНЕС ИМПЕРИЮ! 🌟

👤 Игрок: {user.first_name}
💰 Баланс: {user_data['balance']} монет
📊 Уровень: {user_data['level']}

═══════════════════════
📌 ИСПОЛЬЗУЙ КНОПКИ НИЖЕ
═══════════════════════
"""
    
    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard())

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать профиль"""
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    total_games = user_data['games_won'] + user_data['games_lost']
    win_rate = (user_data['games_won'] / total_games * 100) if total_games > 0 else 0
    
    # Считаем стоимость бизнесов
    business_value = 0
    for biz_id in user_data['businesses']:
        if biz_id in db.businesses_data:
            business_value += db.businesses_data[biz_id]['cost']
    
    profile_text = f"""
👤 ПРОФИЛЬ ИГРОКА
═══════════════════════
🆔 ID: {user.id}
📛 Имя: {user.first_name}

💰 БАЛАНС: {user_data['balance']} монет
🏦 В банке: {user_data['bank']} монет
💎 Всего активов: {user_data['balance'] + user_data['bank'] + business_value} монет

📊 ПРОГРЕСС
═══════════════════════
⭐ Уровень: {user_data['level']}
✨ Опыт: {user_data['exp']}/{user_data['level'] * 100}
🏪 Бизнесов: {len(user_data['businesses'])}
📦 Предметов: {sum(user_data['inventory'].values())}

📈 СТАТИСТИКА
═══════════════════════
💵 Всего заработано: {user_data['total_earned']}
💸 Всего потрачено: {user_data['total_spent']}
🎮 Игр сыграно: {total_games}
├ Побед: {user_data['games_won']}
├ Поражений: {user_data['games_lost']}
└ Винрейт: {win_rate:.1f}%
🔥 Дней подряд: {user_data['daily_streak']}
"""
    
    await update.message.reply_text(profile_text, reply_markup=get_back_keyboard())

async def work_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /work - работа"""
    user_id = update.effective_user.id
    user_data = db.get_user(user_id)
    
    # Проверка кулдауна
    if user_data['last_work']:
        last_work = datetime.fromisoformat(user_data['last_work'])
        time_diff = datetime.now() - last_work
        if time_diff.total_seconds() < 3600:  # 1 час
            remaining = 3600 - int(time_diff.total_seconds())
            minutes = remaining // 60
            seconds = remaining % 60
            
            await update.message.reply_text(
                f"⏰ ТЫ УЖЕ РАБОТАЛ!\n"
                f"═══════════════════════\n"
                f"Отдохни ещё:\n"
                f"⏳ {minutes} мин {seconds} сек\n\n"
                f"💡 Совет: Зарабатывай на бизнесе!",
                reply_markup=get_back_keyboard()
            )
            return
    
    # Случайная работа
    jobs = [
        ("👨‍💻 Программист", random.randint(300, 600), "Написал крутой сайт"),
        ("👷 Строитель", random.randint(250, 450), "Построил дом"),
        ("🚚 Водитель", random.randint(200, 400), "Доставил груз"),
        ("👨‍🏫 Учитель", random.randint(150, 300), "Провёл урок"),
        ("👨‍🍳 Повар", random.randint(200, 350), "Приготовил ужин"),
        ("👨‍🎨 Художник", random.randint(100, 800), "Нарисовал картину"),
        ("👨‍✈️ Пилот", random.randint(500, 1000), "Совершил рейс"),
        ("👨‍⚕️ Врач", random.randint(400, 700), "Вылечил пациентов")
    ]
    
    job, salary, action = random.choice(jobs)
    
    # Обновление данных
    db.update_balance(user_id, salary)
    db.add_exp(user_id, salary // 10)
    user_data = db.get_user(user_id)
    user_data['last_work'] = datetime.now().isoformat()
    db.save_data()
    
    await update.message.reply_text(
        f"💼 РАБОТА ВЫПОЛНЕНА!\n"
        f"═══════════════════════\n"
        f"Профессия: {job}\n"
        f"Действие: {action}\n\n"
        f"💰 Заработано: +{salary} монет\n"
        f"⭐ Опыт: +{salary // 10}\n"
        f"═══════════════════════\n"
        f"💰 Текущий баланс: {user_data['balance']} монет",
        reply_markup=get_back_keyboard()
    )

async def casino_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню казино"""
    user_id = update.effective_user.id
    user_data = db.get_user(user_id)
    
    text = f"""
🎰 КАЗИНО И ИГРЫ
═══════════════════════
💰 Твой баланс: {user_data['balance']} монет

Выбери игру:
"""
    await update.message.reply_text(text, reply_markup=get_casino_keyboard())

async def business_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню бизнеса"""
    user_id = update.effective_user.id
    user_data = db.get_user(user_id)
    
    text = f"""
🏪 УПРАВЛЕНИЕ БИЗНЕСОМ
═══════════════════════
💰 Баланс: {user_data['balance']} монет
📊 Уровень: {user_data['level']}

🏢 ТВОЙ БИЗНЕС:
═══════════════════════
"""
    
    if user_data['businesses']:
        for biz_id in user_data['businesses']:
            if biz_id in db.businesses_data:
                biz_info = db.businesses_data[biz_id]
                text += f"✅ {biz_info['name']} - {biz_info['income']}💰/час\n"
    else:
        text += "❌ У тебя пока нет бизнеса\n"
    
    text += "\n🏪 ДОСТУПНО ДЛЯ ПОКУПКИ:\n"
    
    for biz_id, biz_data in db.businesses_data.items():
        if biz_id not in user_data['businesses']:
            status = "✅" if user_data['level'] >= biz_data['level_req'] else "❌"
            text += f"\n{status} {biz_data['name']}\n"
            text += f"├ Цена: {biz_data['cost']}💰\n"
            text += f"├ Доход: {biz_data['income']}💰/час\n"
            text += f"└ Треб. уровень: {biz_data['level_req']}\n"
    
    await update.message.reply_text(text, reply_markup=get_business_keyboard(user_data))

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Топ игроков"""
    # Сортировка пользователей по балансу
    top_users = []
    for user_id, data in db.users.items():
        top_users.append({
            'id': user_id,
            'balance': data['balance'],
            'level': data['level'],
            'businesses': len(data['businesses'])
        })
    
    top_users.sort(key=lambda x: x['balance'], reverse=True)
    top_users = top_users[:10]
    
    text = "🏆 ТОП 10 ИГРОКОВ 🏆\n═══════════════════════\n\n"
    
    for i, user in enumerate(top_users, 1):
        try:
            user_info = await context.bot.get_chat(int(user['id']))
            name = user_info.first_name
        except:
            name = f"ID: {user['id']}"
        
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "👤"
        text += f"{medal} {i}. {name}\n"
        text += f"   ├ 💰 {user['balance']} монет\n"
        text += f"   ├ ⭐ Уровень {user['level']}\n"
        text += f"   └ 🏪 Бизнесов: {user['businesses']}\n\n"
    
    await update.message.reply_text(text, reply_markup=get_back_keyboard())

async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ежедневный бонус"""
    user_id = update.effective_user.id
    user_data = db.get_user(user_id)
    
    now = datetime.now()
    
    if user_data['last_daily']:
        last_daily = datetime.fromisoformat(user_data['last_daily'])
        if last_daily.date() == now.date():
            next_daily = last_daily + timedelta(days=1)
            time_until = next_daily - now
            hours = time_until.seconds // 3600
            minutes = (time_until.seconds % 3600) // 60
            await update.message.reply_text(
                f"⏰ БОНУС УЖЕ ПОЛУЧЕН!\n"
                f"═══════════════════════\n"
                f"Следующий через:\n"
                f"⏳ {hours} ч {minutes} мин",
                reply_markup=get_back_keyboard()
            )
            return
    
    # Расчет бонуса
    if user_data['last_daily']:
        last_daily = datetime.fromisoformat(user_data['last_daily'])
        if (now - last_daily).days <= 1:
            user_data['daily_streak'] += 1
        else:
            user_data['daily_streak'] = 1
    else:
        user_data['daily_streak'] = 1
    
    # Базовый бонус + бонус за streak
    base_bonus = 500
    streak_bonus = user_data['daily_streak'] * 50
    total_bonus = base_bonus + streak_bonus
    
    db.update_balance(user_id, total_bonus)
    user_data['last_daily'] = now.isoformat()
    db.save_data()
    
    await update.message.reply_text(
        f"🎁 ЕЖЕДНЕВНЫЙ БОНУС!\n"
        f"═══════════════════════\n"
        f"💰 База: +{base_bonus}\n"
        f"🔥 Streak x{user_data['daily_streak']}: +{streak_bonus}\n"
        f"📦 ВСЕГО: +{total_bonus} монет\n"
        f"═══════════════════════\n"
        f"💰 Текущий баланс: {user_data['balance']}",
        reply_markup=get_back_keyboard()
    )

async def transfer_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню перевода"""
    user_id = update.effective_user.id
    user_data = db.get_user(user_id)
    
    await update.message.reply_text(
        f"💸 ПЕРЕВОД ДЕНЕГ\n"
        f"═══════════════════════\n"
        f"💰 Твой баланс: {user_data['balance']} монет\n\n"
        f"📝 Используй команду:\n"
        f"`/transfer ID СУММА`\n\n"
        f"Пример: `/transfer 5596589260 500`\n\n"
        f"💡 ID игрока можно узнать в его профиле",
        parse_mode='Markdown',
        reply_markup=get_back_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь"""
    text = """
❓ ПОМОЩЬ ПО ИГРЕ
═══════════════════════

📋 ОСНОВНЫЕ КОМАНДЫ:
═══════════════════════
💰 /work - Заработать деньги (1 раз в час)
🏪 /business - Купить и управлять бизнесом
🎰 /casino - Сыграть в казино
💸 /transfer - Перевести деньги другому игроку
🎁 /daily - Получить ежедневный бонус
🏆 /top - Топ богатейших игроков

🎮 КАЗИНО:
═══════════════════════
🎲 Кости - угадай, кто выкинет больше
🪙 Орёл/Решка - 50/50 шанс
🎰 Слоты - собери комбинации

🏪 БИЗНЕС:
═══════════════════════
Покупай бизнес и получай пассивный доход!
Чем выше уровень - тем больше доступно бизнесов

📊 УРОВНИ:
═══════════════════════
Опыт даётся за работу и игры
100 опыта = 1 уровень
С каждым уровнем открывается новый бизнес

👑 АДМИН:
═══════════════════════
/addmoney ID СУММА - выдать деньги (только админ)
"""
    await update.message.reply_text(text, reply_markup=get_back_keyboard())

# ==================== ОБРАБОТЧИК КНОПОК ====================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на инлайн кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = db.get_user(user_id)
    
    # Главное меню
    if query.data == "main_menu":
        text = f"""
🌟 ГЛАВНОЕ МЕНЮ
═══════════════════════
👤 Игрок: {query.from_user.first_name}
💰 Баланс: {user_data['balance']} монет
📊 Уровень: {user_data['level']}
"""
        await query.edit_message_text(text, reply_markup=get_main_keyboard())
    
    # Профиль
    elif query.data == "profile":
        total_games = user_data['games_won'] + user_data['games_lost']
        win_rate = (user_data['games_won'] / total_games * 100) if total_games > 0 else 0
        
        business_value = 0
        for biz_id in user_data['businesses']:
            if biz_id in db.businesses_data:
                business_value += db.businesses_data[biz_id]['cost']
        
        text = f"""
👤 ПРОФИЛЬ ИГРОКА
═══════════════════════
🆔 ID: {user_id}
📛 Имя: {query.from_user.first_name}

💰 БАЛАНС: {user_data['balance']} монет
💎 Всего активов: {user_data['balance'] + business_value} монет

📊 ПРОГРЕСС
═══════════════════════
⭐ Уровень: {user_data['level']}
✨ Опыт: {user_data['exp']}/{user_data['level'] * 100}
🏪 Бизнесов: {len(user_data['businesses'])}
🔥 Дней подряд: {user_data['daily_streak']}

📈 СТАТИСТИКА
═══════════════════════
🎮 Игр: {total_games} (Винрейт: {win_rate:.1f}%)
"""
        await query.edit_message_text(text, reply_markup=get_back_keyboard())
    
    # Работа
    elif query.data == "work":
        await work_command(update, context)
        await query.delete()
    
    # Меню бизнеса
    elif query.data == "business_menu":
        text = f"""
🏪 УПРАВЛЕНИЕ БИЗНЕСОМ
═══════════════════════
💰 Баланс: {user_data['balance']} монет
📊 Уровень: {user_data['level']}

🏢 ТВОЙ БИЗНЕС:
═══════════════════════
"""
        if user_data['businesses']:
            for biz_id in user_data['businesses']:
                if biz_id in db.businesses_data:
                    biz_info = db.businesses_data[biz_id]
                    text += f"✅ {biz_info['name']} - {biz_info['income']}💰/час\n"
        else:
            text += "❌ У тебя пока нет бизнеса\n"
        
        await query.edit_message_text(text, reply_markup=get_business_keyboard(user_data))
    
    # Меню казино
    elif query.data == "casino_menu":
        text = f"""
🎰 КАЗИНО
═══════════════════════
💰 Баланс: {user_data['balance']} монет
"""
        await query.edit_message_text(text, reply_markup=get_casino_keyboard())
    
    # Меню перевода
    elif query.data == "transfer_menu":
        await query.edit_message_text(
            f"💸 ПЕРЕВОД ДЕНЕГ\n"
            f"═══════════════════════\n"
            f"💰 Твой баланс: {user_data['balance']} монет\n\n"
            f"📝 Используй команду:\n"
            f"`/transfer ID СУММА`\n\n"
            f"Пример: `/transfer 5596589260 500`",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )
    
    # Топ
    elif query.data == "top":
        top_users = []
        for uid, data in db.users.items():
            top_users.append({
                'id': uid,
                'balance': data['balance'],
                'level': data['level'],
                'businesses': len(data['businesses'])
            })
        
        top_users.sort(key=lambda x: x['balance'], reverse=True)
        top_users = top_users[:10]
        
        text = "🏆 ТОП 10 ИГРОКОВ 🏆\n═══════════════════════\n\n"
        
        for i, user in enumerate(top_users, 1):
            try:
                user_info = await context.bot.get_chat(int(user['id']))
                name = user_info.first_name
            except:
                name = f"ID: {user['id']}"
            
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "👤"
            text += f"{medal} {i}. {name}\n"
            text += f"   ├ 💰 {user['balance']} монет\n"
            text += f"   └ ⭐ Уровень {user['level']}\n\n"
        
        await query.edit_message_text(text, reply_markup=get_back_keyboard())
    
    # Ежедневный бонус
    elif query.data == "daily":
        await daily_command(update, context)
        await query.delete()
    
    # Помощь
    elif query.data == "help":
        text = """
❓ ПОМОЩЬ
═══════════════════════
💰 /work - Заработать
🏪 /business - Бизнес
🎰 /casino - Казино
💸 /transfer - Перевод
🎁 /daily - Бонус
🏆 /top - Топ игроков

🎮 ИГРЫ:
🎲 Кости - кто больше
🪙 Орёл/Решка - 50/50
🎰 Слоты - собери 3
"""
        await query.edit_message_text(text, reply_markup=get_back_keyboard())
    
    # Покупка бизнеса
    elif query.data.startswith("buy_"):
        biz_id = query.data.replace("buy_", "")
        biz_data = db.businesses_data.get(biz_id)
        
        if biz_data:
            if user_data['balance'] >= biz_data['cost']:
                if user_data['level'] >= biz_data['level_req']:
                    db.update_balance(user_id, -biz_data['cost'])
                    user_data['businesses'][biz_id] = {'last_collected': datetime.now().isoformat()}
                    db.save_data()
                    
                    await query.edit_message_text(
                        f"✅ ПОЗДРАВЛЯЮ!\n"
                        f"═══════════════════════\n"
                        f"Ты купил {biz_data['name']}!\n\n"
                        f"💰 Доход: {biz_data['income']}💰/час\n"
                        f"💵 Остаток: {user_data['balance']}💰",
                        reply_markup=get_back_keyboard()
                    )
                else:
                    await query.edit_message_text(
                        f"❌ НЕДОСТАТОЧНО УРОВНЯ!\n"
                        f"═══════════════════════\n"
                        f"Нужно: {biz_data['level_req']} уровень\n"
                        f"У тебя: {user_data['level']} уровень",
                        reply_markup=get_back_keyboard()
                    )
            else:
                await query.edit_message_text(
                    f"❌ НЕДОСТАТОЧНО СРЕДСТВ!\n"
                    f"═══════════════════════\n"
                    f"Нужно: {biz_data['cost']}💰\n"
                    f"У тебя: {user_data['balance']}💰",
                    reply_markup=get_back_keyboard()
                )
    
    # Сбор дохода с бизнеса
    elif query.data == "collect_business":
        total_income = 0
        now = datetime.now()
        
        for biz_id, biz_data in user_data['businesses'].items():
            if biz_id in db.businesses_data:
                last_collected = datetime.fromisoformat(biz_data['last_collected'])
                biz_info = db.businesses_data[biz_id]
                
                time_passed = (now - last_collected).total_seconds()
                collections = int(time_passed // biz_info['cooldown'])
                
                if collections > 0:
                    income = biz_info['income'] * collections
                    total_income += income
                    biz_data['last_collected'] = now.isoformat()
        
        if total_income > 0:
            db.update_balance(user_id, total_income)
            db.save_data()
            await query.edit_message_text(
                f"💰 ДОХОД ПОЛУЧЕН!\n"
                f"═══════════════════════\n"
                f"Собрано: +{total_income}💰\n\n"
                f"💰 Новый баланс: {user_data['balance']}💰",
                reply_markup=get_back_keyboard()
            )
        else:
            await query.edit_message_text(
                f"⏰ ЕЩЁ РАНО!\n"
                f"═══════════════════════\n"
                f"Доход ещё не накоплен.\n"
                f"Зайди позже!",
                reply_markup=get_back_keyboard()
            )
    
    # Игры казино
    elif query.data.startswith("game_"):
        game = query.data.replace("game_", "")
        context.user_data['current_game'] = game
        context.user_data['game_state'] = 'waiting_bet'
        
        await query.edit_message_text(
            f"🎮 {game.upper()}\n"
            f"═══════════════════════\n"
            f"💰 Твой баланс: {user_data['balance']}💰\n\n"
            f"💬 Введи сумму ставки:"
        )

# ==================== ОБРАБОТЧИК СООБЩЕНИЙ ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user_id = update.effective_user.id
    user_data = db.get_user(user_id)
    
    # Обработка ставок для игр
    if 'current_game' in context.user_data and context.user_data.get('game_state') == 'waiting_bet':
        try:
            bet = int(update.message.text)
            if bet <= 0:
                await update.message.reply_text("❌ Ставка должна быть положительной!")
                return
            
            if bet > user_data['balance']:
                await update.message.reply_text(
                    f"❌ Недостаточно средств!\n"
                    f"💰 Твой баланс: {user_data['balance']}",
                    reply_markup=get_back_keyboard()
                )
                return
            
            game = context.user_data['current_game']
            
            # Списываем ставку
            db.update_balance(user_id, -bet)
            
            if game == 'dice':
                result, amount, won = MiniGames.roll_dice(bet)
            elif game == 'slots':
                result, amount, won = MiniGames.slots(bet)
            elif game == 'coin':
                await update.message.reply_text("🎮 Выбери: орёл или решка?")
                context.user_data['game_state'] = 'waiting_choice'
                context.user_data['bet'] = bet
                return
            
            # Обновляем баланс
            if amount != 0:
                db.update_balance(user_id, amount)
                if amount > 0:
                    user_data['games_won'] += 1
                else:
                    user_data['games_lost'] += 1
                db.save_data()
            
            user_data = db.get_user(user_id)
            await update.message.reply_text(
                f"{result}\n\n💰 Текущий баланс: {user_data['balance']}",
                reply_markup=get_main_keyboard()
            )
            
            # Очищаем состояние
            del context.user_data['current_game']
            del context.user_data['game_state']
            
        except ValueError:
            await update.message.reply_text("❌ Введи число!", reply_markup=get_back_keyboard())
    
    # Обработка выбора орёл/решка
    elif context.user_data.get('game_state') == 'waiting_choice':
        choice = update.message.text.lower()
        if choice in ['орёл', 'орел', 'решка', 'heads', 'tails']:
            bet = context.user_data['bet']
            game_choice = 'heads' if choice in ['орёл', 'орел', 'heads'] else 'tails'
            
            result, amount, won = MiniGames.coin_flip(bet, game_choice)
            db.update_balance(user_id, amount)
            
            if amount > 0:
                user_data['games_won'] += 1
            elif amount < 0:
                user_data['games_lost'] += 1
            db.save_data()
            
            user_data = db.get_user(user_id)
            await update.message.reply_text(
                f"{result}\n\n💰 Текущий баланс: {user_data['balance']}",
                reply_markup=get_main_keyboard()
            )
            
            del context.user_data['current_game']
            del context.user_data['game_state']
            del context.user_data['bet']
        else:
            await update.message.reply_text("❌ Введи 'орёл' или 'решка'!")

# ==================== АДМИН КОМАНДЫ ====================

async def addmoney_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ команда для выдачи денег"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ У тебя нет прав администратора!")
        return
    
    try:
        args = context.args
        if len(args) != 2:
            await update.message.reply_text("❌ Использование: /addmoney ID СУММА")
            return
        
        target_id = int(args[0])
        amount = int(args[1])
        
        db.get_user(target_id)
        db.update_balance(target_id, amount)
        user_data = db.get_user(target_id)
        
        await update.message.reply_text(
            f"✅ АДМИН ДЕЙСТВИЕ\n"
            f"═══════════════════════\n"
            f"Выдано: +{amount}💰\n"
            f"Пользователю: {target_id}\n"
            f"💰 Новый баланс: {user_data['balance']}💰"
        )
    except ValueError:
        await update.message.reply_text("❌ Сумма должна быть числом!")

async def transfer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда перевода"""
    try:
        args = context.args
        if len(args) != 2:
            await update.message.reply_text(
                "❌ Неправильный формат!\n"
                "Использование: /transfer ID СУММА\n"
                "Пример: /transfer 5596589260 500",
                reply_markup=get_back_keyboard()
            )
            return
        
        to_id = int(args[0])
        amount = int(args[1])
        from_id = update.effective_user.id
        
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть положительной!")
            return
        
        from_data = db.get_user(from_id)
        
        if from_data['balance'] < amount:
            await update.message.reply_text(
                f"❌ Недостаточно средств!\n"
                f"💰 Твой баланс: {from_data['balance']}",
                reply_markup=get_back_keyboard()
            )
            return
        
        if db.transfer_money(from_id, to_id, amount):
            await update.message.reply_text(
                f"✅ ПЕРЕВОД ВЫПОЛНЕН!\n"
                f"═══════════════════════\n"
                f"💰 Сумма: {amount} монет\n"
                f"👤 Получатель: {to_id}\n"
                f"📊 Твой баланс: {from_data['balance'] - amount}",
                reply_markup=get_main_keyboard()
            )
            
            try:
                await context.bot.send_message(
                    to_id,
                    f"💰 ВАМ ПЕРЕВЕЛИ ДЕНЬГИ!\n"
                    f"═══════════════════════\n"
                    f"Сумма: +{amount} монет\n"
                    f"От: {from_id}"
                )
            except:
                pass
        else:
            await update.message.reply_text("❌ Ошибка перевода! Проверь ID получателя.")
    except ValueError:
        await update.message.reply_text("❌ Сумма должна быть числом!")

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================

def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("work", work_command))
    application.add_handler(CommandHandler("casino", casino_menu))
    application.add_handler(CommandHandler("business", business_menu))
    application.add_handler(CommandHandler("top", top_command))
    application.add_handler(CommandHandler("daily", daily_command))
    application.add_handler(CommandHandler("transfer", transfer_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("addmoney", addmoney_command))
    
    # Регистрируем обработчик колбэков
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Регистрируем обработчик сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 БОТ ЗАПУЩЕН!")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print(f"📁 Файл данных: {DATA_FILE}")
    print("✅ Нажми Ctrl+C для остановки")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
