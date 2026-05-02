"""Firestore + Cloud Storage backend. Same API surface as local_store."""
import os
import random
import time
from typing import Optional

from google.cloud import firestore, storage
from google.api_core.exceptions import AlreadyExists

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
BUCKET_NAME = os.environ["CPS_BUCKET"]  # required
COLLECTION = os.environ.get("CPS_COLLECTION", "pets")

_db = firestore.Client(project=PROJECT)
_gcs = storage.Client(project=PROJECT)
_bucket = _gcs.bucket(BUCKET_NAME)

SPRITE_PREFIX = "spritesheets/"
SHOT_PREFIX = "screenshots/"

# Public URL pattern: bucket must be readable by allUsers (set once at deploy time).
_PUBLIC_URL = f"https://storage.googleapis.com/{BUCKET_NAME}"


def _doc_to_pet(snap) -> Optional[dict]:
    if not snap.exists:
        return None
    d = snap.to_dict() or {}
    if d.get("takedown"):
        return None
    return d


def get(pet_id: str) -> Optional[dict]:
    return _doc_to_pet(_db.collection(COLLECTION).document(pet_id).get())


def exists(pet_id: str) -> bool:
    return _db.collection(COLLECTION).document(pet_id).get().exists


def _upload(path: str, data: bytes, content_type: str) -> None:
    blob = _bucket.blob(path)
    blob.cache_control = "public, max-age=31536000, immutable"
    blob.upload_from_string(data, content_type=content_type)


def create(pet_id: str, display_name: str, description: str,
           spritesheet_bytes: bytes, ip_hash: str,
           screenshot_bytes: Optional[bytes] = None,
           screenshot_ext: Optional[str] = None) -> dict:
    doc_ref = _db.collection(COLLECTION).document(pet_id)
    if doc_ref.get().exists:
        raise ValueError("name_taken")

    sprite_path = f"{SPRITE_PREFIX}{pet_id}.webp"
    _upload(sprite_path, spritesheet_bytes, "image/webp")

    screenshot_filename = None
    if screenshot_bytes and screenshot_ext:
        screenshot_filename = f"{pet_id}.{screenshot_ext}"
        _upload(
            f"{SHOT_PREFIX}{screenshot_filename}",
            screenshot_bytes,
            f"image/{screenshot_ext if screenshot_ext != 'jpg' else 'jpeg'}",
        )

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
    # Firestore create() is transactional: fails with AlreadyExists if doc was just created.
    try:
        doc_ref.create(pet)
    except AlreadyExists:
        raise ValueError("name_taken")
    return pet


def list_visible() -> list[dict]:
    out = []
    for snap in _db.collection(COLLECTION).where("takedown", "==", False).stream():
        d = snap.to_dict()
        if d:
            out.append(d)
    return out


def count_visible() -> int:
    """Cheap aggregate count (1 read regardless of collection size)."""
    agg = _db.collection(COLLECTION).where("takedown", "==", False).count().get()
    # `agg` is list[list[AggregationResult]]
    return int(agg[0][0].value)


def grid_pets(featured_ids: list[str], total: int, featured_slots: int) -> list[dict]:
    """Pull every visible pet, then sample in Python.
    Fine up to a few hundred pets; cheap (1 Firestore query per pageload).
    No composite index needed."""
    all_pets = list_visible()
    by_id = {p["id"]: p for p in all_pets}

    featured = [by_id[i] for i in featured_ids if i in by_id][:featured_slots]
    feat_ids = {p["id"] for p in featured}

    rest = [p for p in all_pets if p["id"] not in feat_ids]
    random.shuffle(rest)
    rest = rest[: total - len(featured)]
    return featured + rest


def spritesheet_url(pet: dict) -> str:
    return f"{_PUBLIC_URL}/{SPRITE_PREFIX}{pet['id']}.webp"


def screenshot_url(pet: dict) -> Optional[str]:
    fn = pet.get("screenshot_filename")
    return f"{_PUBLIC_URL}/{SHOT_PREFIX}{fn}" if fn else None


def spritesheet_bytes(pet_id: str) -> Optional[bytes]:
    blob = _bucket.blob(f"{SPRITE_PREFIX}{pet_id}.webp")
    if not blob.exists():
        return None
    return blob.download_as_bytes()
