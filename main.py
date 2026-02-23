from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import get_player, update_player
import config

router = Router()

# ========== ГЛАВНОЕ МЕНЮ ==========
async def get_main_keyboard(user_id: int):
    """Главное меню со всеми кнопками"""
    player = await get_player(user_id)
    
    builder = InlineKeyboardBuilder()
    
    # Верхний ряд (статы)
    builder.row(
        InlineKeyboardButton(text=f"👤 {player['character_name'] or 'Без имени'}", callback_data="profile"),
        InlineKeyboardButton(text=f"💰 {player['money']}$", callback_data="money_menu"),
        width=2
    )
    
    # Основные разделы (3 в ряд)
    builder.row(
        InlineKeyboardButton(text="🚗 Транспорт", callback_data="transport_menu"),
        InlineKeyboardButton(text="🏠 Дом", callback_data="house_menu"),
        InlineKeyboardButton(text="💼 Работа", callback_data="work_menu"),
        width=3
    )
    
    builder.row(
        InlineKeyboardButton(text="🔫 Оружие", callback_data="weapon_menu"),
        InlineKeyboardButton(text="🏪 Магазин 24/7", callback_data="shop_247"),
        InlineKeyboardButton(text="🏦 Банк", callback_data="bank_menu"),
        width=3
    )
    
    builder.row(
        InlineKeyboardButton(text="👮 Фракции", callback_data="fraction_menu"),
        InlineKeyboardButton(text="📱 Телефон", callback_data="phone_menu"),
        InlineKeyboardButton(text="🎰 Казино", callback_data="casino_menu"),
        width=3
    )
    
    builder.row(
        InlineKeyboardButton(text="⚔️ PvP", callback_data="pvp_menu"),
        InlineKeyboardButton(text="🏆 Клан", callback_data="clan_menu"),
        InlineKeyboardButton(text="⭐ Топы", callback_data="leaderboard"),
        width=3
    )
    
    # Нижняя панель
    builder.row(
        InlineKeyboardButton(text="📍 Город", callback_data="city_menu"),
        InlineKeyboardButton(text="📊 Инвентарь", callback_data="inventory"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings"),
        width=3
    )
    
    if player['wanted_level'] > 0:
        builder.row(
            InlineKeyboardButton(text=f"🚔 РОЗЫСК: {player['wanted_level']} ⭐", callback_data="wanted_info"),
            width=1
        )
    
    return builder.as_markup()

@router.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery):
    """Возврат в главное меню"""
    keyboard = await get_main_keyboard(callback.from_user.id)
    await callback.message.edit_text(
        "🏙 **BLACK RUSSIA**\n"
        "Главное меню города",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ========== ПРОФИЛЬ ==========
@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    player = await get_player(callback.from_user.id)
    
    # Статус фракции
    fraction_text = "🚫 Нет" if not player['fraction'] else f"👮 {player['fraction']} [{player['fraction_rank']}]"
    
    # Статус розыска
    wanted_text = f"{player['wanted_level']} ⭐" if player['wanted_level'] > 0 else "Нет"
    
    text = (
        f"👤 **ПРОФИЛЬ**\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📛 Имя: {player['character_name']}\n"
        f"🆔 Паспорт: {player['passport'] or '❌'}\n"
        f"📱 Телефон: {player['phone_number'] or '❌'}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 Наличные: ${player['money']:,}\n"
        f"🏦 В банке: ${player['bank']:,}\n"
        f"📊 Уровень: {player['level']} (XP: {player['experience']})\n"
        f"━━━━━━━━━━━━━━━\n"
        f"❤️ Здоровье: {player['health']}/{player['max_health']}\n"
        f"🛡 Броня: {player['armor']}\n"
        f"🍔 Сытость: {player['hunger']}%\n"
        f"💧 Жажда: {player['thirst']}%\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👮 Фракция: {fraction_text}\n"
        f"🚔 Розыск: {wanted_text}\n"
        f"🏠 Дом: {'Есть' if player['current_house_id'] else 'Нет'}\n"
        f"🚗 Машин: {await get_cars_count(callback.from_user.id)}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 Сменить имя", callback_data="change_name"),
        InlineKeyboardButton(text="📸 Фото", callback_data="profile_photo"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="profile_stats"),
        InlineKeyboardButton(text="🏅 Достижения", callback_data="achievements"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"),
        width=1
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())

# ========== ДЕНЬГИ ==========
@router.callback_query(F.data == "money_menu")
async def money_menu(callback: CallbackQuery):
    player = await get_player(callback.from_user.id)
    
    text = (
        f"💰 **ФИНАНСЫ**\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"Наличные: ${player['money']:,}\n"
        f"В банке: ${player['bank']:,}\n"
        f"Всего: ${player['money'] + player['bank']:,}\n\n"
        f"Последние операции:"
    )
    
    # Показываем последние 3 транзакции
    transactions = await get_last_transactions(callback.from_user.id, 3)
    for t in transactions:
        text += f"\n{t['type']}: {t['amount']}$ - {t['description']}"
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💸 Перевести", callback_data="money_transfer"),
        InlineKeyboardButton(text="💳 Карты", callback_data="bank_cards"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="📊 Вся история", callback_data="money_history"),
        InlineKeyboardButton(text="📈 Курсы валют", callback_data="exchange_rates"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"),
        width=1
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())

# ========== ТРАНСПОРТ ==========
@router.callback_query(F.data == "transport_menu")
async def transport_menu(callback: CallbackQuery):
    player = await get_player(callback.from_user.id)
    cars = await get_player_vehicles(callback.from_user.id)
    
    text = (
        f"🚗 **ТРАНСПОРТ**\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"Всего машин: {len(cars)}\n"
        f"В гараже: {await get_cars_in_garage(callback.from_user.id)}\n"
        f"На улице: {await get_cars_outside(callback.from_user.id)}\n\n"
    )
    
    if cars:
        text += "🚘 Последняя машина:\n"
        last_car = cars[0]
        text += f"• {last_car['model']} ({last_car['license_plate']})\n"
        text += f"  Топливо: {last_car['fuel']}% | Состояние: {last_car['health']}%"
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🚘 Мои машины", callback_data="my_cars"),
        InlineKeyboardButton(text="🏪 Купить авто", callback_data="buy_car"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🔧 Тюнинг", callback_data="tuning_menu"),
        InlineKeyboardButton(text="⛽ Заправка", callback_data="fuel_menu"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🅿️ Гараж", callback_data="garage_menu"),
        InlineKeyboardButton(text="🔍 Найти машину", callback_data="find_car"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"),
        width=1
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())

@router.callback_query(F.data == "my_cars")
async def my_cars(callback: CallbackQuery):
    cars = await get_player_vehicles(callback.from_user.id)
    
    if not cars:
        await callback.answer("🚫 У вас нет машин!", show_alert=True)
        return
    
    text = "🚘 **ВАШИ МАШИНЫ**\n━━━━━━━━━━━━━━━\n\n"
    
    builder = InlineKeyboardBuilder()
    
    for i, car in enumerate(cars[:5], 1):
        status = "🔓" if not car['is_locked'] else "🔒"
        location = "В гараже" if car['garage_id'] else "На улице"
        
        text += f"{status} **{car['model']}**\n"
        text += f"└ Номер: {car['license_plate']}\n"
        text += f"└ {location} | Бензин: {car['fuel']}%\n"
        text += f"└ Пробег: {car['mileage']} км\n\n"
        
        builder.row(
            InlineKeyboardButton(text=f"🚗 {car['model']}", callback_data=f"car_info_{car['vehicle_id']}"),
            width=1
        )
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="transport_menu"),
        width=1
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())

# ========== РАБОТА ==========
@router.callback_query(F.data == "work_menu")
async def work_menu(callback: CallbackQuery):
    player = await get_player(callback.from_user.id)
    job = await get_player_job(callback.from_user.id)
    
    text = (
        f"💼 **ЦЕНТР ЗАНЯТОСТИ**\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"Текущая работа: {job['job_name'] if job else 'Безработный'}\n"
        f"Уровень: {job['job_level'] if job else 0}\n"
        f"Опыт: {job['job_exp'] if job else 0}\n\n"
        f"📋 Доступные работы:\n"
    )
    
    builder = InlineKeyboardBuilder()
    
    # Добавляем все работы из конфига
    for job_id, job_name in config.JOBS.items():
        builder.row(
            InlineKeyboardButton(text=f"🚚 {job_name}", callback_data=f"job_info_{job_id}"),
            width=1
        )
    
    # Кнопка начать работу если есть работа
    if job:
        builder.row(
            InlineKeyboardButton(text="▶️ НАЧАТЬ РАБОТУ", callback_data="start_working"),
            width=1
        )
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"),
        width=1
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("job_info_"))
async def job_info(callback: CallbackQuery):
    job_id = callback.data.replace("job_info_", "")
    job_name = config.JOBS[job_id]
    
    # Инфа о работе
    job_details = {
        "trucker": {"min_level": 1, "pay": "100-300$", "desc": "Перевозка грузов между городами"},
        "miner": {"min_level": 2, "pay": "80-200$", "desc": "Добыча полезных ископаемых"},
        "fisher": {"min_level": 1, "pay": "50-150$", "desc": "Ловля рыбы на продажу"},
        # ... остальные работы
    }
    
    info = job_details.get(job_id, {})
    
    text = (
        f"🚚 **{job_name}**\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📝 {info.get('desc', 'Нет описания')}\n\n"
        f"💰 Зарплата: {info.get('pay', '100$')}\n"
        f"📊 Требуемый уровень: {info.get('min_level', 1)}\n\n"
        f"Хотите устроиться на эту работу?"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Устроиться", callback_data=f"apply_job_{job_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="work_menu"),
        width=2
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())

@router.callback_query(F.data == "start_working")
async def start_working(callback: CallbackQuery):
    player = await get_player(callback.from_user.id)
    job = await get_player_job(callback.from_user.id)
    
    if not job:
        await callback.answer("Сначала устроитесь на работу!", show_alert=True)
        return
    
    # Проверяем кулдаун
    if job['last_work']:
        cooldown = (datetime.now() - job['last_work']).seconds
        if cooldown < 300:  # 5 минут
            wait = 300 - cooldown
            await callback.answer(f"⏳ Отдых {wait} секунд!", show_alert=True)
            return
    
    # Разные мини-игры для разных работ
    if job['job_name'] == "Дальнобойщик":
        await trucker_game(callback)
    elif job['job_name'] == "Шахтер":
        await miner_game(callback)
    else:
        await simple_work(callback)

async def trucker_game(callback: CallbackQuery):
    """Мини-игра для дальнобойщика"""
    cities = ["Центр", "Север", "Юг", "Восток", "Запад"]
    from_city = random.choice(cities)
    to_city = random.choice([c for c in cities if c != from_city])
    distance = random.randint(10, 50)
    pay = distance * random.randint(8, 12)
    
    text = (
        f"🚛 **ДАЛЬНОБОЙЩИК**\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📍 Маршрут: {from_city} → {to_city}\n"
        f"📏 Расстояние: {distance} км\n"
        f"💰 Оплата: ${pay}\n"
        f"⛽ Расход топлива: {distance // 2}%\n\n"
        f"Отправиться в рейс?"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Поехали", callback_data=f"trucker_go_{from_city}_{to_city}_{pay}_{distance}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="work_menu"),
        width=2
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())

# ========== ФРАКЦИИ ==========
@router.callback_query(F.data == "fraction_menu")
async def fraction_menu(callback: CallbackQuery):
    player = await get_player(callback.from_user.id)
    
    text = (
        f"👮 **ФРАКЦИИ ГОРОДА**\n"
        f"━━━━━━━━━━━━━━━\n\n"
    )
    
    if player['fraction']:
        text += f"Ваша фракция: **{player['fraction']}**\n"
        text += f"Ранг: {player['fraction_rank']}\n"
        text += f"Опыт: {player['fraction_exp']}\n\n"
    else:
        text += "Вы не состоите во фракции\n\n"
    
    builder = InlineKeyboardBuilder()
    
    # Кнопки фракций
    for frac_id, frac_name in config.FRACTIONS.items():
        builder.row(
            InlineKeyboardButton(text=f"👮 {frac_name}", callback_data=f"fraction_info_{frac_id}"),
            width=1
        )
    
    if player['fraction']:
        builder.row(
            InlineKeyboardButton(text="📋 Меню фракции", callback_data="my_fraction_menu"),
            width=1
        )
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"),
        width=1
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("fraction_info_"))
async def fraction_info(callback: CallbackQuery):
    frac_id = callback.data.replace("fraction_info_", "")
    frac_name = config.FRACTIONS[frac_id]
    
    # Инфа о фракции
    fractions_info = {
        "police": {
            "desc": "Поддержание порядка в городе",
            "requirements": "Уровень 5, чистый профиль",
            "benefits": "Зарплата, табельное оружие, форма"
        },
        "mafia": {
            "desc": "Контроль криминала в городе",
            "requirements": "Уровень 3, связи",
            "benefits": "Нелегальный бизнес, крышевание"
        },
        # ... остальные фракции
    }
    
    info = fractions_info.get(frac_id, {})
    
    text = (
        f"👮 **{frac_name}**\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📝 {info.get('desc', 'Нет описания')}\n\n"
        f"📋 Требования:\n{info.get('requirements', 'Нет')}\n\n"
        f"🎁 Преимущества:\n{info.get('benefits', 'Нет')}\n\n"
        f"Вступить во фракцию?"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Вступить", callback_data=f"join_fraction_{frac_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="fraction_menu"),
        width=2
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())

# ========== МАГАЗИН 24/7 ==========
@router.callback_query(F.data == "shop_247")
async def shop_247(callback: CallbackQuery):
    player = await get_player(callback.from_user.id)
    
    text = (
        f"🏪 **МАГАЗИН 24/7**\n"
        f"Ваш баланс: ${player['money']:,}\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"Что желаете купить?"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🍔 Еда", callback_data="shop_food"),
        InlineKeyboardButton(text="💊 Аптечка", callback_data="shop_medkit"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="📱 Сим-карта", callback_data="shop_sim"),
        InlineKeyboardButton(text="🧥 Одежда", callback_data="shop_clothes"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🎫 Лотерея", callback_data="shop_lottery"),
        InlineKeyboardButton(text="🎁 Подарки", callback_data="shop_gifts"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"),
        width=1
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())

@router.callback_query(F.data == "shop_food")
async def shop_food(callback: CallbackQuery):
    text = "🍔 **ЕДА**\n━━━━━━━━━━━━━━━\n\n"
    
    builder = InlineKeyboardBuilder()
    
    food_items = [
        {"name": "Бутерброд", "price": 10, "hunger": 15},
        {"name": "Пицца", "price": 50, "hunger": 40},
        {"name": "Гамбургер", "price": 30, "hunger": 30},
        {"name": "Кола", "price": 15, "thirst": 20},
        {"name": "Вода", "price": 5, "thirst": 15}
    ]
    
    for item in food_items:
        builder.row(
            InlineKeyboardButton(
                text=f"{item['name']} - {item['price']}$", 
                callback_data=f"buy_food_{item['name']}_{item['price']}"
            ),
            width=1
        )
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="shop_247"),
        width=1
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())

# ========== ОРУЖИЕ ==========
@router.callback_query(F.data == "weapon_menu")
async def weapon_menu(callback: CallbackQuery):
    player = await get_player(callback.from_user.id)
    
    text = (
        f"🔫 **ОРУЖЕЙНЫЙ МАГАЗИН**\n"
        f"Ваш баланс: ${player['money']:,}\n"
        f"Лицензия: {'✅' if player['weapon_license'] else '❌'}\n"
        f"━━━━━━━━━━━━━━━\n\n"
    )
    
    if not player['weapon_license']:
        text += "❌ Для покупки оружия нужна лицензия!\n"
        text += "Купите лицензию в банке."
    
    builder = InlineKeyboardBuilder()
    
    if player['weapon_license']:
        builder.row(
            InlineKeyboardButton(text="🔫 Пистолеты", callback_data="weapon_pistols"),
            InlineKeyboardButton(text="🔪 Холодное", callback_data="weapon_melee"),
            width=2
        )
        builder.row(
            InlineKeyboardButton(text="🔫 Автоматы", callback_data="weapon_rifles"),
            InlineKeyboardButton(text="💣 Гранаты", callback_data="weapon_grenades"),
            width=2
        )
    
    builder.row(
        InlineKeyboardButton(text="🎯 Тиры", callback_data="shooting_range"),
        InlineKeyboardButton(text="📊 Мое оружие", callback_data="my_weapons"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"),
        width=1
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())

# ========== КАЗИНО ==========
@router.callback_query(F.data == "casino_menu")
async def casino_menu(callback: CallbackQuery):
    player = await get_player(callback.from_user.id)
    
    text = (
        f"🎰 **КАЗИНО BLACK RUSSIA**\n"
        f"Ваш баланс: ${player['money']:,}\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"Выберите игру:"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎰 Слоты", callback_data="casino_slots"),
        InlineKeyboardButton(text="🎲 Кости", callback_data="casino_dice"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🃏 Блэкджек", callback_data="casino_blackjack"),
        InlineKeyboardButton(text="🎡 Рулетка", callback_data="casino_roulette"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🏆 Турниры", callback_data="casino_tournaments"),
        InlineKeyboardButton(text="📊 Моя статистика", callback_data="casino_stats"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"),
        width=1
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())

@router.callback_query(F.data == "casino_slots")
async def casino_slots(callback: CallbackQuery):
    text = (
        f"🎰 **ИГРОВЫЕ АВТОМАТЫ**\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"Выберите ставку:"
    )
    
    builder = InlineKeyboardBuilder()
    for bet in [10, 50, 100, 500, 1000]:
        builder.row(
            InlineKeyboardButton(text=f"💰 Ставка {bet}$", callback_data=f"slot_bet_{bet}"),
            width=1
        )
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="casino_menu"),
        width=1
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())

# ========== ТЕЛЕФОН ==========
@router.callback_query(F.data == "phone_menu")
async def phone_menu(callback: CallbackQuery):
    player = await get_player(callback.from_user.id)
    
    if not player['phone_number']:
        text = "📱 **ТЕЛЕФОН**\n━━━━━━━━━━━━━━━\n\n❌ У вас нет телефона!\nКупите сим-карту в магазине 24/7"
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🏪 Купить сим-карту", callback_data="shop_sim"),
            InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"),
            width=1
        )
    else:
        text = (
            f"📱 **ТЕЛЕФОН**\n"
            f"Номер: {player['phone_number']}\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"Что хотите сделать?"
        )
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📞 Позвонить", callback_data="phone_call"),
            InlineKeyboardButton(text="💬 Написать SMS", callback_data="phone_sms"),
            width=2
        )
        builder.row(
            InlineKeyboardButton(text="📇 Контакты", callback_data="phone_contacts"),
            InlineKeyboardButton(text="📨 Сообщения", callback_data="phone_messages"),
            width=2
        )
        builder.row(
            InlineKeyboardButton(text="📻 Рация", callback_data="phone_radio"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="phone_settings"),
            width=2
        )
        builder.row(
            InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"),
            width=1
        )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())

# ========== PVP ==========
@router.callback_query(F.data == "pvp_menu")
async def pvp_menu(callback: CallbackQuery):
    player = await get_player(callback.from_user.id)
    
    text = (
        f"⚔️ **PvP АРЕНА**\n"
        f"Ваше здоровье: {player['health']}/{player['max_health']}\n"
        f"Броня: {player['armor']}\n"
        f"Оружие: {player['weapon']}\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"Выберите режим:"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚔️ Дуэль", callback_data="pvp_duel"),
        InlineKeyboardButton(text="👥 Командный бой", callback_data="pvp_team"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🏆 Рейтинговые", callback_data="pvp_ranked"),
        InlineKeyboardButton(text="🎯 Тренировка", callback_data="pvp_train"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="pvp_stats"),
        InlineKeyboardButton(text="🏅 Топ бойцов", callback_data="pvp_top"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"),
        width=1
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())

# ========== ИНВЕНТАРЬ ==========
@router.callback_query(F.data == "inventory")
async def inventory_menu(callback: CallbackQuery):
    weapons = await get_player_weapons(callback.from_user.id)
    items = await get_player_items(callback.from_user.id)
    
    text = (
        f"🎒 **ИНВЕНТАРЬ**\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"🔫 Оружие: {len(weapons)} шт.\n"
        f"📦 Предметы: {len(items)} шт.\n\n"
    )
    
    if weapons:
        text += "**Оружие:**\n"
        for w in weapons[:3]:
            text += f"• {w['weapon_name']} ({w['ammo']} патр.)\n"
    
    if items:
        text += "\n**Предметы:**\n"
        for i in items[:3]:
            text += f"• {i['item_name']} x{i['quantity']}\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔫 Оружие", callback_data="inventory_weapons"),
        InlineKeyboardButton(text="📦 Предметы", callback_data="inventory_items"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="💊 Наркотики", callback_data="inventory_drugs"),
        InlineKeyboardButton(text="🎫 Документы", callback_data="inventory_docs"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"),
        width=1
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())

# Вспомогательные функции
async def get_cars_count(user_id):
    conn = await get_connection()
    count = await conn.fetchval("SELECT COUNT(*) FROM vehicles WHERE owner_id = $1", user_id)
    await conn.close()
    return count

async def get_cars_in_garage(user_id):
    conn = await get_connection()
    count = await conn.fetchval("SELECT COUNT(*) FROM vehicles WHERE owner_id = $1 AND garage_id IS NOT NULL", user_id)
    await conn.close()
    return count

async def get_cars_outside(user_id):
    conn = await get_connection()
    count = await conn.fetchval("SELECT COUNT(*) FROM vehicles WHERE owner_id = $1 AND garage_id IS NULL", user_id)
    await conn.close()
    return count

async def get_player_vehicles(user_id):
    conn = await get_connection()
    vehicles = await conn.fetch("SELECT * FROM vehicles WHERE owner_id = $1 ORDER BY bought_date DESC", user_id)
    await conn.close()
    return vehicles

async def get_player_job(user_id):
    conn = await get_connection()
    job = await conn.fetchrow("SELECT * FROM player_jobs WHERE user_id = $1", user_id)
    await conn.close()
    return job

async def get_last_transactions(user_id, limit):
    conn = await get_connection()
    trans = await conn.fetch("SELECT * FROM transactions WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2", user_id, limit)
    await conn.close()
    return trans

async def get_player_weapons(user_id):
    conn = await get_connection()
    weapons = await conn.fetch("SELECT * FROM inventory_weapons WHERE owner_id = $1", user_id)
    await conn.close()
    return weapons

async def get_player_items(user_id):
    conn = await get_connection()
    items = await conn.fetch("SELECT * FROM inventory_items WHERE owner_id = $1", user_id)
    await conn.close()
    return items
