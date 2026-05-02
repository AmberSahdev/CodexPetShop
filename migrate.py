"""One-shot migrator: copy every pet from the local store into the cloud store.

Usage:
  CPS_BUCKET=your-bucket GOOGLE_CLOUD_PROJECT=your-project .venv/bin/python migrate.py

Reads pets from data/pets.json + data/spritesheets/ + data/screenshots/, writes
to Firestore + GCS. Skips pets already in the cloud store.
"""
import os
import sys

# Force-load both backends regardless of CPS_BACKEND.
import local_store
os.environ.setdefault("CPS_BACKEND", "gcp")
import cloud_store


def main():
    pets = local_store.list_visible()
    if not pets:
        print("No local pets found."); return
    print(f"Found {len(pets)} local pets")
    for pet in pets:
        pid = pet["id"]
        if cloud_store.exists(pid):
            print(f"  · {pid}: already in cloud, skipping"); continue
        sprite = local_store.spritesheet_bytes(pid)
        if not sprite:
            print(f"  ✗ {pid}: missing spritesheet"); continue
        shot_path = local_store.get_screenshot_path(pet)
        shot_bytes = shot_path.read_bytes() if shot_path else None
        shot_ext = (shot_path.suffix.lstrip(".") if shot_path else None)
        try:
            cloud_store.create(
                pet_id=pid,
                display_name=pet["display_name"],
                description=pet["description"],
                spritesheet_bytes=sprite,
                ip_hash=pet.get("ip_hash", "migrated"),
                screenshot_bytes=shot_bytes,
                screenshot_ext=shot_ext,
            )
            print(f"  ✓ {pid} migrated")
        except Exception as e:
            print(f"  ✗ {pid}: {e}")


if __name__ == "__main__":
    main()
