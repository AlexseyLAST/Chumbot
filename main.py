import asyncio
import logging
import os
import uvicorn

from bot.discord_bot import TOKEN, bot
from web.app import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

async def main():
    # Render передаёт порт в переменную окружения PORT, по умолчанию для локала 8000
    port = int(os.getenv("PORT", 8000))

    config = uvicorn.Config(
        app, 
        host="0.0.0.0", 
        port=port, 
        loop="asyncio", 
        log_level="info",
        proxy_headers=True,       # Считывать заголовки X-Forwarded-Proto от Render
        forwarded_allow_ips="*"   # Доверять прокси Render
    )
    server = uvicorn.Server(config)

    async with bot:
        try:
            await asyncio.gather(
                bot.start(TOKEN),
                server.serve(),
            )
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        finally:
            if not bot.is_closed():
                await bot.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Chumbot] Успешно остановлен.")