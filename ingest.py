"""Ingest pet directories from data/incoming/.

Each subdirectory's name is the pet id, and must contain:
  - pet.json
  - spritesheet.webp

Usage:
  .venv/bin/python ingest.py            # ingest every dir in data/incoming/
  .venv/bin/python ingest.py ruckus     # ingest just data/incoming/ruckus/
"""
import json
import shutil
import sys
from pathlib import Path

import config
import store
from pet_schema import validate_pet_json

INCOMING = config.DATA_DIR / "incoming"


def ingest_one(pet_dir: Path) -> bool:
    pet_id = pet_dir.name.lower()
    pet_json = pet_dir / "pet.json"
    sprite = pet_dir / "spritesheet.webp"

    if not pet_json.exists():
        print(f"  ✗ {pet_id}: missing pet.json"); return False
    if not sprite.exists():
        print(f"  ✗ {pet_id}: missing spritesheet.webp"); return False

    try:
        manifest = json.loads(pet_json.read_text())
    except json.JSONDecodeError as e:
        print(f"  ✗ {pet_id}: pet.json is invalid JSON ({e})"); return False

    errs = validate_pet_json(manifest)
    if errs:
        print(f"  ✗ {pet_id}: {'; '.join(errs)}"); return False

    if manifest["id"] != pet_id:
        print(f'  ✗ {pet_id}: pet.json id "{manifest["id"]}" must match folder name')
        return False

    if store.exists(pet_id):
        print(f"  ✗ {pet_id}: already exists in store"); return False

    sprite_bytes = sprite.read_bytes()
    if len(sprite_bytes) > config.MAX_SPRITESHEET_BYTES:
        print(f"  ✗ {pet_id}: spritesheet exceeds 2 MB"); return False

    from app import make_thumbnail
    try:
        screenshot_bytes = make_thumbnail(sprite_bytes)
        screenshot_ext = "png"
    except Exception as e:
        print(f"  ✗ {pet_id}: thumbnail generation failed ({e})"); return False

    store.create(
        pet_id=pet_id,
        display_name=manifest["displayName"],
        description=manifest["description"],
        spritesheet_bytes=sprite_bytes,
        ip_hash="ingest",
        screenshot_bytes=screenshot_bytes,
        screenshot_ext=screenshot_ext,
    )
    shutil.rmtree(pet_dir)
    print(f"  ✓ {pet_id} ingested")
    return True


def main(argv):
    INCOMING.mkdir(parents=True, exist_ok=True)
    targets = []
    if len(argv) > 1:
        for name in argv[1:]:
            targets.append(INCOMING / name)
    else:
        targets = [p for p in INCOMING.iterdir() if p.is_dir()]

    if not targets:
        print(f"nothing to ingest in {INCOMING}"); return

    print(f"ingesting {len(targets)} pet(s)…")
    for d in targets:
        if not d.is_dir():
            print(f"  ✗ {d.name}: not a directory"); continue
        ingest_one(d)


if __name__ == "__main__":
    main(sys.argv)
