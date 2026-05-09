# cogs/vacation.py
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import pytz
from config import ALLOWED_ROLES, TIMEZONE, BOT_FOOTER, VACATION_CHANNEL_ID

# Глобальная переменная для бота
bot = None
db = None

def set_bot(bot_instance, db_instance):
    global bot, db
    bot = bot_instance
    db = db_instance

async def auto_delete_message(interaction: discord.Interaction, message: str, delete_after: int = 5):
    """Отправляет временное сообщение"""
    try:
        await interaction.response.send_message(message, ephemeral=True, delete_after=delete_after)
    except:
        try:
            await interaction.followup.send(message, ephemeral=True, delete_after=delete_after)
        except:
            pass

def get_msk_time():
    """Возвращает текущее время в Москве"""
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz)

def format_vacation_date(date_obj):
    """Форматирует дату для отображения"""
    return date_obj.strftime("%d.%m")

def create_static_vacation_embed() -> discord.Embed:
    """Создаёт статичный embed с инструкцией по отпуску"""
    embed = discord.Embed(
        title="🏖️ Отпуск Система",
        description=(
            "**Как оставить отчёт об отпуске?**\n\n"
            "1️⃣ Нажми на кнопку **«В отпуск»**\n"
            "2️⃣ Укажи причину отпуска\n"
            "3️⃣ Укажи даты (ДД.ММ)\n"
            "4️⃣ Ты появишься в списке отпусков\n\n"
            "**Как вернуться?**\n"
            "• Нажми на кнопку **«Вернулся»**\n"
            "• Подтверди слово «вернулся»\n\n"
            "📅 **Важно:** Отпуск может переноситься на следующий год, если дата окончания раньше даты начала!"
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text=BOT_FOOTER)
    return embed

async def create_dynamic_vacation_embed(guild) -> discord.Embed:
    """Создаёт динамический embed со списком отпусков"""
    vacation_users = await db.get_all_vacation_users()
    now = get_msk_time().replace(tzinfo=None)
    
    active_vacations = {uid: data for uid, data in vacation_users.items() if now <= data["end_date"]}
    
    if not active_vacations:
        embed = discord.Embed(
            title="📊 Текущие отпуска",
            description="🎉 **Никого нет в отпуске!**\n\nВсе работают!",
            color=discord.Color.green()
        )
        return embed
    
    sorted_users = sorted(active_vacations.items(), key=lambda x: x[1]["start_date"])
    description = f"👥 **Сейчас в отпуске: {len(sorted_users)}** человек(а)\n\n"
    
    for index, (user_id, data) in enumerate(sorted_users, start=1):
        user = guild.get_member(user_id)
        if user:
            description += f"**{index}.** {user.mention} | 📝 {data['reason']} | 📅 **{data['start_str']} - {data['end_str']}**\n"
        else:
            description += f"**{index}.** Пользователь {user_id} | 📝 {data['reason']} | 📅 **{data['start_str']} - {data['end_str']}**\n"
    
    embed = discord.Embed(
        title="📊 Текущие отпуска",
        description=description,
        color=discord.Color.blue()
    )
    return embed

class VacationModal(discord.ui.Modal, title="🏖️ Уход в отпуск"):
    reason = discord.ui.TextInput(
        label="Причина отпуска",
        placeholder="Напиши причину (отпуск, больничный, командировка)",
        required=True,
        max_length=100,
        min_length=1
    )
    
    start_date = discord.ui.TextInput(
        label="Дата начала (ДД.ММ)",
        placeholder="Например: 01.06",
        required=True,
        max_length=5,
        min_length=5
    )
    
    end_date = discord.ui.TextInput(
        label="Дата окончания (ДД.ММ)",
        placeholder="Например: 30.06",
        required=True,
        max_length=5,
        min_length=5
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        if ALLOWED_ROLES:
            user_roles = [role.id for role in interaction.user.roles]
            if not any(role_id in user_roles for role_id in ALLOWED_ROLES) and not interaction.user.guild_permissions.administrator:
                await auto_delete_message(interaction, "❌ У тебя нет прав для использования отпуска!", 3)
                return
        
        try:
            current_year = get_msk_time().year
            
            start_day, start_month = map(int, self.start_date.value.split('.'))
            end_day, end_month = map(int, self.end_date.value.split('.'))
            
            start_datetime = datetime(current_year, start_month, start_day, 0, 0)
            end_datetime = datetime(current_year, end_month, end_day, 23, 59)
            
            if end_datetime < start_datetime:
                end_datetime = datetime(current_year + 1, end_month, end_day, 23, 59)
            
            now = get_msk_time().replace(tzinfo=None)
            if end_datetime < now:
                await auto_delete_message(interaction, "❌ Эта дата уже прошла! Укажи будущую дату.", 3)
                return
            
        except ValueError:
            await auto_delete_message(interaction, "❌ Неверный формат даты! Используй ДД.ММ (например: 01.06)", 3)
            return
        
        await db.save_vacation_user(
            user_id=interaction.user.id,
            user_name=interaction.user.name,
            reason=self.reason.value,
            start_date=start_datetime,
            end_date=end_datetime,
            start_str=format_vacation_date(start_datetime),
            end_str=format_vacation_date(end_datetime)
        )
        
        await update_vacation_panel(interaction.guild)
        
        await auto_delete_message(
            interaction,
            f"✅ Ты ушёл в отпуск!\n📅 **С:** {format_vacation_date(start_datetime)}\n📅 **По:** {format_vacation_date(end_datetime)}\n📝 **Причина:** {self.reason.value}",
            5
        )

class ReturnFromVacationModal(discord.ui.Modal, title="✅ Подтверждение возврата из отпуска"):
    confirm = discord.ui.TextInput(
        label="Введи 'вернулся' для подтверждения",
        placeholder="вернулся",
        required=True,
        max_length=10,
        min_length=7
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.confirm.value.lower() == "вернулся":
            user_data = await db.get_vacation_user(interaction.user.id)
            if user_data:
                await db.remove_vacation_user(interaction.user.id)
                await update_vacation_panel(interaction.guild)
                
                await auto_delete_message(
                    interaction,
                    f"✅ Добро пожаловать из отпуска!\n📅 Ты отсутствовал с {user_data['start_str']} по {user_data['end_str']}",
                    5
                )
            else:
                await auto_delete_message(interaction, "❌ Тебя нет в списке отпусков!", 3)
        else:
            await auto_delete_message(interaction, "❌ Неправильное проверочное слово!", 3)

class VacationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🏖️ В отпуск", style=discord.ButtonStyle.primary, custom_id="vacation_go_button")
    async def go_vacation(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VacationModal())
    
    @discord.ui.button(label="✅ Вернулся", style=discord.ButtonStyle.success, custom_id="vacation_back_button")
    async def back_from_vacation(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_data = await db.get_vacation_user(interaction.user.id)
        if not user_data:
            await auto_delete_message(interaction, "❌ Тебя нет в списке отпусков!", 3)
            return
        
        await interaction.response.send_modal(ReturnFromVacationModal())

async def update_vacation_panel(guild):
    """Обновляет панель отпусков (статичный embed + динамический + кнопки)"""
    panel_info = await db.get_vacation_panel_info()
    
    static_embed = create_static_vacation_embed()
    dynamic_embed = await create_dynamic_vacation_embed(guild)
    
    if panel_info:
        channel = guild.get_channel(panel_info["channel_id"])
        if channel:
            try:
                message = await channel.fetch_message(panel_info["message_id"])
                await message.edit(embeds=[static_embed, dynamic_embed], view=VacationView())
                return
            except:
                pass
    
    # Если панель не найдена, создаём новую
    if VACATION_CHANNEL_ID:
        channel = guild.get_channel(VACATION_CHANNEL_ID)
    else:
        channel = guild.system_channel or guild.text_channels[0]
    
    if not channel:
        channel = guild.text_channels[0]
    
    msg = await channel.send(embeds=[static_embed, dynamic_embed], view=VacationView())
    await db.save_vacation_panel_info(msg.channel.id, msg.id)

@tasks.loop(hours=1)
async def check_vacation_expiry():
    """Раз в час проверяет завершившиеся отпуска"""
    expired_users = await db.get_expired_vacations()
    
    if expired_users:
        for user_id in expired_users:
            await db.remove_vacation_user(user_id)
        
        for guild in bot.guilds:
            await update_vacation_panel(guild)

async def setup_vacation_commands(bot_instance):
    global bot
    bot = bot_instance
    
    @bot.tree.command(name="setup_vacation", description="Отправить панель отпусков в текущий канал")
    @app_commands.default_permissions(administrator=True)
    async def setup_vacation(interaction: discord.Interaction):
        static_embed = create_static_vacation_embed()
        dynamic_embed = await create_dynamic_vacation_embed(interaction.guild)
        
        msg = await interaction.response.send_message(embeds=[static_embed, dynamic_embed], view=VacationView())
        await db.save_vacation_panel_info(interaction.channel_id, msg.id)
    
    @bot.tree.command(name="setup_vacation_channel", description="Установить канал для панели отпусков (админ)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="Канал для панели отпусков")
    async def setup_vacation_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        static_embed = create_static_vacation_embed()
        dynamic_embed = await create_dynamic_vacation_embed(interaction.guild)
        
        msg = await channel.send(embeds=[static_embed, dynamic_embed], view=VacationView())
        await db.save_vacation_panel_info(msg.channel.id, msg.id)
        await interaction.response.send_message(f"✅ Панель отпусков создана в канале {channel.mention}", ephemeral=True)
    
    @bot.tree.command(name="vacation_list", description="Показать список отпусков")
    async def vacation_list(interaction: discord.Interaction):
        embed = await create_dynamic_vacation_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @bot.tree.command(name="vacation_check", description="Проверить, в отпуске ли пользователь")
    @app_commands.describe(user="Пользователь для проверки")
    async def vacation_check(interaction: discord.Interaction, user: discord.Member):
        user_data = await db.get_vacation_user(user.id)
        
        if user_data:
            await interaction.response.send_message(
                f"✅ **{user.display_name}** сейчас в отпуске!\n"
                f"📝 Причина: {user_data['reason']}\n"
                f"📅 **С:** {user_data['start_str']}\n"
                f"📅 **По:** {user_data['end_str']}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(f"✅ **{user.display_name}** на месте!", ephemeral=True)