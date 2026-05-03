"""Storage facade. Picks a backend based on CPS_BACKEND env var.

  CPS_BACKEND=local  → JSON file + filesystem (default; for dev)
  CPS_BACKEND=gcp    → Firestore + Cloud Storage (for App Engine)
"""
import os

_backend = os.environ.get("CPS_BACKEND", "local").lower()

if _backend == "gcp":
    from cloud_store import (  # noqa: F401
        get, exists, create, list_visible, count_visible, bump_download, grid_pets,
        spritesheet_url, screenshot_url, spritesheet_bytes, screenshot_bytes,
    )
else:
    from local_store import (  # noqa: F401
        get, exists, create, list_visible, count_visible, bump_download, grid_pets,
        spritesheet_url, screenshot_url, spritesheet_bytes, screenshot_bytes,
        get_spritesheet_path, get_screenshot_path,
    )
