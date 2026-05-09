# bot.py
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from database import DatabaseManager
from cogs.afk import set_bot as set_afk_bot, setup_afk_commands, check_afk_expiry, update_afk_panel
from cogs.vacation import set_bot as set_vacation_bot, setup_vacation_commands, check_vacation_expiry, update_vacation_panel

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.db = DatabaseManager()
    
    async def setup_hook(self):
        await self.db.init_db()
        
        set_afk_bot(self, self.db)
        set_vacation_bot(self, self.db)
        
        await setup_afk_commands(self)
        await setup_vacation_commands(self)
        
        await self.db.clear_expired_afk()
        await self.db.clear_expired_vacations()
        
        check_afk_expiry.start()
        check_vacation_expiry.start()
        
        print("✅ Бот готов и все системы запущены!")
    
    async def on_ready(self):
        print(f"✅ Бот {self.user} запущен!")
        print(f"ID бота: {self.user.id}")
        print(f"На серверах: {[guild.name for guild in self.guilds]}")
        
        synced = await self.tree.sync()
        print(f"✅ Глобально синхронизировано {len(synced)} команд")
        for cmd in synced:
            print(f"   /{cmd.name}")
        
        # Восстанавливаем панели в нужных каналах
        for guild in self.guilds:
            try:
                await update_afk_panel(guild)
                await update_vacation_panel(guild)
                print(f"✅ Панели восстановлены на сервере {guild.name}")
            except Exception as e:
                print(f"❌ Ошибка при обновлении панелей на {guild.name}: {e}")
        
        print("🚀 Бот готов!")

bot = MyBot()
bot.run(os.getenv("DISCORD_TOKEN"))