"""
███████╗ ██████╗ ███╗   ███╗██████╗ ██╗███████╗    █████╗ ██████╗  ██████╗  ██████╗ █████╗ ██╗     ██╗██████╗ ███████╗██╗███████╗
╚══███╔╝██╔══██╗████╗ ████║██╔══██╗██║██╔════╝   ██╔══██╗██╔══██╗██╔═══██╗██╔════╝██╔══██╗██║     ██║██╔══██╗██╔════╝██║██╔════╝
  ███╔╝ ███████║██╔████╔██║██████╔╝██║███████╗   ███████║██████╔╝██║   ██║██║     ███████║██║     ██║██████╔╝███████╗██║███████╗
 ███╔╝  ██╔══██║██║╚██╔╝██║██╔═══╝ ██║╚════██║   ██╔══██║██╔═══╝ ██║   ██║██║     ██╔══██║██║     ██║██╔═══╝ ╚════██║██║╚════██║
███████╗██║  ██║██║ ╚═╝ ██║██║     ██║███████║   ██║  ██║██║     ╚██████╔╝╚██████╗██║  ██║███████╗██║██║     ███████║██║███████║
╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝     ╚═╝╚══════╝   ╚═╝  ╚═╝╚═╝      ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝╚═╝     ╚══════╝╚═╝╚══════╝
Зомби Апокалипсис RPG v3.0 - МЕГА ВЕРСИЯ с сюжетом, экономикой, кланами, ивентами и мультиплеером
"""

import os
import logging
import random
import json
import asyncio
import sqlite3
import hashlib
import time
import math
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
import threading

# Telegram
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
from flask import Flask, jsonify, request

# ============================================
# ТОКЕН БОТА (ВСТАВЛЕН ТВОЙ)
# ============================================

TOKEN = "7952669809:AAGWRKCVWluswRysvH2qVYKQnuAn4KvDMcs"

# ============================================
# НАСТРОЙКИ ЛОГИРОВАНИЯ
# ============================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# FLASK ДЛЯ BOTHOST
# ============================================

app = Flask(__name__)

@app.route('/')
def home():
    return "🧟 Zombie Apocalypse RPG Bot is running 24/7! МЕГА ВЕРСИЯ 3.0"

@app.route('/health')
def health():
    return jsonify({
        "status": "alive", 
        "players": len(game.players) if 'game' in globals() else 0,
        "clans": len(game.clans) if 'game' in globals() else 0,
        "uptime": str(datetime.now() - game.start_time) if 'game' in globals() else "unknown"
    })

@app.route('/stats')
def stats():
    if 'game' not in globals():
        return jsonify({"error": "Game not initialized"})
    
    return jsonify({
        "total_players": len(game.players),
        "total_clans": len(game.clans),
        "total_kills": sum(p.kills["zombie"] for p in game.players.values()),
        "total_wealth": sum(p.money["bottlecaps"] for p in game.players.values()),
        "active_battles": len(game.active_battles),
        "game_day": game.game_day,
        "game_hour": game.game_hour,
        "current_event": game.current_event.name if game.current_event else None
    })

def run_flask():
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# ============================================
# БАЗА ДАННЫХ
# ============================================

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('zombie_rpg.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.init_db()
    
    def init_db(self):
        # Игроки
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                data TEXT,
                level INTEGER DEFAULT 1,
                days_survived INTEGER DEFAULT 1,
                kills INTEGER DEFAULT 0,
                wealth INTEGER DEFAULT 100,
                clan_id INTEGER,
                reputation_survivors INTEGER DEFAULT 0,
                reputation_raiders INTEGER DEFAULT 0,
                reputation_military INTEGER DEFAULT 0,
                reputation_scientists INTEGER DEFAULT 0,
                reputation_cult INTEGER DEFAULT 0,
                last_active TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Кланы
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS clans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                tag TEXT UNIQUE,
                leader_id INTEGER,
                level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0,
                members_count INTEGER DEFAULT 1,
                base_level INTEGER DEFAULT 1,
                treasury INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Инвентарь
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_id TEXT,
                item_type TEXT,
                name TEXT,
                quantity INTEGER,
                durability INTEGER,
                equipped BOOLEAN DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES players(user_id)
            )
        ''')
        
        # Квесты
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                quest_id TEXT,
                quest_name TEXT,
                progress INTEGER,
                target INTEGER,
                completed BOOLEAN DEFAULT 0,
                reward_type TEXT,
                reward_amount INTEGER,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES players(user_id)
            )
        ''')
        
        # Достижения
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                achievement_id TEXT,
                achievement_name TEXT,
                unlocked_at TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES players(user_id)
            )
        ''')
        
        # Торговый рынок
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS market (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id INTEGER,
                item_id TEXT,
                item_name TEXT,
                quantity INTEGER,
                price_per_unit INTEGER,
                currency TEXT DEFAULT 'bottlecaps',
                listed_at TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY(seller_id) REFERENCES players(user_id)
            )
        ''')
        
        # Логи действий
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def save_player(self, user_id, username, player):
        data_json = json.dumps({
            'stats': player.stats,
            'money': player.money,
            'kills': player.kills,
            'location': player.location,
            'shelter_level': player.shelter_level,
            'quests': player.quests,
            'achievements': player.achievements,
            'reputation': player.reputation,
            'radiation': player.radiation,
            'hunger': player.hunger,
            'thirst': player.thirst,
            'energy': player.energy,
            'max_energy': player.max_energy
        })
        
        self.cursor.execute('''
            INSERT OR REPLACE INTO players 
            (user_id, username, data, level, days_survived, kills, wealth, 
             reputation_survivors, reputation_raiders, reputation_military, 
             reputation_scientists, reputation_cult, last_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, username, data_json, player.level, player.days_survived,
            player.kills['zombie'], player.money['bottlecaps'],
            player.reputation['survivors'], player.reputation['raiders'],
            player.reputation['military'], player.reputation['scientists'],
            player.reputation['cult'], datetime.now()
        ))
        self.conn.commit()
    
    def load_player(self, user_id):
        self.cursor.execute('SELECT * FROM players WHERE user_id = ?', (user_id,))
        result = self.cursor.fetchone()
        if result:
            return {
                'user_id': result[0],
                'username': result[1],
                'data': json.loads(result[2]),
                'level': result[3],
                'days_survived': result[4],
                'kills': result[5],
                'wealth': result[6],
                'clan_id': result[7],
                'reputation': {
                    'survivors': result[8],
                    'raiders': result[9],
                    'military': result[10],
                    'scientists': result[11],
                    'cult': result[12]
                }
            }
        return None
    
    def save_inventory(self, user_id, inventory):
        # Очищаем старый инвентарь
        self.cursor.execute('DELETE FROM inventory WHERE user_id = ?', (user_id,))
        
        # Сохраняем новый
        for item in inventory:
            self.cursor.execute('''
                INSERT INTO inventory (user_id, item_id, item_type, name, quantity, durability, equipped)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, 
                item.get('id', 'unknown'), 
                item.get('type', 'misc'),
                item.get('name', 'Unknown'),
                item.get('quantity', 1),
                item.get('durability', 100),
                item.get('equipped', False)
            ))
        
        self.conn.commit()
    
    def load_inventory(self, user_id):
        self.cursor.execute('SELECT * FROM inventory WHERE user_id = ?', (user_id,))
        results = self.cursor.fetchall()
        inventory = []
        for row in results:
            inventory.append({
                'id': row[2],
                'type': row[3],
                'name': row[4],
                'quantity': row[5],
                'durability': row[6],
                'equipped': bool(row[7])
            })
        return inventory
    
    def log_action(self, user_id, action, details=None):
        self.cursor.execute('''
            INSERT INTO logs (user_id, action, details)
            VALUES (?, ?, ?)
        ''', (user_id, action, json.dumps(details) if details else None))
        self.conn.commit()

# ============================================
# ИГРОВЫЕ КЛАССЫ
# ============================================

class GameState(Enum):
    MENU = "menu"
    EXPLORING = "exploring"
    IN_BATTLE = "battle"
    TRADING = "trading"
    CRAFTING = "crafting"
    SHELTER = "shelter"
    CLAN = "clan"

class ItemRarity(Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"

class ItemType(Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    CONSUMABLE = "consumable"
    MATERIAL = "material"
    AMMO = "ammo"
    MEDICAL = "medical"
    FOOD = "food"
    WATER = "water"
    MISC = "misc"

class Weapon:
    def __init__(self, weapon_id, name, damage, range_type, durability, weight, price, rarity, ammo_type=None, ammo_per_shot=1, special_effects=None):
        self.id = weapon_id
        self.name = name
        self.damage = damage
        self.range_type = range_type  # melee, short, medium, long
        self.durability = durability
        self.max_durability = durability
        self.weight = weight
        self.price = price
        self.rarity = rarity
        self.ammo_type = ammo_type
        self.ammo_per_shot = ammo_per_shot
        self.special_effects = special_effects or {}
        self.type = ItemType.WEAPON

class Armor:
    def __init__(self, armor_id, name, defense, durability, weight, price, rarity, special_effects=None):
        self.id = armor_id
        self.name = name
        self.defense = defense
        self.durability = durability
        self.max_durability = durability
        self.weight = weight
        self.price = price
        self.rarity = rarity
        self.special_effects = special_effects or {}
        self.type = ItemType.ARMOR

class Consumable:
    def __init__(self, consumable_id, name, effect_type, effect_value, weight, price, rarity):
        self.id = consumable_id
        self.name = name
        self.effect_type = effect_type  # heal, energy, antidote, etc.
        self.effect_value = effect_value
        self.weight = weight
        self.price = price
        self.rarity = rarity
        self.type = ItemType.CONSUMABLE

class Enemy:
    def __init__(self, enemy_type, level):
        self.type = enemy_type
        self.level = level
        
        enemies_db = {
            # Обычные зомби
            "walker": {
                "name": "🧟 Ходячий",
                "hp_base": 30,
                "hp_per_level": 10,
                "damage_base": 5,
                "damage_per_level": 2,
                "exp_base": 10,
                "exp_per_level": 10,
                "loot_table": [
                    {"item": "rotten_flesh", "chance": 80, "min": 1, "max": 2},
                    {"item": "rags", "chance": 60, "min": 1, "max": 1},
                    {"item": "bottlecaps", "chance": 30, "min": 1, "max": 5}
                ],
                "description": "Медленный, но опасный в группе",
                "image": "🧟"
            },
            "runner": {
                "name": "🏃 Бегун",
                "hp_base": 20,
                "hp_per_level": 8,
                "damage_base": 8,
                "damage_per_level": 3,
                "exp_base": 15,
                "exp_per_level": 15,
                "loot_table": [
                    {"item": "rotten_flesh", "chance": 70, "min": 1, "max": 1},
                    {"item": "sneakers", "chance": 40, "min": 1, "max": 1},
                    {"item": "energy_drink", "chance": 20, "min": 1, "max": 1},
                    {"item": "bottlecaps", "chance": 40, "min": 2, "max": 8}
                ],
                "description": "Быстрый, сложно убежать",
                "image": "🏃"
            },
            "fatty": {
                "name": "🍔 Толстяк",
                "hp_base": 80,
                "hp_per_level": 20,
                "damage_base": 15,
                "damage_per_level": 4,
                "exp_base": 25,
                "exp_per_level": 25,
                "loot_table": [
                    {"item": "fat", "chance": 90, "min": 1, "max": 3},
                    {"item": "rotten_meat", "chance": 80, "min": 2, "max": 4},
                    {"item": "first_aid_kit", "chance": 15, "min": 1, "max": 1},
                    {"item": "bottlecaps", "chance": 50, "min": 5, "max": 15}
                ],
                "description": "Много HP, медленный",
                "image": "🍔"
            },
            "spitter": {
                "name": "💦 Плевальщик",
                "hp_base": 40,
                "hp_per_level": 12,
                "damage_base": 10,
                "damage_per_level": 3,
                "exp_base": 20,
                "exp_per_level": 20,
                "loot_table": [
                    {"item": "acid_gland", "chance": 70, "min": 1, "max": 2},
                    {"item": "toxic_waste", "chance": 40, "min": 1, "max": 1},
                    {"item": "antidote", "chance": 10, "min": 1, "max": 1},
                    {"item": "bottlecaps", "chance": 45, "min": 3, "max": 10}
                ],
                "description": "Атакует кислотой на расстоянии",
                "image": "💦"
            },
            # Элитные
            "brute": {
                "name": "💪 Брут",
                "hp_base": 150,
                "hp_per_level": 30,
                "damage_base": 25,
                "damage_per_level": 5,
                "exp_base": 50,
                "exp_per_level": 50,
                "loot_table": [
                    {"item": "metal_armor", "chance": 30, "min": 1, "max": 1},
                    {"item": "sledgehammer", "chance": 20, "min": 1, "max": 1},
                    {"item": "military_rations", "chance": 40, "min": 2, "max": 4},
                    {"item": "bottlecaps", "chance": 80, "min": 20, "max": 50}
                ],
                "description": "Мутировавший здоровяк",
                "image": "💪"
            },
            "screamer": {
                "name": "📢 Крикун",
                "hp_base": 60,
                "hp_per_level": 15,
                "damage_base": 5,
                "damage_per_level": 2,
                "exp_base": 30,
                "exp_per_level": 30,
                "loot_table": [
                    {"item": "vocal_cords", "chance": 80, "min": 1, "max": 1},
                    {"item": "stun_grenade", "chance": 15, "min": 1, "max": 1},
                    {"item": "earplugs", "chance": 30, "min": 1, "max": 1},
                    {"item": "bottlecaps", "chance": 60, "min": 10, "max": 25}
                ],
                "description": "Призывает подмогу криком",
                "image": "📢"
            },
            # Боссы
            "boss_zombie": {
                "name": "👑 Король Зомби",
                "hp_base": 500,
                "hp_per_level": 100,
                "damage_base": 40,
                "damage_per_level": 8,
                "exp_base": 200,
                "exp_per_level": 100,
                "loot_table": [
                    {"item": "crown", "chance": 100, "min": 1, "max": 1},
                    {"item": "zombie_heart", "chance": 100, "min": 1, "max": 1},
                    {"item": "legendary_weapon", "chance": 50, "min": 1, "max": 1},
                    {"item": "bottlecaps", "chance": 100, "min": 100, "max": 300}
                ],
                "description": "Повелитель орды",
                "image": "👑"
            },
            "boss_doctor": {
                "name": "🥼 Доктор Зед",
                "hp_base": 400,
                "hp_per_level": 80,
                "damage_base": 35,
                "damage_per_level": 7,
                "exp_base": 180,
                "exp_per_level": 90,
                "loot_table": [
                    {"item": "lab_key", "chance": 100, "min": 1, "max": 1},
                    {"item": "antidote_recipe", "chance": 100, "min": 1, "max": 1},
                    {"item": "cure_vial", "chance": 70, "min": 1, "max": 1},
                    {"item": "bottlecaps", "chance": 100, "min": 80, "max": 250}
                ],
                "description": "Создатель вируса",
                "image": "🥼"
            }
        }
        
        data = enemies_db[enemy_type]
        self.name = data["name"]
        self.hp = data["hp_base"] + (level * data["hp_per_level"])
        self.max_hp = self.hp
        self.damage = data["damage_base"] + (level * data["damage_per_level"])
        self.exp_reward = data["exp_base"] + (level * data["exp_per_level"])
        self.loot_table = data["loot_table"]
        self.description = data["description"]
        self.image = data["image"]

class Location:
    def __init__(self, loc_id, name, description, min_level, max_level, danger, loot_table, enemies, npcs=None, special_actions=None):
        self.id = loc_id
        self.name = name
        self.description = description
        self.min_level = min_level
        self.max_level = max_level
        self.danger = danger  # 0-100
        self.loot_table = loot_table
        self.enemies = enemies
        self.npcs = npcs or []
        self.special_actions = special_actions or {}

class NPC:
    def __init__(self, npc_id, name, location, dialogue, quests=None, shop=None):
        self.id = npc_id
        self.name = name
        self.location = location
        self.dialogue = dialogue
        self.quests = quests or []
        self.shop = shop or {}

class Quest:
    def __init__(self, quest_id, name, description, type, target, reward_type, reward_amount, required_level=1, next_quest=None):
        self.id = quest_id
        self.name = name
        self.description = description
        self.type = type  # kill, collect, explore, escort
        self.target = target
        self.reward_type = reward_type
        self.reward_amount = reward_amount
        self.required_level = required_level
        self.next_quest = next_quest

class Achievement:
    def __init__(self, ach_id, name, description, condition, reward_type, reward_amount):
        self.id = ach_id
        self.name = name
        self.description = description
        self.condition = condition  # условие для проверки
        self.reward_type = reward_type
        self.reward_amount = reward_amount

class Clan:
    def __init__(self, clan_id, name, tag, leader_id):
        self.id = clan_id
        self.name = name
        self.tag = tag
        self.leader_id = leader_id
        self.members = [leader_id]
        self.level = 1
        self.exp = 0
        self.base_level = 1
        self.treasury = 0
        self.wins = 0
        self.losses = 0
        self.created_at = datetime.now()

class ClanWar:
    def __init__(self, clan1_id, clan2_id):
        self.clan1_id = clan1_id
        self.clan2_id = clan2_id
        self.start_time = datetime.now()
        self.clan1_points = 0
        self.clan2_points = 0
        self.clan1_members = []
        self.clan2_members = []
        self.active = True

class Event:
    def __init__(self, event_id, name, description, duration, effects, condition=None):
        self.id = event_id
        self.name = name
        self.description = description
        self.duration = duration  # в часах
        self.start_time = None
        self.end_time = None
        self.effects = effects
        self.condition = condition

class Survivor:
    def __init__(self, user_id: int, username: str):
        self.user_id = user_id
        self.username = username
        
        # Основные параметры
        self.level = 1
        self.exp = 0
        self.exp_to_next = 100
        self.days_survived = 1
        
        # Ресурсы
        self.health = 100
        self.max_health = 100
        self.energy = 100
        self.max_energy = 100
        self.hunger = 0
        self.thirst = 0
        self.radiation = 0
        
        # Характеристики
        self.stats = {
            "strength": 5,
            "agility": 5,
            "perception": 5,
            "endurance": 5,
            "intelligence": 5,
            "luck": 5
        }
        
        # Стат поинты для прокачки
        self.stat_points = 0
        
        # Инвентарь (список предметов)
        self.inventory = []
        self.backpack_size = 20
        self.current_weight = 0
        self.max_weight = 50 + (self.stats["strength"] * 5)
        
        # Экипировка
        self.equipment = {
            "weapon": None,
            "armor": None,
            "helmet": None,
            "backpack": None,
            "accessory1": None,
            "accessory2": None
        }
        
        # Экономика
        self.money = {
            "bottlecaps": 100,
            "bullets": 0,
            "meds": 0,
            "food": 0,
            "water": 0,
            "scrap": 0
        }
        
        # Локация
        self.location = "abandoned_shelter"
        self.shelter_level = 1
        
        # Репутации
        self.reputation = {
            "survivors": 0,
            "raiders": 0,
            "military": 0,
            "scientists": 0,
            "cult": 0
        }
        
        # Достижения
        self.achievements = []
        
        # Убийства
        self.kills = {
            "zombie": 0,
            "infected": 0,
            "raider": 0,
            "mutant": 0,
            "boss": 0
        }
        
        # Квесты
        self.quests = []
        self.completed_quests = []
        
        # Клан
        self.clan_id = None
        self.clan_rank = "member"
        
        # Статус
        self.state = GameState.MENU
        self.current_enemy = None
        self.in_battle = False
        
        # Таймеры
        self.last_energy_regen = datetime.now()
        self.last_hunger_increase = datetime.now()
        
        # Статистика
        self.total_played_time = 0
        self.items_crafted = 0
        self.trades_made = 0
        
        # Друзья (для мультиплеера)
        self.friends = []
        self.friend_requests = []
    
    def calculate_max_weight(self):
        self.max_weight = 50 + (self.stats["strength"] * 5)
    
    def calculate_current_weight(self):
        weight = 0
        for item in self.inventory:
            weight += item.get('weight', 1) * item.get('quantity', 1)
        for slot, item in self.equipment.items():
            if item:
                weight += item.get('weight', 0)
        self.current_weight = weight
        return weight
    
    def add_exp(self, amount):
        self.exp += amount
        while self.exp >= self.exp_to_next:
            self.level_up()
    
    def level_up(self):
        self.level += 1
        self.exp -= self.exp_to_next
        self.exp_to_next = int(self.exp_to_next * 1.5)
        self.stat_points += 3
        self.max_health += 20
        self.health = self.max_health
        self.max_energy += 10
        self.energy = self.max_energy
        
        # Сообщение о левелапе будет отправлено отдельно
    
    def add_item(self, item):
        # Проверяем вес
        if self.current_weight + item.get('weight', 1) > self.max_weight:
            return False, "Слишком тяжело!"
        
        # Ищем существующий стак
        for inv_item in self.inventory:
            if inv_item['id'] == item['id'] and inv_item.get('stackable', False):
                inv_item['quantity'] += item.get('quantity', 1)
                self.calculate_current_weight()
                return True, f"+{item.get('quantity', 1)} {item['name']}"
        
        # Добавляем новый предмет
        self.inventory.append(item)
        self.calculate_current_weight()
        return True, f"+ {item['name']}"
    
    def remove_item(self, item_id, quantity=1):
        for i, item in enumerate(self.inventory):
            if item['id'] == item_id:
                if item.get('quantity', 1) > quantity:
                    item['quantity'] -= quantity
                else:
                    self.inventory.pop(i)
                self.calculate_current_weight()
                return True
        return False
    
    def heal(self, amount):
        self.health = min(self.max_health, self.health + amount)
    
    def take_damage(self, amount):
        # Учет брони
        armor_defense = 0
        if self.equipment["armor"]:
            armor_defense += self.equipment["armor"].get('defense', 0)
        if self.equipment["helmet"]:
            armor_defense += self.equipment["helmet"].get('defense', 0)
        
        damage_reduction = armor_defense * 0.5
        actual_damage = max(1, amount - damage_reduction)
        
        self.health -= actual_damage
        return actual_damage
    
    def use_energy(self, amount):
        if self.energy >= amount:
            self.energy -= amount
            return True
        return False
    
    def regenerate_energy(self):
        now = datetime.now()
        hours_passed = (now - self.last_energy_regen).total_seconds() / 3600
        if hours_passed >= 1:
            regen = int(hours_passed * 10)
            self.energy = min(self.max_energy, self.energy + regen)
            self.last_energy_regen = now
    
    def increase_hunger_thirst(self):
        now = datetime.now()
        hours_passed = (now - self.last_hunger_increase).total_seconds() / 3600
        if hours_passed >= 1:
            increase = int(hours_passed * 2)
            self.hunger = min(100, self.hunger + increase)
            self.thirst = min(100, self.thirst + increase)
            self.last_hunger_increase = now
            
            # Эффекты от голода и жажды
            if self.hunger > 80 or self.thirst > 80:
                self.health = max(1, self.health - 2)
    
    def eat(self, food_item):
        if food_item['effect_type'] == 'food':
            self.hunger = max(0, self.hunger - food_item['effect_value'])
            return True
        elif food_item['effect_type'] == 'water':
            self.thirst = max(0, self.thirst - food_item['effect_value'])
            return True
        elif food_item['effect_type'] == 'both':
            self.hunger = max(0, self.hunger - food_item['effect_value'])
            self.thirst = max(0, self.thirst - food_item['effect_value'])
            return True
        return False
    
    def can_enter_location(self, location):
        if location.min_level > self.level:
            return False, f"Нужен уровень {location.min_level}"
        if self.energy < 10:
            return False, "Недостаточно энергии"
        return True, "OK"
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.username,
            'level': self.level,
            'days_survived': self.days_survived,
            'health': self.health,
            'max_health': self.max_health,
            'energy': self.energy,
            'max_energy': self.max_energy,
            'stats': self.stats,
            'money': self.money,
            'location': self.location,
            'shelter_level': self.shelter_level,
            'kills': self.kills,
            'reputation': self.reputation
        }

# ============================================
# ИГРОВОЙ ДВИЖОК
# ============================================

class ZombieGame:
    def __init__(self):
        self.start_time = datetime.now()
        self.db = Database()
        self.players: Dict[int, Survivor] = {}
        self.active_battles: Dict[int, Enemy] = {}
        self.clans: Dict[int, Clan] = {}
        self.clan_wars: Dict[int, ClanWar] = {}
        self.market_listings: Dict[int, dict] = {}
        self.locations = self.create_locations()
        self.npcs = self.create_npcs()
        self.quests = self.create_quests()
        self.achievements = self.create_achievements()
        self.items_db = self.create_items_db()
        
        # Ивентовая система
        self.current_event: Optional[Event] = None
        self.event_schedule = self.create_events()
        
        # Игровое время
        self.game_day = 1
        self.game_hour = 6
        self.last_time_update = datetime.now()
        
        # Лидерборды
        self.leaderboards = {
            'level': [],
            'kills': [],
            'wealth': [],
            'days': [],
            'clans': []
        }
        
        # Статистика
        self.total_players_registered = 0
        self.total_battles = 0
        self.total_kills = 0
        self.total_trades = 0
        
        # Запускаем фоновые задачи
        self.start_background_tasks()
    
    def start_background_tasks(self):
        """Запуск фоновых задач"""
        loop = asyncio.new_event_loop()
        
        async def game_loop():
            while True:
                await asyncio.sleep(60)  # Каждую минуту
                await self.process_game_time()
        
        async def event_loop():
            while True:
                await asyncio.sleep(300)  # Каждые 5 минут
                await self.check_events()
        
        async def save_loop():
            while True:
                await asyncio.sleep(300)  # Каждые 5 минут
                await self.save_all_players()
        
        async def leaderboard_loop():
            while True:
                await asyncio.sleep(600)  # Каждые 10 минут
                self.update_leaderboards()
        
        loop.create_task(game_loop())
        loop.create_task(event_loop())
        loop.create_task(save_loop())
        loop.create_task(leaderboard_loop())
        
        threading.Thread(target=lambda: asyncio.run(loop), daemon=True).start()
    
    def create_locations(self):
        return {
            "abandoned_shelter": Location(
                "abandoned_shelter", "🏚️ Заброшенное убежище",
                "Твое убежище. Здесь можно отдохнуть и сохраниться.",
                1, 1, 0,
                loot_table=[],
                enemies=[],
                npcs=["trader_joe"],
                special_actions={"rest": "Отдых", "craft": "Крафт", "storage": "Хранилище"}
            ),
            "city_ruins": Location(
                "city_ruins", "🏙️ Руины города",
                "Разрушенный центр города. Много зомби, но есть ценный лут.",
                1, 5, 30,
                loot_table=[
                    {"item": "scrap", "chance": 70, "min": 1, "max": 3},
                    {"item": "food", "chance": 50, "min": 1, "max": 2},
                    {"item": "water", "chance": 50, "min": 1, "max": 2},
                    {"item": "ammo", "chance": 30, "min": 5, "max": 15},
                    {"item": "weapon_parts", "chance": 20, "min": 1, "max": 2}
                ],
                enemies=["walker", "runner"]
            ),
            "hospital": Location(
                "hospital", "🏥 Заброшенная больница",
                "Здесь можно найти медикаменты, но здание кишит зараженными.",
                3, 8, 60,
                loot_table=[
                    {"item": "bandage", "chance": 70, "min": 1, "max": 3},
                    {"item": "painkillers", "chance": 50, "min": 1, "max": 2},
                    {"item": "antibiotics", "chance": 30, "min": 1, "max": 1},
                    {"item": "scalpel", "chance": 20, "min": 1, "max": 1},
                    {"item": "first_aid_kit", "chance": 15, "min": 1, "max": 1}
                ],
                enemies=["walker", "spitter", "brute"],
                npcs=["doctor_stein"]
            ),
            "military_base": Location(
                "military_base", "🔫 Военная база",
                "Охраняемая территория. Нужен пропуск.",
                5, 10, 20,
                loot_table=[
                    {"item": "military_rations", "chance": 60, "min": 1, "max": 3},
                    {"item": "rifle_ammo", "chance": 70, "min": 10, "max": 30},
                    {"item": "pistol", "chance": 20, "min": 1, "max": 1},
                    {"item": "military_armor", "chance": 15, "min": 1, "max": 1},
                    {"item": "grenade", "chance": 10, "min": 1, "max": 2}
                ],
                enemies=["raider"],
                npcs=["general_stone", "quartermaster"]
            ),
            "sewer": Location(
                "sewer", "🌊 Канализация",
                "Темно, сыро и воняет. Водятся мутанты.",
                2, 6, 50,
                loot_table=[
                    {"item": "scrap", "chance": 60, "min": 2, "max": 5},
                    {"item": "mutant_organs", "chance": 40, "min": 1, "max": 2},
                    {"item": "old_coins", "chance": 30, "min": 5, "max": 20},
                    {"item": "flashlight", "chance": 20, "min": 1, "max": 1}
                ],
                enemies=["walker", "fatty", "mutant_rat"]
            ),
            "supermarket": Location(
                "supermarket", "🛒 Супермаркет",
                "Место, где можно найти еду и припасы.",
                1, 4, 40,
                loot_table=[
                    {"item": "food", "chance": 80, "min": 2, "max": 5},
                    {"item": "water", "chance": 80, "min": 2, "max": 5},
                    {"item": "batteries", "chance": 40, "min": 1, "max": 3},
                    {"item": "tools", "chance": 30, "min": 1, "max": 2},
                    {"item": "crowbar", "chance": 15, "min": 1, "max": 1}
                ],
                enemies=["walker", "raider"],
                npcs=["trader_joe"]
            ),
            "laboratory": Location(
                "laboratory", "🧪 Секретная лаборатория",
                "Здесь началась эпидемия. Очень опасно.",
                8, 15, 90,
                loot_table=[
                    {"item": "antidote", "chance": 30, "min": 1, "max": 1},
                    {"item": "formulas", "chance": 40, "min": 1, "max": 1},
                    {"item": "prototype_weapon", "chance": 10, "min": 1, "max": 1},
                    {"item": "rare_scrap", "chance": 50, "min": 2, "max": 5},
                    {"item": "hazmat_suit", "chance": 15, "min": 1, "max": 1}
                ],
                enemies=["spitter", "brute", "mutant"],
                npcs=["doctor_zed"]
            ),
            "forest": Location(
                "forest", "🌲 Лес",
                "Опасная зона с дикими зверями и беженцами.",
                1, 3, 25,
                loot_table=[
                    {"item": "berries", "chance": 70, "min": 2, "max": 6},
                    {"item": "wood", "chance": 60, "min": 2, "max": 5},
                    {"item": "herbs", "chance": 50, "min": 1, "max": 3},
                    {"item": "animal_hide", "chance": 30, "min": 1, "max": 2}
                ],
                enemies=["wolf", "bear", "wanderer"]
            ),
            "radio_tower": Location(
                "radio_tower", "📡 Радиовышка",
                "Можно поймать сигналы других выживших.",
                4, 7, 35,
                loot_table=[
                    {"item": "radio_parts", "chance": 50, "min": 1, "max": 2},
                    {"item": "batteries", "chance": 60, "min": 2, "max": 4},
                    {"item": "map_fragments", "chance": 30, "min": 1, "max": 1},
                    {"item": "signal_flare", "chance": 20, "min": 1, "max": 2}
                ],
                enemies=["runner", "screamer"],
                npcs=["radio_operator"]
            ),
            "cemetery": Location(
                "cemetery", "⚰️ Кладбище",
                "Место силы для некромантов и культистов.",
                3, 6, 55,
                loot_table=[
                    {"item": "bone", "chance": 80, "min": 2, "max": 5},
                    {"item": "skull", "chance": 40, "min": 1, "max": 2},
                    {"item": "ancient_coin", "chance": 30, "min": 1, "max": 3},
                    {"item": "cult_artifact", "chance": 10, "min": 1, "max": 1}
                ],
                enemies=["walker", "fatty", "cultist"],
                npcs=["gravedigger"]
            )
        }
    
    def create_npcs(self):
        return {
            "trader_joe": NPC(
                "trader_joe", "Торговец Джо",
                ["abandoned_shelter", "supermarket"],
                "Привет, путник! Хочешь купить или продать что-то?",
                shop={
                    "water": {"price": 3, "stock": 100},
                    "food": {"price": 5, "stock": 100},
                    "bandage": {"price": 10, "stock": 50},
                    "pistol": {"price": 100, "stock": 5},
                    "pistol_ammo": {"price": 2, "stock": 200}
                }
            ),
            "doctor_stein": NPC(
                "doctor_stein", "Доктор Штайн",
                ["hospital"],
                "Я лечил людей до эпидемии... Теперь лечу выживших.",
                quests=["find_medicine", "cure_infected"],
                shop={
                    "bandage": {"price": 8, "stock": 50},
                    "painkillers": {"price": 15, "stock": 30},
                    "antibiotics": {"price": 30, "stock": 20},
                    "first_aid_kit": {"price": 50, "stock": 10}
                }
            ),
            "general_stone": NPC(
                "general_stone", "Генерал Стоун",
                ["military_base"],
                "Военные держат оборону. Присоединяйся, если докажешь, что достоин.",
                quests=["clear_area", "supply_run"],
                shop={
                    "military_rations": {"price": 15, "stock": 50},
                    "rifle": {"price": 200, "stock": 3},
                    "rifle_ammo": {"price": 3, "stock": 100},
                    "grenade": {"price": 80, "stock": 10},
                    "military_armor": {"price": 250, "stock": 2}
                }
            ),
            "quartermaster": NPC(
                "quartermaster", "Каптенармус",
                ["military_base"],
                "Меняю припасы на услуги. Что нужно?",
                shop={
                    "backpack": {"price": 100, "stock": 5},
                    "night_vision": {"price": 300, "stock": 1},
                    "combat_knife": {"price": 80, "stock": 10},
                    "flare_gun": {"price": 120, "stock": 3}
                }
            ),
            "doctor_zed": NPC(
                "doctor_zed", "Доктор Зед",
                ["laboratory"],
                "Ты пришел за правдой? Или за смертью?",
                quests=["find_cure", "stop_zed"]
            ),
            "radio_operator": NPC(
                "radio_operator", "Радист",
                ["radio_tower"],
                "Я слышу сигналы со всего города. Могу рассказать, где безопасно.",
                quests=["find_transmitter", "rescue_survivors"]
            ),
            "gravedigger": NPC(
                "gravedigger", "Могильщик",
                ["cemetery"],
                "Мертвые не дают мне покоя... Они встают из могил.",
                quests=["clean_cemetery", "find_relic"]
            )
        }
    
    def create_quests(self):
        return {
            "first_steps": Quest(
                "first_steps", "Первые шаги",
                "Убей 3 зомби в руинах города",
                "kill", {"enemy": "walker", "count": 3},
                "bottlecaps", 50, 1, "find_shelter"
            ),
            "find_shelter": Quest(
                "find_shelter", "Найти убежище",
                "Найди безопасное место для ночлега",
                "explore", {"location": "abandoned_shelter"},
                "exp", 100, 1, "help_neighbor"
            ),
            "help_neighbor": Quest(
                "help_neighbor", "Помощь соседу",
                "Принеси 5 еды торговцу Джо",
                "collect", {"item": "food", "count": 5},
                "bottlecaps", 100, 2, None
            ),
            "clear_area": Quest(
                "clear_area", "Зачистка района",
                "Убей 10 зомби в любой локации",
                "kill", {"enemy": "zombie", "count": 10},
                "bottlecaps", 150, 3, "scout_hospital"
            ),
            "scout_hospital": Quest(
                "scout_hospital", "Разведка больницы",
                "Исследуй больницу и найди медикаменты",
                "collect", {"item": "first_aid_kit", "count": 2},
                "exp", 200, 4, "find_medicine"
            ),
            "find_medicine": Quest(
                "find_medicine", "Поиск лекарств",
                "Принеси доктору Штайну 3 антибиотика",
                "collect", {"item": "antibiotics", "count": 3},
                "bottlecaps", 200, 5, None
            ),
            "supply_run": Quest(
                "supply_run", "Поставка припасов",
                "Доставь 10 военных пайков на базу",
                "collect", {"item": "military_rations", "count": 10},
                "reputation_military", 50, 6, "join_military"
            ),
            "join_military": Quest(
                "join_military", "Вступление в армию",
                "Поговори с генералом Стоуном",
                "talk", {"npc": "general_stone"},
                "bottlecaps", 300, 7, None
            ),
            "find_cure": Quest(
                "find_cure", "В поисках лекарства",
                "Найди формулу лекарства в лаборатории",
                "collect", {"item": "antidote_recipe", "count": 1},
                "legendary_weapon", 1, 10, "stop_zed"
            ),
            "stop_zed": Quest(
                "stop_zed", "Остановить Доктора Зеда",
                "Победи Доктора Зеда в его лаборатории",
                "kill", {"enemy": "boss_doctor", "count": 1},
                "bottlecaps", 1000, 12, None
            ),
            "clean_cemetery": Quest(
                "clean_cemetery", "Очистка кладбища",
                "Убей 15 зомби на кладбище",
                "kill", {"enemy": "zombie", "count": 15, "location": "cemetery"},
                "cult_reputation", 30, 4, "find_relic"
            ),
            "find_relic": Quest(
                "find_relic", "Древний артефакт",
                "Найди древний артефакт в склепе",
                "collect", {"item": "cult_artifact", "count": 1},
                "rare_weapon", 1, 6, None
            ),
            "rescue_survivors": Quest(
                "rescue_survivors", "Спасение выживших",
                "Найди и спаси 3 группы выживших",
                "rescue", {"count": 3},
                "reputation_survivors", 100, 5, "build_community"
            ),
            "build_community": Quest(
                "build_community", "Постройка общины",
                "Собери 100 дерева и 50 металла для постройки общежития",
                "collect", {"item": "wood", "count": 100},
                "shelter_upgrade", 1, 8, None
            )
        }
    
    def create_achievements(self):
        return {
            "first_kill": Achievement(
                "first_kill", "Первая кровь",
                "Убей своего первого зомби",
                {"kills": {"zombie": 1}},
                "bottlecaps", 20
            ),
            "zombie_hunter": Achievement(
                "zombie_hunter", "Охотник на зомби",
                "Убей 100 зомби",
                {"kills": {"zombie": 100}},
                "bottlecaps", 500
            ),
            "zombie_slayer": Achievement(
                "zombie_slayer", "Истребитель зомби",
                "Убей 1000 зомби",
                {"kills": {"zombie": 1000}},
                "legendary_weapon", 1
            ),
            "survivor_10": Achievement(
                "survivor_10", "Выживший",
                "Проживи 10 дней",
                {"days": 10},
                "bottlecaps", 100
            ),
            "survivor_100": Achievement(
                "survivor_100", "Ветеран",
                "Проживи 100 дней",
                {"days": 100},
                "rare_armor", 1
            ),
            "rich": Achievement(
                "rich", "Богач",
                "Накопи 1000 крышек",
                {"wealth": 1000},
                "bottlecaps", 200
            ),
            "millionaire": Achievement(
                "millionaire", "Миллионер",
                "Накопи 10000 крышек",
                {"wealth": 10000},
                "legendary_item", 1
            ),
            "explorer": Achievement(
                "explorer", "Исследователь",
                "Посети все локации",
                {"locations_visited": 10},
                "bottlecaps", 300
            ),
            "hero": Achievement(
                "hero", "Герой",
                "Выполни 50 квестов",
                {"quests_completed": 50},
                "unique_title", "Герой"
            ),
            "craftsman": Achievement(
                "craftsman", "Мастер на все руки",
                "Создай 100 предметов",
                {"items_crafted": 100},
                "bottlecaps", 500
            ),
            "trader": Achievement(
                "trader", "Торговец",
                "Соверши 50 сделок",
                {"trades": 50},
                "bottlecaps", 300
            ),
            "boss_killer": Achievement(
                "boss_killer", "Убийца боссов",
                "Победи всех боссов",
                {"bosses_defeated": 2},
                "legendary_item", 1
            )
        }
    
    def create_items_db(self):
        return {
            # Оружие
            "pipe": Weapon("pipe", "🔧 Труба", 5, "melee", 20, 3, 10, ItemRarity.COMMON),
            "bat": Weapon("bat", "🏏 Бита", 8, "melee", 30, 4, 25, ItemRarity.COMMON),
            "crowbar": Weapon("crowbar", "🔧 Монтировка", 12, "melee", 40, 4, 40, ItemRarity.COMMON),
            "machete": Weapon("machete", "🔪 Мачете", 15, "melee", 40, 3, 50, ItemRarity.UNCOMMON),
            "axe": Weapon("axe", "🪓 Топор", 20, "melee", 50, 5, 80, ItemRarity.UNCOMMON),
            "chainsaw": Weapon("chainsaw", "⛓️ Бензопила", 35, "melee", 30, 8, 200, ItemRarity.RARE, special_effects={"bleed": 5}),
            "katana": Weapon("katana", "⚔️ Катана", 40, "melee", 60, 4, 300, ItemRarity.RARE, special_effects={"crit": 20}),
            
            # Огнестрельное
            "pistol": Weapon("pistol", "🔫 Пистолет", 15, "medium", 100, 2, 100, ItemRarity.COMMON, ammo_type="pistol_ammo"),
            "revolver": Weapon("revolver", "🔫 Револьвер", 25, "medium", 80, 3, 150, ItemRarity.UNCOMMON, ammo_type="pistol_ammo"),
            "shotgun": Weapon("shotgun", "🔫 Дробовик", 30, "short", 80, 4, 150, ItemRarity.UNCOMMON, ammo_type="shotgun_ammo", ammo_per_shot=2),
            "rifle": Weapon("rifle", "🔫 Винтовка", 25, "long", 90, 5, 200, ItemRarity.RARE, ammo_type="rifle_ammo"),
            "sniper": Weapon("sniper", "🔫 Снайперка", 50, "very_long", 70, 6, 300, ItemRarity.RARE, ammo_type="sniper_ammo"),
            "smg": Weapon("smg", "🔫 Пистолет-пулемёт", 12, "medium", 60, 3, 180, ItemRarity.UNCOMMON, ammo_type="smg_ammo", ammo_per_shot=3),
            "assault_rifle": Weapon("assault_rifle", "🔫 Автомат", 20, "medium", 120, 5, 280, ItemRarity.RARE, ammo_type="rifle_ammo", ammo_per_shot=2),
            
            # Броня
            "leather_jacket": Armor("leather_jacket", "🧥 Кожанка", 5, 30, 3, 30, ItemRarity.COMMON),
            "police_vest": Armor("police_vest", "🛡️ Бронежилет", 15, 50, 5, 100, ItemRarity.UNCOMMON),
            "military_armor": Armor("military_armor", "🛡️ Военная броня", 25, 80, 8, 250, ItemRarity.RARE),
            "hazmat_suit": Armor("hazmat_suit", "🧪 Защитный костюм", 10, 40, 4, 150, ItemRarity.RARE, special_effects={"radiation_protection": 90}),
            "combat_armor": Armor("combat_armor", "⚔️ Боевая броня", 35, 100, 10, 400, ItemRarity.EPIC),
            "power_armor": Armor("power_armor", "💪 Силовая броня", 60, 200, 20, 1000, ItemRarity.LEGENDARY),
            
            # Шлемы
            "cap": Armor("cap", "🧢 Кепка", 2, 20, 1, 10, ItemRarity.COMMON),
            "helmet": Armor("helmet", "⛑️ Каска", 8, 40, 2, 50, ItemRarity.UNCOMMON),
            "military_helmet": Armor("military_helmet", "🎖️ Военный шлем", 15, 60, 3, 120, ItemRarity.RARE),
            
            # Расходники
            "bandage": Consumable("bandage", "🩹 Бинт", "heal", 20, 0.5, 10, ItemRarity.COMMON),
            "first_aid_kit": Consumable("first_aid_kit", "💊 Аптечка", "heal", 50, 1, 30, ItemRarity.UNCOMMON),
            "painkillers": Consumable("painkillers", "💊 Обезбол", "heal", 15, 0.2, 15, ItemRarity.COMMON),
            "antibiotics": Consumable("antibiotics", "💊 Антибиотики", "cure_infection", 100, 0.3, 40, ItemRarity.RARE),
            "antidote": Consumable("antidote", "🧪 Антидот", "cure_radiation", 100, 0.5, 80, ItemRarity.RARE),
            "energy_drink": Consumable("energy_drink", "🥤 Энергетик", "energy", 30, 0.3, 15, ItemRarity.UNCOMMON),
            
            # Еда и вода
            "food": Consumable("food", "🍗 Еда", "food", 20, 0.5, 5, ItemRarity.COMMON),
            "water": Consumable("water", "💧 Вода", "water", 20, 0.5, 3, ItemRarity.COMMON),
            "canned_food": Consumable("canned_food", "🥫 Консервы", "food", 40, 0.8, 10, ItemRarity.UNCOMMON),
            "military_rations": Consumable("military_rations", "📦 Военный паёк", "both", 30, 0.8, 15, ItemRarity.UNCOMMON),
            "berries": Consumable("berries", "🍓 Ягоды", "food", 5, 0.1, 1, ItemRarity.COMMON),
            
            # Боеприпасы
            "pistol_ammo": {"id": "pistol_ammo", "name": "🔫 9mm патроны", "type": "ammo", "weight": 0.1, "stackable": True},
            "rifle_ammo": {"id": "rifle_ammo", "name": "🔫 5.56mm патроны", "type": "ammo", "weight": 0.15, "stackable": True},
            "shotgun_ammo": {"id": "shotgun_ammo", "name": "🔫 12ga патроны", "type": "ammo", "weight": 0.2, "stackable": True},
            "sniper_ammo": {"id": "sniper_ammo", "name": "🔫 7.62mm патроны", "type": "ammo", "weight": 0.2, "stackable": True},
            "smg_ammo": {"id": "smg_ammo", "name": "🔫 .45 патроны", "type": "ammo", "weight": 0.1, "stackable": True},
            
            # Материалы
            "scrap": {"id": "scrap", "name": "🔩 Металлолом", "type": "material", "weight": 0.5, "stackable": True},
            "wood": {"id": "wood", "name": "🪵 Древесина", "type": "material", "weight": 0.5, "stackable": True},
            "cloth": {"id": "cloth", "name": "🧵 Ткань", "type": "material", "weight": 0.2, "stackable": True},
            "leather": {"id": "leather", "name": "🧶 Кожа", "type": "material", "weight": 0.3, "stackable": True},
            "weapon_parts": {"id": "weapon_parts", "name": "🔧 Запчасти для оружия", "type": "material", "weight": 0.3, "stackable": True},
            "electronics": {"id": "electronics", "name": "💻 Электроника", "type": "material", "weight": 0.2, "stackable": True},
            "rare_scrap": {"id": "rare_scrap", "name": "✨ Редкий металл", "type": "material", "weight": 0.3, "stackable": True},
            
            # Лут с зомби
            "rotten_flesh": {"id": "rotten_flesh", "name": "🧟 Гнилая плоть", "type": "misc", "weight": 0.3, "stackable": True},
            "rags": {"id": "rags", "name": "🧵 Тряпки", "type": "material", "weight": 0.1, "stackable": True},
            "fat": {"id": "fat", "name": "🧈 Жир", "type": "misc", "weight": 0.2, "stackable": True},
            "acid_gland": {"id": "acid_gland", "name": "🧪 Кислотная железа", "type": "material", "weight": 0.2, "stackable": True},
            "vocal_cords": {"id": "vocal_cords", "name": "🎤 Голосовые связки", "type": "misc", "weight": 0.1, "stackable": True},
            "zombie_heart": {"id": "zombie_heart", "name": "💓 Сердце зомби", "type": "misc", "weight": 0.5, "stackable": True},
            "crown": {"id": "crown", "name": "👑 Король зомби", "type": "artifact", "weight": 0.5, "stackable": False},
            
            # Квестовые предметы
            "lab_key": {"id": "lab_key", "name": "🔑 Ключ от лаборатории", "type": "quest", "weight": 0.1, "stackable": False},
            "antidote_recipe": {"id": "antidote_recipe", "name": "📜 Рецепт антидота", "type": "quest", "weight": 0.1, "stackable": False},
            "cure_vial": {"id": "cure_vial", "name": "🧪 Пробирка с лекарством", "type": "quest", "weight": 0.2, "stackable": False},
            "cult_artifact": {"id": "cult_artifact", "name": "🔮 Артефакт культа", "type": "artifact", "weight": 0.3, "stackable": False},
            "map_fragments": {"id": "map_fragments", "name": "🗺️ Фрагменты карты", "type": "quest", "weight": 0.1, "stackable": True},
            
            # Гранаты
            "grenade": {"id": "grenade", "name": "💣 Граната", "type": "throwable", "damage": 70, "weight": 1, "price": 80, "stackable": True},
            "molotov": {"id": "molotov", "name": "🔥 Коктейль Молотова", "type": "throwable", "damage": 40, "weight": 1, "price": 30, "stackable": True},
            "stun_grenade": {"id": "stun_grenade", "name": "⚡ Светошумовая", "type": "throwable", "effect": "stun", "weight": 1, "price": 50, "stackable": True},
            
            # Редкие и легендарные
            "prototype_weapon": Weapon("prototype_weapon", "⚡ Прототип плазмы", 80, "long", 50, 3, 800, ItemRarity.LEGENDARY, special_effects={"plasma": True}),
            "legendary_weapon": Weapon("legendary_weapon", "👑 Легендарный меч", 100, "melee", 200, 5, 1000, ItemRarity.LEGENDARY, special_effects={"vampire": 10}),
            "unique_title": {"id": "unique_title", "name": "🏷️ Уникальный титул", "type": "title", "weight": 0, "stackable": False}
        }
    
    def create_events(self):
        return [
            Event("full_moon", "🌕 Полнолуние", "Зомби становятся сильнее и агрессивнее", 24, {"enemy_damage": 1.5, "spawn_rate": 2.0}),
            Event("supply_drop", "📦 Припасы с неба", "Военные сбрасывают припасы в случайных местах", 6, {"loot_multiplier": 2.0}),
            Event("raider_attack", "⚔️ Атака рейдеров", "Рейдеры нападают на всех выживших", 12, {"combat_frequency": 3.0}),
            Event("radiation_storm", "☢️ Радиационная буря", "Радиация повышается во всех локациях", 8, {"radiation": 10}),
            Event("healing_rain", "🌧️ Целебный дождь", "Медленно восстанавливает здоровье на улице", 4, {"health_regen": 2}),
            Event("zombie_horde", "🧟 Орда зомби", "Огромная орда движется через город", 24, {"enemy_count": 3.0}),
            Event("trader_caravan", "🐪 Караван торговцев", "Торговцы предлагают редкие товары", 8, {"shop_discount": 0.7}),
            Event("holiday", "🎉 Праздник", "Все выжившие получают бонусы", 24, {"exp_multiplier": 2.0, "loot_multiplier": 1.5}),
            Event("scientist_research", "🧪 Научные исследования", "Ученые ищут добровольцев", 12, {"quest_rewards": 2.0}),
            Event("darkness", "🌑 Затмение", "Тьма окутала город, зомби невидимы", 6, {"visibility": 0.3})
        ]
    
    async def process_game_time(self):
        """Обработка игрового времени"""
        now = datetime.now()
        minutes_passed = (now - self.last_time_update).total_seconds() / 60
        
        if minutes_passed >= 60:  # Каждый час реального времени = игровой день
            self.game_day += 1
            self.last_time_update = now
            
            # Эффекты от событий
            if self.current_event:
                await self.apply_event_effects()
            
            # Обновление игроков
            for player in self.players.values():
                player.days_survived += 1
                player.regenerate_energy()
                player.increase_hunger_thirst()
                
                # Проверка достижений
                await self.check_achievements(player)
    
    async def apply_event_effects(self):
        """Применение эффектов ивента"""
        if not self.current_event:
            return
        
        event = self.current_event
        for player in self.players.values():
            # Уведомление игроков
            try:
                # Будет отправлено через бота
                pass
            except:
                pass
    
    async def check_events(self):
        """Проверка и запуск событий"""
        if self.current_event and self.current_event.end_time and datetime.now() > self.current_event.end_time:
            self.current_event = None
            # Уведомление о завершении ивента
        
        if not self.current_event and random.random() < 0.3:  # 30% шанс каждый час
            event = random.choice(self.event_schedule)
            event.start_time = datetime.now()
            event.end_time = datetime.now() + timedelta(hours=event.duration)
            self.current_event = event
            
            # Уведомление о начале ивента
            await self.broadcast_event(event)
    
    async def broadcast_event(self, event):
        """Рассылка уведомления о событии всем игрокам"""
        # Будет реализовано через бота
        pass
    
    async def check_achievements(self, player):
        """Проверка достижений игрока"""
        for ach_id, achievement in self.achievements.items():
            if ach_id in player.achievements:
                continue
            
            condition = achievement.condition
            unlocked = False
            
            if 'kills' in condition:
                for enemy_type, count in condition['kills'].items():
                    if player.kills.get(enemy_type, 0) >= count:
                        unlocked = True
            
            elif 'days' in condition:
                if player.days_survived >= condition['days']:
                    unlocked = True
            
            elif 'wealth' in condition:
                if player.money['bottlecaps'] >= condition['wealth']:
                    unlocked = True
            
            elif 'quests_completed' in condition:
                if len(player.completed_quests) >= condition['quests_completed']:
                    unlocked = True
            
            if unlocked:
                player.achievements.append(ach_id)
                # Награда
                if achievement.reward_type == "bottlecaps":
                    player.money['bottlecaps'] += achievement.reward_amount
                # Уведомление будет отправлено через бота
    
    def update_leaderboards(self):
        """Обновление лидербордов"""
        players_list = list(self.players.values())
        
        self.leaderboards['level'] = sorted(players_list, key=lambda p: (p.level, p.exp), reverse=True)[:10]
        self.leaderboards['kills'] = sorted(players_list, key=lambda p: p.kills['zombie'], reverse=True)[:10]
        self.leaderboards['wealth'] = sorted(players_list, key=lambda p: p.money['bottlecaps'], reverse=True)[:10]
        self.leaderboards['days'] = sorted(players_list, key=lambda p: p.days_survived, reverse=True)[:10]
        
        clans_list = list(self.clans.values())
        self.leaderboards['clans'] = sorted(clans_list, key=lambda c: (c.level, c.exp), reverse=True)[:10]
    
    async def save_all_players(self):
        """Сохранение всех игроков в БД"""
        for user_id, player in self.players.items():
            self.db.save_player(user_id, player.username, player)
            self.db.save_inventory(user_id, player.inventory)
    
    def get_player(self, user_id, username=None):
        """Получение игрока (из памяти или БД)"""
        if user_id in self.players:
            return self.players[user_id]
        
        # Загружаем из БД
        data = self.db.load_player(user_id)
        if data:
            player = Survivor(user_id, data['username'])
            # Восстанавливаем данные
            player.level = data['level']
            player.days_survived = data['days_survived']
            player.kills['zombie'] = data['kills']
            
            stats_data = data['data'].get('stats', {})
            for stat, value in stats_data.items():
                if stat in player.stats:
                    player.stats[stat] = value
            
            player.money.update(data['data'].get('money', {}))
            player.location = data['data'].get('location', 'abandoned_shelter')
            player.shelter_level = data['data'].get('shelter_level', 1)
            player.quests = data['data'].get('quests', [])
            player.achievements = data['data'].get('achievements', [])
            player.reputation.update(data['reputation'])
            player.radiation = data['data'].get('radiation', 0)
            player.hunger = data['data'].get('hunger', 0)
            player.thirst = data['data'].get('thirst', 0)
            player.energy = data['data'].get('energy', 100)
            player.max_energy = data['data'].get('max_energy', 100)
            
            # Загружаем инвентарь
            player.inventory = self.db.load_inventory(user_id)
            
            self.players[user_id] = player
            return player
        
        # Новый игрок
        if username:
            player = Survivor(user_id, username)
            self.players[user_id] = player
            self.total_players_registered += 1
            return player
        
        return None

# ============================================
# ГЛОБАЛЬНЫЙ ОБЪЕКТ ИГРЫ
# ============================================

game = ZombieGame()

# ============================================
# КЛАВИАТУРЫ
# ============================================

def get_main_keyboard():
    keyboard = [
        ["🧟 В бой", "🗺️ Исследовать"],
        ["👤 Профиль", "🎒 Инвентарь"],
        ["🏪 Торговец", "🔧 Крафт"],
        ["🏠 Убежище", "📊 Топы"],
        ["🎁 Кейсы", "🤝 Кланы"],
        ["❓ Помощь", "📅 Ивенты"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_battle_keyboard():
    keyboard = [
        ["⚔️ Атака", "🔫 Стрелять"],
        ["💊 Лечиться", "🏃 Убежать"],
        ["🎒 Инвентарь", "📊 Статус"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_shelter_keyboard():
    keyboard = [
        ["😴 Отдых", "📦 Хранилище"],
        ["🔧 Улучшить убежище", "🍳 Приготовить еду"],
        ["📋 Квесты", "◀️ Назад"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_clan_keyboard():
    keyboard = [
        ["🏠 База клана", "👥 Участники"],
        ["⚔️ Войны кланов", "📊 Рейтинг"],
        ["💰 Казна", "📋 Задания"],
        ["◀️ Назад"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_trader_keyboard():
    keyboard = [
        ["💰 Купить", "💸 Продать"],
        ["📋 Ассортимент", "◀️ Назад"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_craft_keyboard():
    keyboard = [
        ["🔧 Оружие", "🛡️ Броня"],
        ["💊 Расходники", "🏠 Убежище"],
        ["📋 Рецепты", "◀️ Назад"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_empty_keyboard():
    return ReplyKeyboardMarkup([[]], resize_keyboard=True)

# ============================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню"""
    user_id = update.effective_user.id
    username = update.effective_user.username or f"Player_{user_id}"
    chat_id = update.effective_chat.id
    
    # Проверка на приватный чат
    if chat_id != user_id:
        await update.message.reply_text(
            "🧟 *Зомби Апокалипсис RPG*\n\n"
            "Бот работает только в личных сообщениях!\n"
            "Напиши мне в личку: @ZombieApocalypseBot",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Получаем игрока
    player = game.get_player(user_id, username)
    
    # Проверка на активную игру
    if player.state != GameState.MENU:
        await update.message.reply_text(
            "🎮 Ты сейчас в игре! Вернись в меню через '◀️ Назад'",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Приветствие
    welcome_text = (
        f"🧟 *ЗОМБИ АПОКАЛИПСИС RPG v3.0*\n\n"
        f"*Добро пожаловать, {username}!*\n\n"
        f"Мир пал. Вирус Z-29 превратил большую часть населения в зомби.\n"
        f"Ты - один из немногих выживших. Твоя цель - выжить, найти убежище,\n"
        f"объединиться с другими и узнать правду о происхождении вируса.\n\n"
        f"📅 *День {game.game_day}* | 🕐 {game.game_hour}:00\n"
        f"📍 Локация: {game.locations[player.location].name}\n\n"
        f"📊 *Твой статус:*\n"
        f"❤️ HP: {player.health}/{player.max_health}\n"
        f"⚡ Энергия: {player.energy}/{player.max_energy}\n"
        f"📈 Уровень: {player.level} (опыт: {player.exp}/{player.exp_to_next})\n"
        f"💰 Крышки: {player.money['bottlecaps']}\n"
        f"🗡️ Убито зомби: {player.kills['zombie']}\n\n"
        f"*Используй кнопки ниже для действий!*"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Проверка достижений
    await game.check_achievements(player)
    
    # Сохраняем в БД
    game.db.save_player(user_id, username, player)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or f"Player_{user_id}"
    chat_id = update.effective_chat.id
    
    # Проверка на приватный чат
    if chat_id != user_id:
        return
    
    # Получаем игрока
    player = game.get_player(user_id, username)
    if not player:
        await start(update, context)
        return
    
    # Обновляем состояние игрока (голод, энергия и т.д.)
    player.regenerate_energy()
    player.increase_hunger_thirst()
    
    # Обработка в зависимости от состояния
    if player.state == GameState.IN_BATTLE:
        await handle_battle_action(update, context, player, text)
    elif player.state == GameState.TRADING:
        await handle_trading_action(update, context, player, text)
    elif player.state == GameState.CRAFTING:
        await handle_crafting_action(update, context, player, text)
    elif player.state == GameState.SHELTER:
        await handle_shelter_action(update, context, player, text)
    elif player.state == GameState.CLAN:
        await handle_clan_action(update, context, player, text)
    else:
        await handle_main_menu(update, context, player, text)

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, player, text):
    """Обработка главного меню"""
    
    if text == "🧟 В бой":
        await start_battle(update, context, player)
    
    elif text == "🗺️ Исследовать":
        await explore(update, context, player)
    
    elif text == "👤 Профиль":
        await show_profile(update, context, player)
    
    elif text == "🎒 Инвентарь":
        await show_inventory(update, context, player)
    
    elif text == "🏪 Торговец":
        await show_trader(update, context, player)
    
    elif text == "🔧 Крафт":
        await show_crafting(update, context, player)
    
    elif text == "🏠 Убежище":
        await show_shelter(update, context, player)
    
    elif text == "📊 Топы":
        await show_leaderboard(update, context)
    
    elif text == "🎁 Кейсы":
        await show_lootboxes(update, context, player)
    
    elif text == "🤝 Кланы":
        await show_clans(update, context, player)
    
    elif text == "📅 Ивенты":
        await show_events(update, context, player)
    
    elif text == "❓ Помощь":
        await show_help(update, context, player)
    
    else:
        await update.message.reply_text(
            "Используй кнопки меню!",
            reply_markup=get_main_keyboard()
        )

async def start_battle(update: Update, context: ContextTypes.DEFAULT_TYPE, player):
    """Начало боя"""
    # Проверка энергии
    if not player.use_energy(10):
        await update.message.reply_text(
            "❌ Недостаточно энергии! Отдохни в убежище.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Выбор врага в зависимости от локации
    location = game.locations[player.location]
    if not location.enemies:
        await update.message.reply_text(
            "❌ Здесь нет врагов! Исследуй другое место.",
            reply_markup=get_main_keyboard()
        )
        return
    
    enemy_type = random.choice(location.enemies)
    enemy = Enemy(enemy_type, player.level)
    
    # Сохраняем врага
    game.active_battles[player.user_id] = enemy
    player.state = GameState.IN_BATTLE
    player.current_enemy = enemy
    
    # Применяем эффекты ивента
    if game.current_event and 'enemy_damage' in game.current_event.effects:
        enemy.damage *= game.current_event.effects['enemy_damage']
    
    battle_text = (
        f"{enemy.image} *ВРАГ!*\n\n"
        f"Ты встретил: *{enemy.name}*\n"
        f"{enemy.description}\n\n"
        f"❤️ HP врага: {enemy.hp}\n"
        f"⚔️ Урон: {enemy.damage}\n"
        f"📊 Уровень: {enemy.level}\n\n"
        f"⚡ Энергия: {player.energy}/100\n"
        f"❤️ Твое HP: {player.health}/{player.max_health}\n\n"
        f"*Что будешь делать?*"
    )
    
    await update.message.reply_text(
        battle_text,
        reply_markup=get_battle_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    
    game.total_battles += 1
    game.db.log_action(player.user_id, "battle_start", {"enemy": enemy_type, "level": enemy.level})

async def handle_battle_action(update: Update, context: ContextTypes.DEFAULT_TYPE, player, action):
    """Обработка действий в бою"""
    enemy = player.current_enemy
    if not enemy:
        player.state = GameState.MENU
        await update.message.reply_text(
            "❌ Бой закончился!",
            reply_markup=get_main_keyboard()
        )
        return
    
    result_text = ""
    
    if action == "⚔️ Атака":
        # Ближний бой
        hit_chance = 50 + player.stats["agility"] * 2
        if random.randint(1, 100) <= hit_chance:
            # Расчет урона
            weapon_damage = 5
            if player.equipment["weapon"]:
                weapon_damage = player.equipment["weapon"].get('damage', 5)
            
            damage = weapon_damage + player.stats["strength"] * 2
            crit_chance = player.stats["luck"] * 2
            if random.randint(1, 100) <= crit_chance:
                damage *= 2
                result_text = f"⚔️ *КРИТ!* Ты нанес *{damage}* урона!"
            else:
                result_text = f"⚔️ Ты нанес *{damage}* урона!"
            
            enemy.hp -= damage
            
            # Износ оружия
            if player.equipment["weapon"] and random.random() < 0.1:
                player.equipment["weapon"]['durability'] -= 1
                if player.equipment["weapon"]['durability'] <= 0:
                    player.equipment["weapon"] = None
                    result_text += "\n🔧 Твое оружие сломалось!"
        else:
            result_text = "❌ Промах!"
    
    elif action == "🔫 Стрелять":
        # Дальний бой
        if player.money["bullets"] > 0:
            player.money["bullets"] -= 1
            hit_chance = 40 + player.stats["perception"] * 3
            if random.randint(1, 100) <= hit_chance:
                damage = 15 + player.stats["perception"] * 3
                enemy.hp -= damage
                result_text = f"🔫 Попадание! *{damage}* урона! (-1 патрон)"
            else:
                result_text = f"🔫 Промах! (-1 патрон)"
        else:
            result_text = "❌ Нет патронов! Используй ближний бой."
    
    elif action == "💊 Лечиться":
        # Поиск аптечки в инвентаре
        healed = False
        for item in player.inventory:
            if item.get('type') == 'consumable' and item.get('effect_type') == 'heal':
                player.heal(item['effect_value'])
                player.inventory.remove(item)
                result_text = f"💊 Ты использовал {item['name']} и восстановил {item['effect_value']} HP"
                healed = True
                break
        
        if not healed:
            result_text = "❌ Нет аптечек!"
    
    elif action == "🏃 Убежать":
        escape_chance = 30 + player.stats["agility"] * 3
        if random.randint(1, 100) <= escape_chance:
            player.state = GameState.MENU
            del game.active_battles[player.user_id]
            await update.message.reply_text(
                "🏃 Ты убежал!",
                reply_markup=get_main_keyboard()
            )
            return
        else:
            result_text = "❌ Не удалось убежать!"
    
    elif action == "🎒 Инвентарь":
        await show_inventory(update, context, player)
        return
    
    elif action == "📊 Статус":
        status_text = (
            f"📊 *Статус боя*\n\n"
            f"*Ты:*\n"
            f"❤️ HP: {player.health}/{player.max_health}\n"
            f"⚡ Энергия: {player.energy}\n"
            f"🔫 Патроны: {player.money['bullets']}\n\n"
            f"*Враг:*\n"
            f"{enemy.image} {enemy.name}\n"
            f"❤️ HP: {enemy.hp}/{enemy.max_hp}\n"
            f"⚔️ Урон: {enemy.damage}"
        )
        await update.message.reply_text(
            status_text,
            reply_markup=get_battle_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Ход врага
    if enemy.hp > 0:
        # Шанс попадания врага
        enemy_hit_chance = 70
        if random.randint(1, 100) <= enemy_hit_chance:
            damage_taken = player.take_damage(enemy.damage)
            result_text += f"\n👾 {enemy.name} атакует и наносит *{damage_taken:.0f}* урона!"
    
    await update.message.reply_text(result_text, parse_mode=ParseMode.MARKDOWN)
    
    # Проверка на победу
    if enemy.hp <= 0:
        # Награда
        exp_gain = enemy.exp_reward
        caps_gain = random.randint(5, 15) * player.level
        
        player.add_exp(exp_gain)
        player.money["bottlecaps"] += caps_gain
        player.kills["zombie"] += 1
        game.total_kills += 1
        
        # Лут
        loot_text = ""
        for loot in enemy.loot_table:
            if random.randint(1, 100) <= loot['chance']:
                quantity = random.randint(loot['min'], loot['max'])
                item = game.items_db.get(loot['item'])
                if item:
                    if isinstance(item, dict):
                        item_copy = item.copy()
                        item_copy['quantity'] = quantity
                    else:
                        item_copy = {'id': loot['item'], 'name': str(loot['item']), 'quantity': quantity}
                    
                    player.add_item(item_copy)
                    loot_text += f"• {item_copy['name']} x{quantity}\n"
        
        # Проверка на уровень
        level_up_text = ""
        if player.exp >= player.exp_to_next:
            level_up_text = f"\n✨ *НОВЫЙ УРОВЕНЬ!* Теперь ты {player.level}!"
        
        del game.active_battles[player.user_id]
        player.state = GameState.MENU
        
        await update.message.reply_text(
            f"🎉 *ПОБЕДА!*\n\n"
            f"✨ Опыт: +{exp_gain}\n"
            f"💰 Крышки: +{caps_gain}\n"
            f"📦 Лут:\n{loot_text}"
            f"{level_up_text}",
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Квесты
        await check_quest_progress(player, "kill", enemy.type)
    
    # Проверка на смерть игрока
    elif player.health <= 0:
        player.health = player.max_health // 2
        player.money["bottlecaps"] = max(10, player.money["bottlecaps"] // 2)
        del game.active_battles[player.user_id]
        player.state = GameState.MENU
        
        await update.message.reply_text(
            f"💀 *ТЫ ПОГИБ...*\n\n"
            f"Но каким-то чудом очнулся в убежище.\n"
            f"Потеряно половина крышек: *{player.money['bottlecaps']}* осталось",
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )

async def explore(update: Update, context: ContextTypes.DEFAULT_TYPE, player):
    """Исследование локации"""
    # Проверка энергии
    if not player.use_energy(15):
        await update.message.reply_text(
            "❌ Недостаточно энергии! Отдохни в убежище.",
            reply_markup=get_main_keyboard()
        )
        return
    
    location = game.locations[player.location]
    
    # Поиск лута
    loot_text = ""
    found_items = []
    
    for loot in location.loot_table:
        if random.randint(1, 100) <= loot['chance']:
            quantity = random.randint(loot['min'], loot['max'])
            item = game.items_db.get(loot['item'])
            if item:
                if isinstance(item, dict):
                    item_copy = item.copy()
                    item_copy['quantity'] = quantity
                else:
                    item_copy = {'id': loot['item'], 'name': str(loot['item']), 'quantity': quantity}
                
                success, msg = player.add_item(item_copy)
                if success:
                    found_items.append(f"• {item_copy['name']} x{quantity}")
    
    # Случайная встреча с врагом
    encounter_chance = location.danger
    if game.current_event and 'spawn_rate' in game.current_event.effects:
        encounter_chance *= game.current_event.effects['spawn_rate']
    
    encounter_text = ""
    if random.randint(1, 100) <= encounter_chance:
        encounter_text = "\n\n⚠️ Ты заметил движение... Приготовься к бою!"
        player.state = GameState.EXPLORING
        # Будет запущен бой после исследования
    
    result_text = (
        f"🗺️ *Исследование {location.name}*\n\n"
        f"{location.description}\n\n"
        f"*Найдено:*\n" + ("\n".join(found_items) if found_items else "Ничего не найдено")
        f"{encounter_text}"
    )
    
    await update.message.reply_text(
        result_text,
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    
    if encounter_text:
        await start_battle(update, context, player)

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, player):
    """Показать профиль игрока"""
    # Расчет веса
    player.calculate_current_weight()
    
    # Статистика
    kill_stats = "\n".join([f"  {k}: {v}" for k, v in player.kills.items() if v > 0])
    
    # Репутация
    rep_text = ""
    for faction, value in player.reputation.items():
        if value > 0:
            rep_text += f"  {faction}: +{value}\n"
        elif value < 0:
            rep_text += f"  {faction}: {value}\n"
    
    # Квесты
    quest_text = f"Активных: {len(player.quests)} | Выполнено: {len(player.completed_quests)}"
    
    # Достижения
    ach_text = f"Получено: {len(player.achievements)}"
    
    profile_text = (
        f"👤 *ПРОФИЛЬ ВЫЖИВШЕГО*\n\n"
        f"*@{player.username}*\n\n"
        f"📊 *ОСНОВНОЕ*\n"
        f"Уровень: {player.level} (опыт: {player.exp}/{player.exp_to_next})\n"
        f"Дней выживания: {player.days_survived}\n"
        f"Стат поинтов: {player.stat_points}\n\n"
        f"❤️ *ЗДОРОВЬЕ*\n"
        f"HP: {player.health}/{player.max_health}\n"
        f"Голод: {player.hunger}% | Жажда: {player.thirst}%\n"
        f"Радиация: {player.radiation}%\n"
        f"Энергия: {player.energy}/{player.max_energy}\n\n"
        f"📈 *ХАРАКТЕРИСТИКИ*\n"
        f"💪 Сила: {player.stats['strength']}\n"
        f"🏃 Ловкость: {player.stats['agility']}\n"
        f"👀 Восприятие: {player.stats['perception']}\n"
        f"💪 Выносливость: {player.stats['endurance']}\n"
        f"🧠 Интеллект: {player.stats['intelligence']}\n"
        f"🍀 Удача: {player.stats['luck']}\n\n"
        f"💰 *РЕСУРСЫ*\n"
        f"Крышки: {player.money['bottlecaps']}\n"
        f"Патроны: {player.money['bullets']}\n"
        f"Еда: {player.money['food']}\n"
        f"Вода: {player.money['water']}\n"
        f"Медикаменты: {player.money['meds']}\n"
        f"Металлолом: {player.money['scrap']}\n\n"
        f"🗡️ *УБИЙСТВА*\n{kill_stats}\n\n"
        f"🏷️ *РЕПУТАЦИЯ*\n{rep_text if rep_text else '  Нейтрален ко всем'}\n\n"
        f"📋 *КВЕСТЫ*\n{quest_text}\n\n"
        f"🏆 *ДОСТИЖЕНИЯ*\n{ach_text}\n\n"
        f"🎒 *ИНВЕНТАРЬ*\n"
        f"Вес: {player.current_weight:.1f}/{player.max_weight}\n"
        f"Предметов: {len(player.inventory)}/{player.backpack_size}"
    )
    
    # Кнопка прокачки если есть очки
    keyboard = get_main_keyboard()
    if player.stat_points > 0:
        keyboard.keyboard.append(["📈 Прокачка"])
    
    await update.message.reply_text(
        profile_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def show_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE, player):
    """Показать инвентарь"""
    if not player.inventory:
        await update.message.reply_text(
            "🎒 *Инвентарь пуст*\n\nИсследуй локации или покупай у торговцев!",
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Группировка по типам
    weapons = []
    armors = []
    consumables = []
    materials = []
    ammo = []
    quest_items = []
    other = []
    
    for item in player.inventory:
        item_type = item.get('type', 'misc')
        name = item.get('name', 'Unknown')
        quantity = item.get('quantity', 1)
        
        if quantity > 1:
            display = f"• {name} x{quantity}"
        else:
            display = f"• {name}"
        
        if item_type == 'weapon':
            weapons.append(display)
        elif item_type == 'armor':
            armors.append(display)
        elif item_type == 'consumable':
            consumables.append(display)
        elif item_type == 'material':
            materials.append(display)
        elif item_type == 'ammo':
            ammo.append(display)
        elif item_type == 'quest':
            quest_items.append(display)
        else:
            other.append(display)
    
    inventory_text = "🎒 *ИНВЕНТАРЬ*\n\n"
    
    if weapons:
        inventory_text += "*⚔️ Оружие:*\n" + "\n".join(weapons) + "\n\n"
    if armors:
        inventory_text += "*🛡️ Броня:*\n" + "\n".join(armors) + "\n\n"
    if consumables:
        inventory_text += "*💊 Расходники:*\n" + "\n".join(consumables) + "\n\n"
    if ammo:
        inventory_text += "*🔫 Патроны:*\n" + "\n".join(ammo) + "\n\n"
    if materials:
        inventory_text += "*🔧 Материалы:*\n" + "\n".join(materials) + "\n\n"
    if quest_items:
        inventory_text += "*📋 Квестовые:*\n" + "\n".join(quest_items) + "\n\n"
    if other:
        inventory_text += "*📦 Прочее:*\n" + "\n".join(other) + "\n\n"
    
    inventory_text += f"Вес: {player.current_weight:.1f}/{player.max_weight}\n"
    inventory_text += f"Слотов: {len(player.inventory)}/{player.backpack_size}"
    
    # Кнопки для использования/экипировки
    keyboard = [
        ["⚔️ Экипировать", "💊 Использовать"],
        ["🗑️ Выбросить", "◀️ Назад"]
    ]
    
    await update.message.reply_text(
        inventory_text,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        parse_mode=ParseMode.MARKDOWN
    )

async def show_trader(update: Update, context: ContextTypes.DEFAULT_TYPE, player):
    """Показать торговца"""
    # Находим NPC в текущей локации
    location = game.locations[player.location]
    npcs = []
    for npc_id in location.npcs:
        npc = game.npcs.get(npc_id)
        if npc:
            npcs.append(npc)
    
    if not npcs:
        await update.message.reply_text(
            "❌ В этой локации нет торговцев!",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Показываем первого торговца (упрощенно)
    trader = npcs[0]
    player.state = GameState.TRADING
    context.user_data['current_trader'] = trader
    
    # Проверка репутации
    rep_requirement = 0
    for faction, value in player.reputation.items():
        if value < rep_requirement:
            await update.message.reply_text(
                f"❌ {trader.name} не доверяет тебе! Нужна репутация выше.",
                reply_markup=get_main_keyboard()
            )
            player.state = GameState.MENU
            return
    
    trader_text = (
        f"🏪 *{trader.name}*\n\n"
        f"_{trader.dialogue}_\n\n"
        f"💰 Твои крышки: {player.money['bottlecaps']}\n\n"
        f"*Что будем делать?*"
    )
    
    await update.message.reply_text(
        trader_text,
        reply_markup=get_trader_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def show_crafting(update: Update, context: ContextTypes.DEFAULT_TYPE, player):
    """Показать крафт"""
    player.state = GameState.CRAFTING
    
    craft_text = (
        "🔧 *МАСТЕРСКАЯ*\n\n"
        "Здесь ты можешь создавать полезные предметы из найденных материалов.\n\n"
        "*Доступные рецепты:*\n"
        "• Бинт (2 ткани) - лечит 20 HP\n"
        "• Аптечка (3 ткани + 1 антибиотик) - лечит 50 HP\n"
        "• Коктейль Молотова (1 бутылка + 1 тряпка + 1 спирт) - урон 40 AOE\n"
        "• Заточка оружия (1 металл + 1 точило) - +5 урона на 10 боев\n"
        "• Самодельный пистолет (3 металла + 1 пружина) - базовое оружие\n\n"
        "Выбери категорию:"
    )
    
    await update.message.reply_text(
        craft_text,
        reply_markup=get_craft_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def show_shelter(update: Update, context: ContextTypes.DEFAULT_TYPE, player):
    """Показать убежище"""
    player.state = GameState.SHELTER
    
    shelter_text = (
        f"🏠 *УБЕЖИЩЕ (Уровень {player.shelter_level})*\n\n"
        f"Твое убежище - единственное безопасное место в этом аду.\n\n"
        f"❤️ Восстановление: +20 HP/час\n"
        f"⚡ Энергия: +30/час\n"
        f"📦 Хранилище: {player.backpack_size} слотов\n"
        f"🛡️ Защита: базовая\n\n"
        f"*Доступные действия:*"
    )
    
    await update.message.reply_text(
        shelter_text,
        reply_markup=get_shelter_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать топы"""
    game.update_leaderboards()
    
    text = "🏆 *ТОПЫ ВЫЖИВШИХ*\n\n"
    
    text += "*📊 ПО УРОВНЮ:*\n"
    for i, p in enumerate(game.leaderboards['level'][:5], 1):
        text += f"{i}. @{p.username} - Ур.{p.level} (дней: {p.days_survived})\n"
    
    text += "\n*🗡️ ПО УБИЙСТВАМ:*\n"
    for i, p in enumerate(game.leaderboards['kills'][:5], 1):
        text += f"{i}. @{p.username} - {p.kills['zombie']} зомби\n"
    
    text += "\n*💰 ПО БОГАТСТВУ:*\n"
    for i, p in enumerate(game.leaderboards['wealth'][:5], 1):
        text += f"{i}. @{p.username} - {p.money['bottlecaps']} крышек\n"
    
    text += "\n*📅 ПО ДНЯМ:*\n"
    for i, p in enumerate(game.leaderboards['days'][:5], 1):
        text += f"{i}. @{p.username} - {p.days_survived} дней\n"
    
    if game.leaderboards['clans']:
        text += "\n*🤝 ПО КЛАНАМ:*\n"
        for i, c in enumerate(game.leaderboards['clans'][:3], 1):
            text += f"{i}. {c.name} [{c.tag}] - Ур.{c.level}\n"
    
    await update.message.reply_text(
        text,
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def show_lootboxes(update: Update, context: ContextTypes.DEFAULT_TYPE, player):
    """Показать кейсы"""
    lootbox_text = (
        "🎁 *КЕЙСЫ С ЛУТОМ*\n\n"
        "*Доступные кейсы:*\n\n"
        "📦 *Обычный ящик* - 50 крышек\n"
        "Шансы:\n"
        "• Еда/вода - 50%\n"
        "• Бинты - 30%\n"
        "• Патроны - 15%\n"
        "• Пистолет - 5%\n\n"
        "📦 *Оружейный ящик* - 150 крышек\n"
        "Шансы:\n"
        "• Обычное оружие - 50%\n"
        "• Патроны - 30%\n"
        "• Гранаты - 15%\n"
        "• Редкое оружие - 5%\n\n"
        "📦 *Военный контейнер* - 500 крышек (нужен ур.5)\n"
        "Шансы:\n"
        "• Редкое оружие - 40%\n"
        "• Броня - 30%\n"
        "• Медикаменты - 20%\n"
        "• Легендарное - 10%\n\n"
        "📦 *Ивентовый кейс* - 200 крышек (ивент)\n"
        "Шансы:\n"
        "• Уникальные предметы - 100%\n\n"
        "💰 Твои крышки: {player.money['bottlecaps']}\n\n"
        "Напиши номер кейса для открытия:\n"
        "1 - Обычный\n"
        "2 - Оружейный\n"
        "3 - Военный (ур.5)\n"
        "4 - Ивентовый"
    )
    
    await update.message.reply_text(
        lootbox_text,
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Сохраняем состояние для ожидания выбора
    context.user_data['waiting_for_lootbox'] = True

async def show_clans(update: Update, context: ContextTypes.DEFAULT_TYPE, player):
    """Показать кланы"""
    player.state = GameState.CLAN
    
    if player.clan_id:
        clan = game.clans.get(player.clan_id)
        if clan:
            clan_text = (
                f"🤝 *КЛАН {clan.name} [{clan.tag}]*\n\n"
                f"Уровень: {clan.level}\n"
                f"Опыт: {clan.exp}\n"
                f"Участников: {len(clan.members)}\n"
                f"Казна: {clan.treasury} крышек\n"
                f"База: ур.{clan.base_level}\n"
                f"Побед в войнах: {clan.wins}\n"
                f"Поражений: {clan.losses}\n\n"
                f"Твой ранг: {player.clan_rank}"
            )
            await update.message.reply_text(
                clan_text,
                reply_markup=get_clan_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            player.clan_id = None
            await show_no_clan(update, context)
    else:
        await show_no_clan(update, context)

async def show_no_clan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню без клана"""
    text = (
        "🤝 *КЛАНЫ*\n\n"
        "Ты пока не состоишь в клане. Кланы дают бонусы:\n"
        "• +10% к опыту\n"
        "• Общая казна\n"
        "• Войны кланов\n"
        "• Совместные рейды\n"
        "• Клановая база\n\n"
        "Доступные действия:\n"
        "1 - Создать клан (1000 крышек)\n"
        "2 - Список кланов\n"
        "3 - Заявки\n\n"
        "Напиши номер действия:"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    
    context.user_data['waiting_for_clan_action'] = True

async def show_events(update: Update, context: ContextTypes.DEFAULT_TYPE, player):
    """Показать текущие ивенты"""
    text = "📅 *ИВЕНТЫ*\n\n"
    
    if game.current_event:
        event = game.current_event
        time_left = event.end_time - datetime.now()
        hours_left = time_left.total_seconds() / 3600
        
        text += f"*ТЕКУЩИЙ ИВЕНТ:*\n"
        text += f"{event.name}\n"
        text += f"_{event.description}_\n"
        text += f"⏱️ Осталось: {hours_left:.1f} часов\n\n"
        text += "*Эффекты:*\n"
        for effect, value in event.effects.items():
            text += f"• {effect}: x{value}\n"
    else:
        text += "Сейчас нет активных ивентов.\n"
        text += "Следующий ивент может начаться в любой момент!\n\n"
    
    text += "*Расписание ивентов:*\n"
    text += "🌕 Полнолуние - каждые 7 дней\n"
    text += "📦 Припасы - случайно\n"
    text += "⚔️ Атака рейдеров - раз в 3 дня\n"
    text += "☢️ Радиация - раз в 5 дней\n"
    text += "🎉 Праздники - по особым дням"
    
    await update.message.reply_text(
        text,
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE, player):
    """Показать помощь"""
    help_text = (
        "🧟 *ZOMBIE APOCALYPSE RPG - ПОМОЩЬ*\n\n"
        "*ОСНОВНЫЕ ДЕЙСТВИЯ:*\n"
        "🧟 В бой - сражение с зомби (тратит 10 энергии)\n"
        "🗺️ Исследовать - поиск ресурсов (15 энергии)\n"
        "👤 Профиль - твои характеристики\n"
        "🎒 Инвентарь - твои вещи\n"
        "🏪 Торговец - купить/продать\n"
        "🔧 Крафт - создание предметов\n"
        "🏠 Убежище - отдых и улучшения\n"
        "📊 Топы - рейтинг игроков\n"
        "🎁 Кейсы - лутбоксы\n"
        "🤝 Кланы - клановая система\n"
        "📅 Ивенты - события\n\n"
        "*БОЕВАЯ СИСТЕМА:*\n"
        "⚔️ Атака - ближний бой (сила + оружие)\n"
        "🔫 Стрелять - дальний бой (тратит патроны)\n"
        "💊 Лечиться - использовать аптечку\n"
        "🏃 Убежать - шанс сбежать (ловкость)\n\n"
        "*ХАРАКТЕРИСТИКИ:*\n"
        "💪 Сила - урон в ближнем бою\n"
        "🏃 Ловкость - шанс убежать, уклонение\n"
        "👀 Восприятие - точность стрельбы\n"
        "💪 Выносливость - макс HP\n"
        "🧠 Интеллект - качество крафта\n"
        "🍀 Удача - криты, редкий лут\n\n"
        "*ЭКОНОМИКА:*\n"
        "💰 Крышки - основная валюта\n"
        "🔫 Патроны - для стрельбы\n"
        "💊 Медикаменты - лечение\n"
        "🍗 Еда/💧 Вода - голод/жажда\n"
        "🔧 Материалы - для крафта\n\n"
        "*ПРОКАЧКА:*\n"
        "За убийства зомби получаешь опыт\n"
        "Новый уровень = +3 стат поинта\n"
        "Используй /stats чтобы распределить\n\n"
        "*КВЕСТЫ И ДОСТИЖЕНИЯ:*\n"
        "Выполняй квесты у NPC\n"
        "Получай достижения за особые действия\n"
        "Награды - крышки, опыт, уникальные предметы\n\n"
        "*КЛАНЫ:*\n"
        "Объединяйся с другими выжившими\n"
        "Сражайтесь в войнах кланов\n"
        "Развивайте общую базу\n\n"
        "*СОВЕТЫ:*\n"
        "• Следи за энергией - без нее нельзя действовать\n"
        "• Ешь и пей регулярно, иначе будешь терять HP\n"
        "• Улучшай убежище для лучшего отдыха\n"
        "• Вступай в клан для бонусов\n"
        "• Участвуй в ивентах для редкого лута"
    )
    
    await update.message.reply_text(
        help_text,
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def check_quest_progress(player, action, target=None):
    """Проверка прогресса квестов"""
    for quest_id in player.quests:
        quest = game.quests.get(quest_id)
        if not quest:
            continue
        
        if quest.type == "kill" and action == "kill":
            if target == quest.target.get('enemy') or quest.target.get('enemy') == 'zombie':
                # Будет обработано отдельно
                pass

# ============================================
# ЗАПУСК БОТА
# ============================================

def main():
    """Запуск бота"""
    print("🧟 Запуск Zombie Apocalypse RPG Bot v3.0...")
    print(f"✅ Токен загружен")
    
    # Запускаем Flask в отдельном потоке
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("✅ Веб-сервер Flask запущен на порту 8080")
    
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", show_help))
    application.add_handler(CommandHandler("profile", show_profile))
    application.add_handler(CommandHandler("inventory", show_inventory))
    application.add_handler(CommandHandler("top", show_leaderboard))
    application.add_handler(CommandHandler("clan", show_clans))
    application.add_handler(CommandHandler("event", show_events))
    
    # Обработчик текста
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Запускаем бота
    print("✅ Бот успешно запущен!")
    print("🤖 Ожидание сообщений...")
    application.run_polling()

if __name__ == '__main__':
    main()
