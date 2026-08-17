import os
import httpx

# Переменная считывается из окружения (.env локально или Environment Variables на Render)
MOKKY_URL = os.getenv("MOKKY_URL")


async def get_messages_data() -> dict:
    """Получает сохраненный словарь сообщений из Mokky.dev (запись id=1)"""
    if not MOKKY_URL:
        print("Ошибка: Переменная MOKKY_URL не задана в .env!")
        return {}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{MOKKY_URL}/messages/1")
            response.raise_for_status()
            res = response.json()
            return res.get("data", {})
        except Exception as e:
            print(f"Ошибка при чтении из Mokky: {e}")
            return {}


async def save_messages_data(data: dict) -> dict:
    """Сохраняет обновленный словарь сообщений в Mokky.dev (запись id=1)"""
    if not MOKKY_URL:
        print("Ошибка: Переменная MOKKY_URL не задана в .env!")
        return {}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.patch(
                f"{MOKKY_URL}/messages/1", json={"data": data}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Ошибка при сохранении в Mokky: {e}")
            return {}