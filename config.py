# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# ID каналов для панелей (куда будут отправлены кнопки)
# Чтобы получить ID канала: ПКМ по каналу → Копировать ID
AFK_CHANNEL_ID = 1497922391177695353          # 👈 ВСТАВЬ ID КАНАЛА ДЛЯ AFK (где будет панель)
VACATION_CHANNEL_ID = 1499478144996868279     # 👈 ВСТАВЬ ID КАНАЛА ДЛЯ ОТПУСКОВ

# ID ролей, которые могут использовать бота (если пусто - все)
ALLOWED_ROLES = []  # [123456789, 987654321]

# Московское время
TIMEZONE = "Europe/Moscow"

# Настройки бота
BOT_FOOTER = "AFK & Отпуска | Семья Sugar"
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")