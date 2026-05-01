import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import pytz

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ===== НАСТРОЙКИ =====
ALLOWED_ROLE_IDS = []  # ID ролей, которые могут использовать бота
ADMIN_ROLE_ID = [1243891359837065348, 1244300549675946007, 1244302312877330432]

# Хранилище AFK пользователей
afk_users = {}

# Хранилище отпусков пользователей
vacation_users = {}

# Сохраняем ID канала и сообщения с панелью AFK
panel_channel_id = None
panel_message_id = None

# Сохраняем ID канала и сообщения с панелью отпусков
vacation_panel_channel_id = None
vacation_panel_message_id = None

# Московское время
MSK_TZ = pytz.timezone('Europe/Moscow')

def get_msk_time():
    return datetime.now(MSK_TZ)

def format_return_time(return_time):
    return return_time.strftime("%d.%m.%Y в %H:%M")

def format_vacation_date(date_obj):
    return date_obj.strftime("%d.%m.%Y")

# ==================== AFK КЛАССЫ ====================

class AFKModal(discord.ui.Modal, title="Уход в AFK"):
    reason = discord.ui.TextInput(
        label="Причина отсутствия",
        placeholder="Напиши причину",
        required=True,
        max_length=100,
        min_length=1
    )
    
    hours = discord.ui.TextInput(
        label="На сколько часов? (1-8)",
        placeholder="Введи число от 1 до 8",
        required=True,
        max_length=1,
        min_length=1
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            hours = int(self.hours.value)
            if hours < 1 or hours > 8:
                await interaction.response.send_message("❌ Введи число от 1 до 8!", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Введи число!", ephemeral=True)
            return
        
        now = get_msk_time()
        return_time = now + timedelta(hours=hours)
        
        afk_users[interaction.user.id] = {
            "reason": self.reason.value,
            "return_time": return_time,
            "start_time": now,
            "hours": hours
        }
        
        await interaction.response.send_message(
            f"✅ Ты ушёл в AFK до {format_return_time(return_time)} (МСК)",
            ephemeral=True
        )
        
        await update_afk_panel(interaction.guild)

class ReturnConfirmModal(discord.ui.Modal, title="Подтверждение возврата"):
    confirm = discord.ui.TextInput(
        label="Введи 'вернулся' для подтверждения",
        placeholder="вернулся",
        required=True,
        max_length=10,
        min_length=7
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.confirm.value.lower() == "вернулся":
            if interaction.user.id in afk_users:
                afk_users.pop(interaction.user.id)
                await interaction.response.send_message("✅ Добро пожаловать обратно!", ephemeral=True)
                await update_afk_panel(interaction.guild)
            else:
                await interaction.response.send_message("❌ Тебя нет в списке AFK!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Неправильное проверочное слово!", ephemeral=True)

class AFKView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🚶 Отошел", style=discord.ButtonStyle.primary, custom_id="afk_go")
    async def go_afk(self, interaction: discord.Interaction, button: discord.ui.Button):
        if ALLOWED_ROLE_IDS:
            user_roles = [role.id for role in interaction.user.roles]
            allowed = any(role_id in user_roles for role_id in ALLOWED_ROLE_IDS)
            if not allowed and interaction.user.guild_permissions.administrator:
                allowed = True
            if not allowed:
                await interaction.response.send_message("❌ У тебя нет прав!", ephemeral=True)
                return
        
        await interaction.response.send_modal(AFKModal())
    
    @discord.ui.button(label="✅ Вернулся", style=discord.ButtonStyle.success, custom_id="afk_back")
    async def back_from_afk(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in afk_users:
            await interaction.response.send_message("❌ Тебя нет в списке AFK!", ephemeral=True)
            return
        
        await interaction.response.send_modal(ReturnConfirmModal())

# ==================== ОТПУСК КЛАССЫ ====================

class VacationModal(discord.ui.Modal, title="Уход в отпуск"):
    reason = discord.ui.TextInput(
        label="Причина отпуска",
        placeholder="Напиши причину (например: отпуск, больничный, командировка)",
        required=True,
        max_length=100,
        min_length=1
    )
    
    start_date = discord.ui.TextInput(
        label="Дата начала отпуска (ДД.ММ)",
        placeholder="Например: 01.06",
        required=True,
        max_length=5,
        min_length=5
    )
    
    end_date = discord.ui.TextInput(
        label="Дата окончания отпуска (ДД.ММ)",
        placeholder="Например: 30.06",
        required=True,
        max_length=5,
        min_length=5
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Получаем текущий год
            current_year = get_msk_time().year
            
            # Парсим даты
            start_day, start_month = map(int, self.start_date.value.split('.'))
            end_day, end_month = map(int, self.end_date.value.split('.'))
            
            # Создаём datetime объекты
            start_datetime = datetime(current_year, start_month, start_day, 0, 0)
            end_datetime = datetime(current_year, end_month, end_day, 23, 59)
            
            # Если дата окончания раньше даты начала - переносим на следующий год
            if end_datetime < start_datetime:
                end_datetime = datetime(current_year + 1, end_month, end_day, 23, 59)
            
            # Проверяем, что отпуск не закончился
            now = get_msk_time().replace(tzinfo=None)
            if end_datetime < now:
                await interaction.response.send_message("❌ Эта дата уже прошла! Укажи будущую дату.", ephemeral=True)
                return
            
            vacation_users[interaction.user.id] = {
                "reason": self.reason.value,
                "start_date": start_datetime,
                "end_date": end_datetime,
                "start_str": format_vacation_date(start_datetime),
                "end_str": format_vacation_date(end_datetime)
            }
            
            await interaction.response.send_message(
                f"✅ Ты ушёл в отпуск!\n"
                f"📅 **С:** {format_vacation_date(start_datetime)}\n"
                f"📅 **По:** {format_vacation_date(end_datetime)}\n"
                f"📝 **Причина:** {self.reason.value}",
                ephemeral=True
            )
            
            await update_vacation_panel(interaction.guild)
            
        except ValueError:
            await interaction.response.send_message("❌ Неверный формат даты! Используй ДД.ММ (например: 01.06)", ephemeral=True)

class ReturnFromVacationModal(discord.ui.Modal, title="Подтверждение возврата из отпуска"):
    confirm = discord.ui.TextInput(
        label="Введи 'вернулся' для подтверждения",
        placeholder="вернулся",
        required=True,
        max_length=10,
        min_length=7
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.confirm.value.lower() == "вернулся":
            if interaction.user.id in vacation_users:
                vacation_users.pop(interaction.user.id)
                await interaction.response.send_message("✅ Добро пожаловать из отпуска!", ephemeral=True)
                await update_vacation_panel(interaction.guild)
            else:
                await interaction.response.send_message("❌ Тебя нет в списке отпусков!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Неправильное проверочное слово!", ephemeral=True)

class VacationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🏖️ В отпуск", style=discord.ButtonStyle.primary, custom_id="vacation_go")
    async def go_vacation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if ALLOWED_ROLE_IDS:
            user_roles = [role.id for role in interaction.user.roles]
            allowed = any(role_id in user_roles for role_id in ALLOWED_ROLE_IDS)
            if not allowed and interaction.user.guild_permissions.administrator:
                allowed = True
            if not allowed:
                await interaction.response.send_message("❌ У тебя нет прав!", ephemeral=True)
                return
        
        await interaction.response.send_modal(VacationModal())
    
    @discord.ui.button(label="✅ Вернулся", style=discord.ButtonStyle.success, custom_id="vacation_back")
    async def back_from_vacation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in vacation_users:
            await interaction.response.send_message("❌ Тебя нет в списке отпусков!", ephemeral=True)
            return
        
        await interaction.response.send_modal(ReturnFromVacationModal())

# ==================== ОБНОВЛЕНИЕ ПАНЕЛЕЙ ====================

async def update_afk_panel(guild):
    """Быстрое обновление панели AFK"""
    global panel_channel_id, panel_message_id
    
    now = get_msk_time()
    expired = [uid for uid, data in afk_users.items() if now >= data["return_time"]]
    for uid in expired:
        del afk_users[uid]
    
    if panel_channel_id and panel_message_id:
        try:
            channel = bot.get_channel(panel_channel_id)
            if channel:
                message = await channel.fetch_message(panel_message_id)
                await message.edit(embed=create_afk_embed(guild), view=AFKView())
                return
        except:
            pass
    
    system_channel = guild.system_channel or guild.text_channels[0]
    async for message in system_channel.history(limit=50):
        if message.author == bot.user and message.embeds and message.embeds[0].title == "📊 AFK Отчеты":
            panel_channel_id = message.channel.id
            panel_message_id = message.id
            await message.edit(embed=create_afk_embed(guild), view=AFKView())
            return
    
    msg = await system_channel.send(embed=create_afk_embed(guild), view=AFKView())
    panel_channel_id = msg.channel.id
    panel_message_id = msg.id

async def update_vacation_panel(guild):
    """Обновление панели отпусков"""
    global vacation_panel_channel_id, vacation_panel_message_id
    
    now = get_msk_time().replace(tzinfo=None)
    expired = [uid for uid, data in vacation_users.items() if now > data["end_date"]]
    for uid in expired:
        del vacation_users[uid]
    
    if vacation_panel_channel_id and vacation_panel_message_id:
        try:
            channel = bot.get_channel(vacation_panel_channel_id)
            if channel:
                message = await channel.fetch_message(vacation_panel_message_id)
                await message.edit(embed=create_vacation_embed(guild), view=VacationView())
                return
        except:
            pass
    
    system_channel = guild.system_channel or guild.text_channels[0]
    async for message in system_channel.history(limit=50):
        if message.author == bot.user and message.embeds and message.embeds[0].title == "🏖️ Отпуска":
            vacation_panel_channel_id = message.channel.id
            vacation_panel_message_id = message.id
            await message.edit(embed=create_vacation_embed(guild), view=VacationView())
            return
    
    msg = await system_channel.send(embed=create_vacation_embed(guild), view=VacationView())
    vacation_panel_channel_id = msg.channel.id
    vacation_panel_message_id = msg.id

# ==================== EMBED ====================

def create_afk_embed(guild):
    """Создает embed со списком AFK"""
    now = get_msk_time()
    active_afk = {uid: data for uid, data in afk_users.items() if now < data["return_time"]}
    
    if not active_afk:
        embed = discord.Embed(
            title="📊 AFK Отчеты",
            description="🎉 **Никого нет в AFK!**\n\nВсе на месте!",
            color=discord.Color.green()
        )
        embed.set_footer(text="Нажми 'Отошел', чтобы уйти в AFK")
        return embed
    
    sorted_users = sorted(active_afk.items(), key=lambda x: x[1]["return_time"])
    description = f"👥 **Сейчас в AFK: {len(sorted_users)}** человек(а)\n\n"
    
    for index, (user_id, data) in enumerate(sorted_users, start=1):
        user = guild.get_member(user_id)
        if user:
            time_str = data["return_time"].strftime("%H:%M")
            description += f"**{index}.** {user.mention} | 📝Причина: {data['reason']} | ⏰ вернётся в: **{time_str}**\n"
    
    embed = discord.Embed(
        title="📊 AFK Отчеты",
        description=description,
        color=discord.Color.orange()
    )
    embed.set_footer(text="Нажми 'Вернулся', когда вернёшься")
    return embed

def create_vacation_embed(guild):
    """Создает embed со списком отпусков"""
    now = get_msk_time().replace(tzinfo=None)
    active_vacations = {uid: data for uid, data in vacation_users.items() if now <= data["end_date"]}
    
    if not active_vacations:
        embed = discord.Embed(
            title="🏖️ Отпуска",
            description="🎉 **Никого нет в отпуске!**\n\nВсе работают!",
            color=discord.Color.green()
        )
        embed.set_footer(text="Нажми 'В отпуск', чтобы уйти в отпуск")
        return embed
    
    sorted_users = sorted(active_vacations.items(), key=lambda x: x[1]["start_date"])
    description = f"👥 **Сейчас в отпуске: {len(sorted_users)}** человек(а)\n\n"
    
    for index, (user_id, data) in enumerate(sorted_users, start=1):
        user = guild.get_member(user_id)
        if user:
            description += f"**{index}.** {user.mention} | 📝Причина: {data['reason']} | 📅 **{data['start_str']} - {data['end_str']}**\n"
    
    embed = discord.Embed(
        title="🏖️ Отпуска",
        description=description,
        color=discord.Color.blue()
    )
    embed.set_footer(text="Нажми 'Вернулся', когда вернёшься из отпуска")
    return embed

# ==================== ЗАДАЧИ И КОМАНДЫ ====================

@tasks.loop(minutes=1)
async def check_afk_expiry():
    for guild in bot.guilds:
        now = get_msk_time()
        expired = [uid for uid, data in afk_users.items() if now >= data["return_time"]]
        if expired:
            for uid in expired:
                del afk_users[uid]
            await update_afk_panel(guild)

@tasks.loop(minutes=60)  # Проверяем раз в час (отпуска не такие срочные)
async def check_vacation_expiry():
    for guild in bot.guilds:
        now = get_msk_time().replace(tzinfo=None)
        expired = [uid for uid, data in vacation_users.items() if now > data["end_date"]]
        if expired:
            for uid in expired:
                del vacation_users[uid]
            await update_vacation_panel(guild)

@bot.event
async def on_ready():
    print(f"✅ Бот AFK {bot.user} запущен!")
    await bot.tree.sync()
    check_afk_expiry.start()
    check_vacation_expiry.start()
    print("🚀 Используй команды:")
    print("   /setup_afk_panel - панель AFK")
    print("   /setup_vacation_panel - панель отпусков")
    print("   /afk_list - список AFK")
    print("   /vacation_list - список отпусков")

@bot.tree.command(name="setup_afk_panel", description="Отправить панель AFK")
@app_commands.default_permissions(administrator=True)
async def setup_afk_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📊 AFK Отчеты",
        description="Используй кнопки ниже для отметки отсутствия.\n\n"
                   "**🚶 Отошел** — укажи причину и время\n"
                   "**✅ Вернулся** — подтверди возврат словом 'вернулся'",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, view=AFKView())
    
    msg = await interaction.original_response()
    global panel_channel_id, panel_message_id
    panel_channel_id = msg.channel.id
    panel_message_id = msg.id

@bot.tree.command(name="setup_vacation_panel", description="Отправить панель отпусков")
@app_commands.default_permissions(administrator=True)
async def setup_vacation_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🏖️ Отпуска",
        description="Используй кнопки ниже для отметки отпуска.\n\n"
                   "**🏖️ В отпуск** — укажи причину и даты (ДД.ММ)\n"
                   "**✅ Вернулся** — подтверди возврат словом 'вернулся'",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, view=VacationView())
    
    msg = await interaction.original_response()
    global vacation_panel_channel_id, vacation_panel_message_id
    vacation_panel_channel_id = msg.channel.id
    vacation_panel_message_id = msg.id

@bot.tree.command(name="afk_list", description="Показать список AFK")
async def afk_list(interaction: discord.Interaction):
    await interaction.response.send_message(embed=create_afk_embed(interaction.guild), ephemeral=True)

@bot.tree.command(name="vacation_list", description="Показать список отпусков")
async def vacation_list(interaction: discord.Interaction):
    await interaction.response.send_message(embed=create_vacation_embed(interaction.guild), ephemeral=True)

bot.run(os.getenv("DISCORD_TOKEN"))