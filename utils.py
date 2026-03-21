from datetime import datetime, timedelta

def get_pet_emoji(pet_type: str, stage: int) -> str:
    """Возвращает эмодзи питомца в зависимости от типа и стадии"""
    emojis = {
        'fox': ['🦊', '🦊', '🦊✨', '🦊👑'],
        'cat': ['🐱', '🐱', '🐱🌟', '🐱💎'],
        'dragon': ['🥚', '🐉', '🐉🔥', '🐉👑'],
        'owl': ['🦉', '🦉', '🦉✨', '🦉📚']
    }
    return emojis.get(pet_type, ['🐾'])[min(stage, 3)]

def get_stage_name(stage: int) -> str:
    stages = ['🥚 Яйцо', '🐣 Детёныш', '🌟 Юный', '👑 Взрослый']
    return stages[min(stage, 3)]

def should_evolve(user_data) -> bool:
    """Проверяет, пора ли эволюционировать"""
    # Если уже на максимальной стадии
    if user_data['pet_stage'] >= 3:
        return False
    
    # Проверяем возраст питомца (в днях)
    created_at = user_data['created_at']
    days_old = (datetime.now() - created_at).days
    
    # Эволюция каждые 5 дней
    required_days = (user_data['pet_stage'] + 1) * 5
    return days_old >= required_days

def get_hunger_decline(last_feed) -> int:
    """Расчёт голода: 20% в день"""
    hours_since_feed = (datetime.now() - last_feed).total_seconds() / 3600
    decline = int(hours_since_feed / 24 * 20)  # 20% в день
    return min(100, decline)