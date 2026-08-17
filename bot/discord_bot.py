"""
Ядро Discord-бота.

Здесь создаётся клиент discord.py и низкоуровневые функции для
отправки, редактирования и удаления сообщений — их дергает веб-панель.
"""

import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError(
        "Не задан BOT_TOKEN. Скопируйте .env.example в .env и вставьте туда токен бота."
    )

DEFAULT_COLOR = "5865F2"  # стандартный "blurple" Discord

intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True  # обязательно включить в Discord Developer Portal -> Bot -> Privileged Intents

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"[bot] Подключен как {bot.user} (ID: {bot.user.id})")


def get_all_text_channels():
    """Список (guild, channel) для всех текстовых каналов, доступных боту."""
    result = []
    for guild in bot.guilds:
        for channel in guild.text_channels:
            result.append((guild, channel))
    return result


def build_embed(title: str = "", description: str = "", color_hex: str = DEFAULT_COLOR) -> discord.Embed:
    kwargs = {}
    if title:
        kwargs["title"] = title
    if description:
        kwargs["description"] = description
    try:
        color_int = int((color_hex or DEFAULT_COLOR).lstrip("#"), 16)
    except ValueError:
        color_int = int(DEFAULT_COLOR, 16)
    kwargs["color"] = discord.Color(color_int)
    return discord.Embed(**kwargs)


async def _get_channel(channel_id: int | str) -> discord.abc.Messageable:
    """Возвращает канал Discord, независимо от типа ID из хранилища."""
    channel_id = int(channel_id)
    channel = bot.get_channel(channel_id)
    if channel is None:
        channel = await bot.fetch_channel(channel_id)
    return channel


async def send_message(channel_id: int, content: str | None = None, embed_data: dict | None = None) -> discord.Message:
    channel = await _get_channel(channel_id)
    embed = build_embed(**{k: v for k, v in (embed_data or {}).items() if k in ("title", "description", "color_hex")}) if embed_data else None
    if embed_data and "color" in embed_data:
        # позволяем передавать ключ "color" вместо "color_hex" для удобства вызова
        embed = build_embed(embed_data.get("title", ""), embed_data.get("description", ""), embed_data.get("color", DEFAULT_COLOR))
    return await channel.send(content=content, embed=embed)


async def edit_message(channel_id: int | str, message_id: int | str, content: str | None = None, embed_data: dict | None = None) -> discord.Message:
    """Обновляет сообщение и передаёт ошибку Discord вызывающему коду."""
    channel = await _get_channel(channel_id)
    message = await channel.fetch_message(int(message_id))
    embed = None
    if embed_data:
        embed = build_embed(embed_data.get("title", ""), embed_data.get("description", ""), embed_data.get("color", DEFAULT_COLOR))
    await message.edit(content=content, embed=embed)
    return message


async def delete_message(channel_id: int | str, message_id: int | str):
    """Удаляет сообщение из канала Discord по его ID."""
    c_id = int(channel_id)
    m_id = int(message_id)
    channel = await _get_channel(c_id)
    message = await channel.fetch_message(m_id)
    await message.delete()
    print(f"[Discord] Сообщение {m_id} успешно удалено из канала {c_id}.")
