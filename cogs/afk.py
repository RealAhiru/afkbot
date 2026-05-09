# cogs/afk.py
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import pytz
from config import ALLOWED_ROLES, TIMEZONE, BOT_FOOTER, AFK_CHANNEL_ID

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

def format_return_time(return_time):
    """Форматирует время возврата"""
    return return_time.strftime("%H:%M")

def format_full_time(return_time):
    """Форматирует полное время для ЛС"""
    return return_time.strftime("%d.%m.%Y в %H:%M")

def create_static_afk_embed() -> discord.Embed:
    """Создаёт статичный embed с инструкцией по AFK"""
    embed = discord.Embed(
        title="🚶‍♂️ AFK Система",
        description=(
            "**Как оставить AFK отчёт?**\n\n"
            "1️⃣ Нажми на кнопку **«Отошел»**\n"
            "2️⃣ Укажи причину отсутствия\n"
            "3️⃣ Укажи время отсутствия (1-8 часов)\n"
            "4️⃣ Ты появишься в списке AFK\n\n"
            "**Как вернуться?**\n"
            "• Нажми на кнопку **«Вернулся»**\n"
            "• Подтверди слово «вернулся»\n\n"
            "⏰ **Важно:** Если ты не вернёшься вовремя, тебя исключат из списка автоматически!"
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text=BOT_FOOTER)
    return embed

async def create_dynamic_afk_embed(guild) -> discord.Embed:
    """Создаёт динамический embed со списком AFK"""
    afk_users = await db.get_all_afk_users()
    now = get_msk_time()
    
    active_afk = {uid: data for uid, data in afk_users.items() if now < data["return_time"]}
    
    if not active_afk:
        embed = discord.Embed(
            title="📊 Текущие AFK",
            description="🎉 **Никого нет в AFK!**\n\nВсе на месте, можно работать!",
            color=discord.Color.green()
        )
        return embed
    
    sorted_users = sorted(active_afk.items(), key=lambda x: x[1]["return_time"])
    description = f"👥 **Сейчас в AFK: {len(sorted_users)}** человек(а)\n\n"
    
    for index, (user_id, data) in enumerate(sorted_users, start=1):
        user = guild.get_member(user_id)
        if user:
            time_str = format_return_time(data["return_time"])
            description += f"**{index}.** {user.mention} | 📝 {data['reason']} | ⏰ вернётся в: **{time_str}**\n"
        else:
            description += f"**{index}.** Пользователь {user_id} | 📝 {data['reason']} | ⏰ вернётся в: **{format_return_time(data['return_time'])}**\n"
    
    embed = discord.Embed(
        title="📊 Текущие AFK",
        description=description,
        color=discord.Color.orange()
    )
    return embed

class AFKModal(discord.ui.Modal, title="🚶 Уход в AFK"):
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
                await auto_delete_message(interaction, "❌ Введи число от 1 до 8!", 3)
                return
        except ValueError:
            await auto_delete_message(interaction, "❌ Введи число!", 3)
            return
        
        if ALLOWED_ROLES:
            user_roles = [role.id for role in interaction.user.roles]
            if not any(role_id in user_roles for role_id in ALLOWED_ROLES) and not interaction.user.guild_permissions.administrator:
                await auto_delete_message(interaction, "❌ У тебя нет прав для использования AFK!", 3)
                return
        
        now = get_msk_time()
        return_time = now + timedelta(hours=hours)
        
        await db.save_afk_user(
            user_id=interaction.user.id,
            user_name=interaction.user.name,
            reason=self.reason.value,
            hours=hours,
            return_time=return_time,
            start_time=now
        )
        
        await update_afk_panel(interaction.guild)
        
        await auto_delete_message(
            interaction,
            f"✅ Ты ушёл в AFK!\n📝 Причина: {self.reason.value}\n⏰ Вернёшься: {format_full_time(return_time)} (МСК)",
            5
        )

class ReturnConfirmModal(discord.ui.Modal, title="✅ Подтверждение возврата"):
    confirm = discord.ui.TextInput(
        label="Введи 'вернулся' для подтверждения",
        placeholder="вернулся",
        required=True,
        max_length=10,
        min_length=7
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.confirm.value.lower() == "вернулся":
            user_data = await db.get_afk_user(interaction.user.id)
            if user_data:
                await db.remove_afk_user(interaction.user.id)
                await update_afk_panel(interaction.guild)
                
                await auto_delete_message(
                    interaction,
                    f"✅ Добро пожаловать обратно!\nТы отсутствовал: {user_data['hours']} час(а/ов)\n📝 Причина была: {user_data['reason']}",
                    5
                )
            else:
                await auto_delete_message(interaction, "❌ Тебя нет в списке AFK!", 3)
        else:
            await auto_delete_message(interaction, "❌ Неправильное проверочное слово!", 3)

class AFKView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🚶 Отошел", style=discord.ButtonStyle.primary, custom_id="afk_go_button")
    async def go_afk(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AFKModal())
    
    @discord.ui.button(label="✅ Вернулся", style=discord.ButtonStyle.success, custom_id="afk_back_button")
    async def back_from_afk(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_data = await db.get_afk_user(interaction.user.id)
        if not user_data:
            await auto_delete_message(interaction, "❌ Тебя нет в списке AFK!", 3)
            return
        
        await interaction.response.send_modal(ReturnConfirmModal())

async def update_afk_panel(guild):
    """Обновляет панель AFK (статичный embed + динамический + кнопки)"""
    panel_info = await db.get_afk_panel_info()
    
    static_embed = create_static_afk_embed()
    dynamic_embed = await create_dynamic_afk_embed(guild)
    
    if panel_info:
        channel = guild.get_channel(panel_info["channel_id"])
        if channel:
            try:
                message = await channel.fetch_message(panel_info["message_id"])
                # Отправляем два embed в одном сообщении
                await message.edit(embeds=[static_embed, dynamic_embed], view=AFKView())
                return
            except:
                pass
    
    # Если панель не найдена, создаём новую
    if AFK_CHANNEL_ID:
        channel = guild.get_channel(AFK_CHANNEL_ID)
    else:
        channel = guild.system_channel or guild.text_channels[0]
    
    if not channel:
        channel = guild.text_channels[0]
    
    msg = await channel.send(embeds=[static_embed, dynamic_embed], view=AFKView())
    await db.save_afk_panel_info(msg.channel.id, msg.id)

@tasks.loop(minutes=1)
async def check_afk_expiry():
    """Каждую минуту проверяет просроченных AFK"""
    expired_users = await db.get_expired_afk_users()
    
    if expired_users:
        for user_id in expired_users:
            await db.remove_afk_user(user_id)
        
        for guild in bot.guilds:
            await update_afk_panel(guild)

async def setup_afk_commands(bot_instance):
    global bot
    bot = bot_instance
    
    @bot.tree.command(name="setup_afk", description="Отправить панель AFK в текущий канал")
    @app_commands.default_permissions(administrator=True)
    async def setup_afk(interaction: discord.Interaction):
        static_embed = create_static_afk_embed()
        dynamic_embed = await create_dynamic_afk_embed(interaction.guild)
        
        msg = await interaction.response.send_message(embeds=[static_embed, dynamic_embed], view=AFKView())
        await db.save_afk_panel_info(interaction.channel_id, msg.id)
    
    @bot.tree.command(name="setup_afk_channel", description="Установить канал для AFK панели (админ)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="Канал для панели AFK")
    async def setup_afk_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        static_embed = create_static_afk_embed()
        dynamic_embed = await create_dynamic_afk_embed(interaction.guild)
        
        msg = await channel.send(embeds=[static_embed, dynamic_embed], view=AFKView())
        await db.save_afk_panel_info(msg.channel.id, msg.id)
        await interaction.response.send_message(f"✅ Панель AFK создана в канале {channel.mention}", ephemeral=True)
    
    @bot.tree.command(name="afk_list", description="Показать список AFK")
    async def afk_list(interaction: discord.Interaction):
        embed = await create_dynamic_afk_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @bot.tree.command(name="afk_check", description="Проверить, в AFK ли пользователь")
    @app_commands.describe(user="Пользователь для проверки")
    async def afk_check(interaction: discord.Interaction, user: discord.Member):
        user_data = await db.get_afk_user(user.id)
        
        if user_data:
            now = get_msk_time()
            remaining = user_data["return_time"] - now
            hours_left = remaining.total_seconds() / 3600
            
            await interaction.response.send_message(
                f"✅ **{user.display_name}** сейчас в AFK!\n"
                f"📝 Причина: {user_data['reason']}\n"
                f"⏰ Вернётся: {format_full_time(user_data['return_time'])}\n"
                f"⌛ Осталось: {int(hours_left)} ч {int(remaining.total_seconds() % 3600 // 60)} мин",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(f"✅ **{user.display_name}** на месте!", ephemeral=True)