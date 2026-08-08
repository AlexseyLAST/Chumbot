"""
Очень простое персистентное хранилище на JSON-файле.

Хранит соответствие "человекочитаемое имя сообщения" -> {канал, id
сообщения в Discord, текст, параметры embed}. Этого достаточно для
одного сервера/небольшой команды; при желании легко заменить на
SQLite, поменяв только этот файл.
"""

import json
from pathlib import Path
from threading import Lock

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_FILE = DATA_DIR / "messages.json"
_lock = Lock()


def _ensure_file() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text("{}", encoding="utf-8")


def load_all() -> dict:
    _ensure_file()
    with _lock:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_all(data: dict) -> None:
    _ensure_file()
    with _lock:
        DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get(key: str) -> dict | None:
    return load_all().get(key)


def upsert(key: str, entry: dict) -> None:
    data = load_all()
    data[key] = entry
    save_all(data)


def delete(key: str) -> None:
    data = load_all()
    data.pop(key, None)
    save_all(data)
