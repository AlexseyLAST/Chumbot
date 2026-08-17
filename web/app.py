"""
Веб-панель на FastAPI с авторизацией через Discord OAuth2.
"""

import os
import re
from pathlib import Path

import httpx
from fastapi import FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from bot import storage
from bot.discord_bot import (
    bot,
    delete_message,
    edit_message,
    get_all_text_channels,
    send_message,
)

BASE_DIR = Path(__file__).resolve().parent

# --- Переменные окружения ---
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://127.0.0.1:8000/auth/callback")
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-change-me")

# Список Discord ID, которым разрешен доступ (через запятую в .env)
ALLOWED_USERS = [
    int(uid.strip())
    for uid in os.getenv("ALLOWED_DISCORD_USERS", "").split(",")
    if uid.strip()
]

app = FastAPI(title="Discord Rules Manager")

# 1. Сначала подключаем ProxyHeadersMiddleware
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

# 2. Затем SessionMiddleware с включенным https_only
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="chumbot_session",
    same_site="lax",
    https_only=True,  # Обязательно True для работы кук на HTTPS
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# --- Проверка авторизации ---
def check_auth(request: Request) -> dict:
    user = request.session.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"},
        )
    return user


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9а-яА-Я]+", "-", name.strip().lower()).strip("-")
    return slug or "message"


# --- OAuth2 Маршруты ---
@app.get("/login")
async def login():
    discord_auth_url = (
        f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify"
    )
    return RedirectResponse(discord_auth_url)


@app.get("/auth/callback")
async def callback(request: Request, code: str):
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    async with httpx.AsyncClient() as client:
        # 1. Обмениваем код на токен
        token_res = await client.post("https://discord.com/api/v10/oauth2/token", data=data, headers=headers)
        if token_res.status_code != 200:
            return HTMLResponse("Ошибка авторизации в Discord", status_code=400)
        
        access_token = token_res.json()["access_token"]

        # 2. Получаем данные пользователя
        user_res = await client.get(
            "https://discord.com/api/v10/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_data = user_res.json()

    user_id = int(user_data["id"])

    print(f"\n[АВТОРИЗАЦИЯ] Твой Discord ID: {user_id}\n")

    # 3. Проверяем, есть ли пользователь в белом списке
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        return HTMLResponse("У вас нет доступа к этой панели.", status_code=403)

    # Сохраняем в сессию
    request.session["user"] = {
        "id": user_data["id"],
        "username": user_data["username"],
        "avatar": user_data.get("avatar"),
    }
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")


# --- Защищенные маршруты панели ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    check_auth(request)
    entries = storage.load_all()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "entries": entries,
            "bot_ready": bot.is_ready(),
            "bot_user": str(bot.user) if bot.user else None,
            "current_user": request.session.get("user"),
        },
    )


@app.get("/new", response_class=HTMLResponse)
async def new_form(request: Request):
    check_auth(request)
    channels = get_all_text_channels() if bot.is_ready() else []
    return templates.TemplateResponse(
        request=request,
        name="edit.html",
        context={
            "channels": channels,
            "entry": None,
            "key": None,
            "bot_ready": bot.is_ready(),
        },
    )


@app.post("/new")
async def create_message(
    request: Request,
    name: str = Form(...),
    channel_id: int = Form(...),
    content: str = Form(""),
    use_embed: bool = Form(False),
    embed_title: str = Form(""),
    embed_color: str = Form("5865F2"),
):
    check_auth(request)
    key = slugify(name)
    embed_data = {"title": embed_title, "description": content, "color": embed_color} if use_embed else None
    message = await send_message(channel_id, content=(None if use_embed else content), embed_data=embed_data)

    storage.upsert(
        key,
        {
            "name": name,
            "channel_id": channel_id,
            "message_id": message.id,
            "content": content,
            "use_embed": use_embed,
            "embed_title": embed_title,
            "embed_color": embed_color,
        },
    )
    return RedirectResponse("/", status_code=303)


@app.get("/edit/{key}", response_class=HTMLResponse)
async def edit_form(request: Request, key: str):
    check_auth(request)
    entry = storage.get(key)
    channels = get_all_text_channels() if bot.is_ready() else []
    return templates.TemplateResponse(
        request=request,
        name="edit.html",
        context={
            "channels": channels,
            "entry": entry,
            "key": key,
            "bot_ready": bot.is_ready(),
        },
    )


@app.post("/edit/{key}")
async def update_message(
    request: Request,
    key: str,
    content: str = Form(""),
    use_embed: bool = Form(False),
    embed_title: str = Form(""),
    embed_color: str = Form("5865F2"),
):
    check_auth(request)
    entry = storage.get(key)
    if not entry:
        return RedirectResponse("/", status_code=303)

    embed_data = {"title": embed_title, "description": content, "color": embed_color} if use_embed else None
    try:
        await edit_message(
            entry["channel_id"],
            entry["message_id"],
            content=(None if use_embed else content),
            embed_data=embed_data,
        )
    except Exception as exc:
        # Запись в Mokky не меняем, если Discord не принял правку.
        print(f"[Edit Error] Не удалось обновить сообщение {entry['message_id']} в Discord: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Discord не принял изменение сообщения. Запись в панели не изменена.",
        ) from exc

    entry.update(
        {
            "content": content,
            "use_embed": use_embed,
            "embed_title": embed_title,
            "embed_color": embed_color,
        }
    )
    storage.upsert(key, entry)
    return RedirectResponse("/", status_code=303)


@app.post("/delete/{key}")
async def remove_message(request: Request, key: str):
    check_auth(request)
    entry = storage.get(key)
    
    if entry:
        # Сначала удаляем в Discord. Запись в Mokky удаляется только при успехе.
        try:
            await delete_message(entry["channel_id"], entry["message_id"])
        except Exception as exc:
            print(f"[Delete Error] Не удалось удалить сообщение {entry['message_id']} из Discord: {exc}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Discord не удалил сообщение. Запись в панели сохранена.",
            ) from exc

        storage.delete(key)

    return RedirectResponse("/", status_code=303)
