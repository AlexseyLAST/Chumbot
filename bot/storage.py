import os
import httpx

MOKKY_URL = os.getenv("MOKKY_URL")


def _get_headers():
    return {"Content-Type": "application/json"}


def load_all() -> dict:
    """Загружает все сообщения из Mokky.dev"""
    if not MOKKY_URL:
        print("[Mokky] Ошибка: MOKKY_URL не задан в переменных окружения.")
        return {}
    try:
        response = httpx.get(f"{MOKKY_URL}/messages/1", headers=_get_headers(), timeout=5.0)
        response.raise_for_status()
        return response.json().get("data", {})
    except Exception as e:
        print(f"[Mokky Error] Ошибка загрузки данных: {e}")
        return {}


def get(key: str) -> dict | None:
    """Получает одно сообщение по ключу"""
    all_data = load_all()
    return all_data.get(key)


def upsert(key: str, entry: dict):
    """Добавляет или обновляет сообщение по ключу в Mokky.dev"""
    all_data = load_all()
    all_data[key] = entry
    _save_all(all_data)


def delete(key: str):
    """Удаляет сообщение по ключу из Mokky.dev"""
    all_data = load_all()
    if key in all_data:
        del all_data[key]
        _save_all(all_data)


def _save_all(data: dict):
    """Вспомогательная функция сохранения всего объекта в Mokky.dev"""
    if not MOKKY_URL:
        return
    try:
        httpx.patch(
            f"{MOKKY_URL}/messages/1",
            json={"data": data},
            headers=_get_headers(),
            timeout=5.0,
        )
    except Exception as e:
        print(f"[Mokky Error] Ошибка сохранения данных: {e}")