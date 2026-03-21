import asyncpg
from config import DATABASE_URL

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(DATABASE_URL)
        await self._create_tables()

    async def _create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    pet_type TEXT DEFAULT 'fox',
                    pet_stage INTEGER DEFAULT 0,
                    hunger INTEGER DEFAULT 100,
                    mood INTEGER DEFAULT 100,
                    last_feed TIMESTAMP DEFAULT NOW(),
                    last_pet TIMESTAMP DEFAULT NOW(),
                    coins INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

    async def get_user(self, user_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)

    async def create_user(self, user_id: int, username: str, pet_type: str):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, username, pet_type)
                VALUES ($1, $2, $3)
            """, user_id, username, pet_type)

    async def update_hunger(self, user_id: int, hunger: int):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users SET hunger = $1, last_feed = NOW()
                WHERE user_id = $2
            """, min(100, hunger), user_id)

    async def update_mood(self, user_id: int, mood: int):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users SET mood = $1, last_pet = NOW()
                WHERE user_id = $2
            """, min(100, mood), user_id)

    async def add_coins(self, user_id: int, amount: int):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users SET coins = coins + $1 WHERE user_id = $2
            """, amount, user_id)

    async def update_stage(self, user_id: int, stage: int):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users SET pet_stage = $1 WHERE user_id = $2
            """, stage, user_id)

db = Database()