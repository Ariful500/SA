import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required.")

_admin_raw = os.getenv("ADMIN_ID")
if not _admin_raw:
    raise RuntimeError("ADMIN_ID environment variable is required.")
try:
    ADMIN_ID = int(_admin_raw)
except ValueError:
    raise RuntimeError(f"ADMIN_ID must be an integer, got: {_admin_raw!r}")

_group_raw = os.getenv("GROUP_CHAT_ID")
if not _group_raw:
    raise RuntimeError("GROUP_CHAT_ID environment variable is required.")
try:
    GROUP_CHAT_ID = int(_group_raw)
except ValueError:
    raise RuntimeError(f"GROUP_CHAT_ID must be an integer, got: {_group_raw!r}")

# Lamix Configuration
LAMIX_URL      = os.getenv("LAMIX_URL")
LAMIX_USERNAME = os.getenv("LAMIX_USERNAME")
LAMIX_PASSWORD = os.getenv("LAMIX_PASSWORD")

# Limit Configuration
DAILY_LIMIT       = 120
LIMIT_RESET_HOUR  = 6
MAX_PER_ORDER     = 30
