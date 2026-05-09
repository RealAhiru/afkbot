# database.py
import aiosqlite
from datetime import datetime
import asyncio

class DatabaseManager:
    def __init__(self, db_path: str = "afk_data.db"):
        self.db_path = db_path

    async def init_db(self):
        """Создаёт таблицы при запуске"""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица для AFK пользователей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS afk_users (
                    user_id INTEGER PRIMARY KEY,
                    user_name TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    hours INTEGER NOT NULL,
                    return_time TIMESTAMP NOT NULL,
                    start_time TIMESTAMP NOT NULL
                )
            """)
            
            # Таблица для ОТПУСКОВ
            await db.execute("""
                CREATE TABLE IF NOT EXISTS vacation_users (
                    user_id INTEGER PRIMARY KEY,
                    user_name TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    start_date TIMESTAMP NOT NULL,
                    end_date TIMESTAMP NOT NULL,
                    start_str TEXT NOT NULL,
                    end_str TEXT NOT NULL
                )
            """)
            
            # Таблица для хранения ID сообщения с панелью AFK
            await db.execute("""
                CREATE TABLE IF NOT EXISTS afk_panel_info (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL
                )
            """)
            
            # Таблица для хранения ID сообщения с панелью ОТПУСКОВ
            await db.execute("""
                CREATE TABLE IF NOT EXISTS vacation_panel_info (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL
                )
            """)
            
            await db.commit()
            print("✅ База данных инициализирована")

    # ========== AFK МЕТОДЫ ==========
    
    async def save_afk_user(self, user_id: int, user_name: str, reason: str, hours: int, return_time: datetime, start_time: datetime):
        """Сохраняет AFK пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO afk_users 
                (user_id, user_name, reason, hours, return_time, start_time)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, user_name, reason, hours, return_time.isoformat(), start_time.isoformat()))
            await db.commit()

    async def remove_afk_user(self, user_id: int):
        """Удаляет AFK пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM afk_users WHERE user_id = ?", (user_id,))
            await db.commit()

    async def get_all_afk_users(self):
        """Получает всех AFK пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id, user_name, reason, hours, return_time, start_time FROM afk_users") as cursor:
                rows = await cursor.fetchall()
                afk_dict = {}
                for row in rows:
                    afk_dict[row[0]] = {
                        "user_name": row[1],
                        "reason": row[2],
                        "hours": row[3],
                        "return_time": datetime.fromisoformat(row[4]),
                        "start_time": datetime.fromisoformat(row[5])
                    }
                return afk_dict

    async def get_afk_user(self, user_id: int):
        """Получает одного AFK пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id, user_name, reason, hours, return_time, start_time FROM afk_users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "user_name": row[1],
                        "reason": row[2],
                        "hours": row[3],
                        "return_time": datetime.fromisoformat(row[4]),
                        "start_time": datetime.fromisoformat(row[5])
                    }
                return None

    async def save_afk_panel_info(self, channel_id: int, message_id: int):
        """Сохраняет ID канала и сообщения с панелью AFK"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO afk_panel_info (id, channel_id, message_id)
                VALUES (1, ?, ?)
            """, (channel_id, message_id))
            await db.commit()

    async def get_afk_panel_info(self):
        """Получает ID канала и сообщения с панелью AFK"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT channel_id, message_id FROM afk_panel_info WHERE id = 1") as cursor:
                row = await cursor.fetchone()
                if row:
                    return {"channel_id": row[0], "message_id": row[1]}
                return None

    async def clear_expired_afk(self):
        """Удаляет просроченных AFK пользователей"""
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM afk_users WHERE return_time <= ?", (now,))
            await db.commit()

    async def get_expired_afk_users(self):
        """Возвращает список просроченных AFK пользователей"""
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id FROM afk_users WHERE return_time <= ?", (now,)) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    # ========== ОТПУСК МЕТОДЫ ==========
    
    async def save_vacation_user(self, user_id: int, user_name: str, reason: str, start_date: datetime, end_date: datetime, start_str: str, end_str: str):
        """Сохраняет пользователя в отпуске"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO vacation_users 
                (user_id, user_name, reason, start_date, end_date, start_str, end_str)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, user_name, reason, start_date.isoformat(), end_date.isoformat(), start_str, end_str))
            await db.commit()

    async def remove_vacation_user(self, user_id: int):
        """Удаляет пользователя из отпуска"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM vacation_users WHERE user_id = ?", (user_id,))
            await db.commit()

    async def get_all_vacation_users(self):
        """Получает всех пользователей в отпуске"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id, user_name, reason, start_date, end_date, start_str, end_str FROM vacation_users") as cursor:
                rows = await cursor.fetchall()
                vacation_dict = {}
                for row in rows:
                    vacation_dict[row[0]] = {
                        "user_name": row[1],
                        "reason": row[2],
                        "start_date": datetime.fromisoformat(row[3]),
                        "end_date": datetime.fromisoformat(row[4]),
                        "start_str": row[5],
                        "end_str": row[6]
                    }
                return vacation_dict

    async def get_vacation_user(self, user_id: int):
        """Получает одного пользователя в отпуске"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id, user_name, reason, start_date, end_date, start_str, end_str FROM vacation_users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "user_name": row[1],
                        "reason": row[2],
                        "start_date": datetime.fromisoformat(row[3]),
                        "end_date": datetime.fromisoformat(row[4]),
                        "start_str": row[5],
                        "end_str": row[6]
                    }
                return None

    async def save_vacation_panel_info(self, channel_id: int, message_id: int):
        """Сохраняет ID канала и сообщения с панелью отпусков"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO vacation_panel_info (id, channel_id, message_id)
                VALUES (1, ?, ?)
            """, (channel_id, message_id))
            await db.commit()

    async def get_vacation_panel_info(self):
        """Получает ID канала и сообщения с панелью отпусков"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT channel_id, message_id FROM vacation_panel_info WHERE id = 1") as cursor:
                row = await cursor.fetchone()
                if row:
                    return {"channel_id": row[0], "message_id": row[1]}
                return None

    async def clear_expired_vacations(self):
        """Удаляет завершившиеся отпуска"""
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM vacation_users WHERE end_date <= ?", (now,))
            await db.commit()

    async def get_expired_vacations(self):
        """Возвращает список пользователей с завершившимся отпуском"""
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id FROM vacation_users WHERE end_date <= ?", (now,)) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def close(self):
        """Закрывает соединение с БД"""
        pass