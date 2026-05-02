import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("CPS_DATA_DIR", BASE_DIR / "data"))
SPRITESHEET_DIR = DATA_DIR / "spritesheets"
SCREENSHOT_DIR = DATA_DIR / "screenshots"
PETS_DB_PATH = DATA_DIR / "pets.json"

MAX_SPRITESHEET_BYTES = 2 * 1024 * 1024
MAX_SPRITESHEET_DIM = 2048
MAX_SCREENSHOT_BYTES = 4 * 1024 * 1024
ALLOWED_SCREENSHOT_FORMATS = {"PNG", "JPEG", "WEBP", "GIF"}
SCREENSHOT_EXT = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp", "GIF": "gif"}

# Hand-picked names for the top row of the home grid. Missing pets are skipped.
FEATURED_PETS = ["ruckus"]

GRID_TOTAL = 8
GRID_FEATURED_SLOTS = 4

# Hard cap on the number of pets we'll accept. See README "Pet cap" section.
MAX_PETS = 1000

IP_HASH_SALT = os.environ.get("CPS_IP_SALT", "dev-salt-change-me")
