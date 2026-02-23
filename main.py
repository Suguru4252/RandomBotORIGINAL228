import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import random
import json
import os
from datetime import datetime, timedelta
import asyncio

# ==================== НАСТРОЙКИ ====================
# ⚠️ ВСТАВЬТЕ СЮДА НОВЫЙ ТОКЕН (после отзыва старого)
BOT_TOKEN = "8572906701:AAFpWLGbEZqvZsupPZqElr0q197f3WllvYU"  # ЗАМЕНИТЕ НА НОВЫЙ!
ADMIN_ID = 5596589260  # Ваш ID (главный админ)

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
        self.games = {}  # Активные игры
        self.market = {}  # Рынок сырья
        self.load_data()
    
    def load_data(self):
        """Загрузка данных из файла"""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.users = data.get('users', {})
                    self.market = data.get('market', self.init_market())
            except Exception as e:
                logger.error(f"Ошибка загрузки данных: {e}")
                self.init_default_data()
        else:
            self.init_default_data()
    
    def init_default_data(self):
        """Инициализация данных по умолчанию"""
        self.market = self.init_market()
        self.save_data()
    
    def init_market(self):
        """Инициализация рыночных цен"""
        return {
            'wood': {'price': 10, 'available': 1000},
            'metal': {'price': 25, 'available': 500},
            'food': {'price': 5, 'available': 2000},
            'electronics': {'price': 50, 'available': 200}
        }
    
    def save_data(self):
        """Сохранение данных в файл"""
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'users': self.users,
                'market': self.market
            }, f, ensure_ascii=False, indent=2)
    
    def get_user(self, user_id):
        """Получение данных пользователя"""
        user_id = str(user_id)
        if user_id not in self.users:
            self.users[user_id] = {
                'balance': 5000,  # Стартовый баланс
                'bank': 0,  # Деньги в банке
                'inventory': {},  # Инвентарь
                'businesses': {},  # Бизнесы
                'last_work': None,  # Последняя работа
                'level': 1,  # Уровень
                'exp': 0,  # Опыт
                'daily_streak': 0,  # Дней подряд
                'last_daily': None,  # Последний ежедневный бонус
                'total_earned': 0,  # Всего заработано
                'total_spent': 0,  # Всего потрачено
                'games_won': 0,  # Выиграно игр
                'games_lost': 0,  # Проиграно игр
                'referrals': [],  # Рефералы
                'achievements': []  # Достижения
            }
            self.save_data()
        return self.users[user_id]
    
    def update_balance(self, user_id, amount):
        """Обновление баланса"""
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
    
    def transfer_money(self, from_id, to_id, amount):
        """Перевод денег между пользователями"""
        from_id, to_id = str(from_id), str(to_id)
        if from_id in self.users and to_id in self.users:
            if self.users[from_id]['balance'] >= amount:
                self.users[from_id]['balance'] -= amount
                self.users[from_id]['total_spent'] += amount
                self.users[to_id]['balance'] += amount
                self.users[to_id]['total_earned'] += amount
                self.save_data()
                return True
        return False
    
    def add_exp(self, user_id, amount):
        """Добавление опыта и повышение уровня"""
        user_id = str(user_id)
        if user_id in self.users:
            self.users[user_id]['exp'] += amount
            # Проверка на повышение уровня (100 * уровень)
            while self.users[user_id]['exp'] >= self.users[user_id]['level'] * 100:
                self.users[user_id]['exp'] -= self.users[user_id]['level'] * 100
                self.users[user_id]['level'] += 1
            self.save_data()
            return True
        return False

# Инициализация базы данных
db = GameDatabase()

# ==================== БИЗНЕС СИСТЕМА ====================
BUSINESSES = {
    'farm': {
        'name': '🌾 Ферма',
        'cost': 1000,
        'income': 100,
        'cooldown': 3600,  # 1 час
        'required_level': 1,
        'resources_needed': {'food': 10},
        'description': 'Приносит 100 монет в час'
    },
    'mine': {
        'name': '⛏ Шахта',
        'cost': 5000,
        'income': 500,
        'cooldown': 7200,  # 2 часа
        'required_level': 3,
        'resources_needed': {'metal': 20},
        'description': 'Приносит 500 монет за 2 часа'
    },
    'factory': {
        'name': '🏭 Завод',
        'cost': 15000,
        'income': 2000,
        'cooldown': 21600,  # 6 часов
        'required_level': 5,
        'resources_needed': {'metal': 50, 'electronics': 20},
        'description': 'Приносит 2000 монет за 6 часов'
    },
    'casino': {
        'name': '🎰 Казино',
        'cost': 50000,
        'income': 10000,
        'cooldown': 86400,  # 24 часа
        'required_level': 10,
        'resources_needed': {'electronics': 100, 'wood': 200},
        'description': 'Приносит 10000 монет в день'
    }
}

# ==================== МИНИ-ИГРЫ ====================
class MiniGames:
    @staticmethod
    def roll_dice(bet):
        """Игра в кости"""
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
        """Орел или решка"""
        result = random.choice(['heads', 'tails'])
        
        if choice == result:
            win_amount = bet * 2
            return f"🪙 Выпало: {result}\n✅ Ты угадал! Выигрыш: {win_amount} монет!", win_amount, True
        else:
            return f"🪙 Выпало: {result}\n❌ Ты не угадал! Потеряно: {bet} монет!", -bet, False
    
    @staticmethod
    def slots(bet):
        """Слоты"""
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

# ==================== ОБРАБОТЧИКИ КОМАНД ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    # Проверка на реферала
    if context.args and len(context.args) > 0:
        referrer_id = context.args[0]
        if referrer_id != str(user.id) and referrer_id not in user_data['referrals']:
            referrer_data = db.get_user(referrer_id)
            if referrer_data:
                db.update_balance(referrer_id, 500)
                user_data['referrals'].append(referrer_id)
                await context.bot.send_message(
                    referrer_id,
                    f"🎉 По вашей реферальной ссылке зарегистрировался {user.first_name}!\n💰 +500 монет!"
                )
    
    welcome_text = f"""
🌟 Добро пожаловать в RPG Бизнес Империю, {user.first_name}! 🌟

💰 Твой баланс: {user_data['balance']} монет
📊 Твой уровень: {user_data['level']}

📋 Доступные команды:
/profile 📊 - твой профиль
/work 💼 - работать
/business 🏪 - управление бизнесом
/casino 🎰 - казино и игры
/shop 🛒 - магазин ресурсов
/market 📈 - рынок сырья
/transfer [id] [сумма] 💸 - перевести деньги
/top 🏆 - топ игроков
/daily 🎁 - ежедневный бонус
/help ❓ - помощь

👑 Админ команды:
/addmoney [id] [сумма] - выдать деньги
/reset [id] - сбросить игрока
/market_reset - сбросить рынок
"""
    
    # Создаем клавиатуру
    keyboard = [
        [InlineKeyboardButton("📊 Профиль", callback_data="profile"),
         InlineKeyboardButton("💰 Работа", callback_data="work")],
        [InlineKeyboardButton("🏪 Бизнес", callback_data="business_menu"),
         InlineKeyboardButton("🎰 Казино", callback_data="casino_menu")],
        [InlineKeyboardButton("🏆 Топ", callback_data="top"),
         InlineKeyboardButton("🎁 Daily", callback_data="daily")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /profile"""
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    # Расчет статистики
    total_games = user_data['games_won'] + user_data['games_lost']
    win_rate = (user_data['games_won'] / total_games * 100) if total_games > 0 else 0
    
    profile_text = f"""
👤 Профиль: {user.first_name}
🆔 ID: {user.id}

💰 Баланс: {user_data['balance']} монет
🏦 Банк: {user_data['bank']} монет
📊 Уровень: {user_data['level']} (Опыт: {user_data['exp']}/{user_data['level'] * 100})
📦 Предметов: {sum(user_data['inventory'].values())}
🏪 Бизнесов: {len(user_data['businesses'])}

📈 Статистика:
└ Всего заработано: {user_data['total_earned']}
└ Всего потрачено: {user_data['total_spent']}
└ Игр сыграно: {total_games} (Побед: {user_data['games_won']}, Поражений: {user_data['games_lost']})
└ Винрейт: {win_rate:.1f}%
└ Дней подряд: {user_data['daily_streak']}
└ Рефералов: {len(user_data['referrals'])}
"""
    
    await update.message.reply_text(profile_text)

async def work_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /work"""
    user_id = update.effective_user.id
    user_data = db.get_user(user_id)
    
    # Проверка кулдауна
    if user_data['last_work']:
        last_work = datetime.fromisoformat(user_data['last_work'])
        time_diff = datetime.now() - last_work
        if time_diff.total_seconds() < 3600:  # 1 час кулдаун
            remaining = 3600 - int(time_diff.total_seconds())
            minutes = remaining // 60
            seconds = remaining % 60
            await update.message.reply_text(
                f"⏰ Ты уже работал! Отдохни.\n"
                f"Следующая работа через: {minutes} мин {seconds} сек"
            )
            return
    
    # Генерация случайной работы и заработка
    jobs = [
        ("🚚 Дальнобойщик", random.randint(200, 500)),
        ("👨‍💻 Программист", random.randint(300, 600)),
        ("👨‍🏫 Учитель", random.randint(150, 300)),
        ("👨‍🔧 Строитель", random.randint(250, 450)),
        ("👨‍🍳 Шеф-повар", random.randint(200, 400)),
        ("👨‍🎨 Художник", random.randint(100, 800)),
        ("👨‍✈️ Пилот", random.randint(500, 1000)),
        ("👨‍⚖️ Судья", random.randint(400, 700))
    ]
    
    job, salary = random.choice(jobs)
    
    # Обновление данных
    db.update_balance(user_id, salary)
    db.add_exp(user_id, salary // 10)
    user_data = db.get_user(user_id)
    user_data['last_work'] = datetime.now().isoformat()
    db.save_data()
    
    await update.message.reply_text(
        f"💼 Ты работал: {job}\n"
        f"💰 Заработано: {salary} монет\n"
        f"⭐️ Получено опыта: {salary // 10}\n"
        f"📊 Текущий баланс: {user_data['balance']} монет"
    )

async def casino_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню казино"""
    keyboard = [
        [InlineKeyboardButton("🎲 Кости", callback_data="game_dice"),
         InlineKeyboardButton("🪙 Орёл/Решка", callback_data="game_coin")],
        [InlineKeyboardButton("🎰 Слоты", callback_data="game_slots"),
         InlineKeyboardButton("🔢 Рандом", callback_data="game_random")],
        [InlineKeyboardButton("📊 Моя статистика", callback_data="game_stats"),
         InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎰 Добро пожаловать в казино!\n\n"
        "Выбери игру:",
        reply_markup=reply_markup
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = db.get_user(user_id)
    
    if query.data == "profile":
        # Показываем профиль
        text = f"""
👤 Профиль: {query.from_user.first_name}
💰 Баланс: {user_data['balance']} монет
📊 Уровень: {user_data['level']} (Опыт: {user_data['exp']}/{user_data['level']*100})
🏪 Бизнесов: {len(user_data['businesses'])}
        """
        await query.edit_message_text(text)
    
    elif query.data == "work":
        # Быстрая работа через кнопку
        await work_command(update, context)
        await query.delete()
    
    elif query.data == "casino_menu":
        keyboard = [
            [InlineKeyboardButton("🎲 Кости", callback_data="game_dice"),
             InlineKeyboardButton("🪙 Орёл/Решка", callback_data="game_coin")],
            [InlineKeyboardButton("🎰 Слоты", callback_data="game_slots"),
             InlineKeyboardButton("🔢 Рандом", callback_data="game_random")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎰 Выбери игру:",
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("game_"):
        game = query.data.replace("game_", "")
        
        # Сохраняем состояние игры
        context.user_data['current_game'] = game
        context.user_data['game_state'] = 'waiting_bet'
        
        await query.edit_message_text(
            f"🎮 Игра: {game}\n\n"
            f"💰 Твой баланс: {user_data['balance']} монет\n\n"
            f"Введи сумму ставки:"
        )
    
    elif query.data == "back_to_main":
        keyboard = [
            [InlineKeyboardButton("📊 Профиль", callback_data="profile"),
             InlineKeyboardButton("💰 Работа", callback_data="work")],
            [InlineKeyboardButton("🏪 Бизнес", callback_data="business_menu"),
             InlineKeyboardButton("🎰 Казино", callback_data="casino_menu")],
            [InlineKeyboardButton("🏆 Топ", callback_data="top"),
             InlineKeyboardButton("🎁 Daily", callback_data="daily")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"🌟 Главное меню\n\n💰 Баланс: {user_data['balance']} монет",
            reply_markup=reply_markup
        )

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
                await update.message.reply_text(f"❌ Недостаточно средств! Твой баланс: {user_data['balance']}")
                return
            
            game = context.user_data['current_game']
            
            # Списываем ставку
            db.update_balance(user_id, -bet)
            
            # Играем в выбранную игру
            if game == 'dice':
                result, amount, won = MiniGames.roll_dice(bet)
            elif game == 'coin':
                await update.message.reply_text("Выбери: орёл или решка?")
                context.user_data['game_state'] = 'waiting_choice'
                context.user_data['bet'] = bet
                return
            elif game == 'slots':
                result, amount, won = MiniGames.slots(bet)
            elif game == 'random':
                number = random.randint(1, 10)
                await update.message.reply_text(f"🎲 Загадано число от 1 до 10. Угадай!")
                context.user_data['game_state'] = 'waiting_guess'
                context.user_data['bet'] = bet
                context.user_data['random_number'] = number
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
                f"{result}\n\n💰 Текущий баланс: {user_data['balance']}"
            )
            
            # Очищаем состояние игры
            del context.user_data['current_game']
            del context.user_data['game_state']
            
        except ValueError:
            await update.message.reply_text("❌ Введи число!")
    
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
                f"{result}\n\n💰 Текущий баланс: {user_data['balance']}"
            )
            
            del context.user_data['current_game']
            del context.user_data['game_state']
            del context.user_data['bet']
        else:
            await update.message.reply_text("❌ Введи 'орёл' или 'решка'!")
    
    elif context.user_data.get('game_state') == 'waiting_guess':
        try:
            guess = int(update.message.text)
            bet = context.user_data['bet']
            number = context.user_data['random_number']
            
            if guess == number:
                win_amount = bet * 3
                db.update_balance(user_id, win_amount)
                user_data['games_won'] += 1
                result = f"🎉 Ты угадал! Число было {number}\n💰 Выигрыш: {win_amount} монет!"
            else:
                user_data['games_lost'] += 1
                result = f"❌ Не угадал! Число было {number}\n💔 Потеряно: {bet} монет!"
            
            db.save_data()
            user_data = db.get_user(user_id)
            await update.message.reply_text(
                f"{result}\n\n💰 Текущий баланс: {user_data['balance']}"
            )
            
            del context.user_data['current_game']
            del context.user_data['game_state']
            del context.user_data['bet']
            del context.user_data['random_number']
            
        except ValueError:
            await update.message.reply_text("❌ Введи число от 1 до 10!")

# ==================== АДМИН КОМАНДЫ ====================

async def add_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ команда для выдачи денег"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ У тебя нет прав администратора!")
        return
    
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        
        if db.update_balance(target_id, amount):
            user_data = db.get_user(target_id)
            await update.message.reply_text(
                f"✅ Выдано {amount} монет пользователю {target_id}\n"
                f"💰 Новый баланс: {user_data['balance']}"
            )
        else:
            await update.message.reply_text("❌ Пользователь не найден!")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Использование: /addmoney [id] [сумма]")

async def reset_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ команда для сброса игрока"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ У тебя нет прав администратора!")
        return
    
    try:
        target_id = str(context.args[0])
        if target_id in db.users:
            del db.users[target_id]
            db.save_data()
            await update.message.reply_text(f"✅ Данные игрока {target_id} сброшены!")
        else:
            await update.message.reply_text("❌ Пользователь не найден!")
    except IndexError:
        await update.message.reply_text("❌ Использование: /reset [id]")

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================

def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("work", work_command))
    application.add_handler(CommandHandler("casino", casino_menu))
    application.add_handler(CommandHandler("addmoney", add_money))
    application.add_handler(CommandHandler("reset", reset_player))
    
    # Регистрируем обработчик колбэков
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Регистрируем обработчик сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем бота
    print("🤖 Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
