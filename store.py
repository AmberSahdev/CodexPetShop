"""Local filesystem-backed store. Swap for Firestore + GCS later behind same API."""
import json
import os
import random
import threading
import time
from pathlib import Path
from typing import Optional

from config import PETS_DB_PATH, SPRITESHEET_DIR, SCREENSHOT_DIR

_lock = threading.Lock()


def _ensure_dirs():
    SPRITESHEET_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    PETS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not PETS_DB_PATH.exists():
        PETS_DB_PATH.write_text("{}")


def _read_all() -> dict:
    _ensure_dirs()
    try:
        return json.loads(PETS_DB_PATH.read_text() or "{}")
    except json.JSONDecodeError:
        return {}


def _write_all(data: dict) -> None:
    tmp = PETS_DB_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, PETS_DB_PATH)


def get(pet_id: str) -> Optional[dict]:
    pet = _read_all().get(pet_id)
    if pet and not pet.get("takedown"):
        return pet
    return None


def exists(pet_id: str) -> bool:
    return get(pet_id) is not None


def create(pet_id: str, display_name: str, description: str,
           spritesheet_bytes: bytes, ip_hash: str,
           screenshot_bytes: Optional[bytes] = None,
           screenshot_ext: Optional[str] = None) -> dict:
    """Atomic-ish create: rejects if id exists, writes files then db."""
    with _lock:
        data = _read_all()
        if pet_id in data:
            raise ValueError("name_taken")
        (SPRITESHEET_DIR / f"{pet_id}.webp").write_bytes(spritesheet_bytes)
        screenshot_filename = None
        if screenshot_bytes and screenshot_ext:
            screenshot_filename = f"{pet_id}.{screenshot_ext}"
            (SCREENSHOT_DIR / screenshot_filename).write_bytes(screenshot_bytes)
        pet = {
            "id": pet_id,
            "display_name": display_name,
            "description": description,
            "spritesheet_filename": f"{pet_id}.webp",
            "screenshot_filename": screenshot_filename,
            "random": random.random(),
            "created_at": time.time(),
            "ip_hash": ip_hash,
            "takedown": False,
        }
        data[pet_id] = pet
        _write_all(data)
        return pet


def list_visible() -> list[dict]:
    return [p for p in _read_all().values() if not p.get("takedown")]


def get_spritesheet_path(pet_id: str) -> Path:
    return SPRITESHEET_DIR / f"{pet_id}.webp"


def get_screenshot_path(pet: dict) -> Optional[Path]:
    fn = pet.get("screenshot_filename")
    if not fn:
        return None
    p = SCREENSHOT_DIR / fn
    return p if p.exists() else None


def grid_pets(featured_ids: list[str], total: int, featured_slots: int) -> list[dict]:
    """Return up to `total` pets: featured row first (in order), then random."""
    all_pets = list_visible()
    by_id = {p["id"]: p for p in all_pets}

    featured = [by_id[i] for i in featured_ids if i in by_id][:featured_slots]
    featured_set = {p["id"] for p in featured}

    rest = [p for p in all_pets if p["id"] not in featured_set]
    random.shuffle(rest)
    rest = rest[: total - len(featured)]
    return featured + rest
