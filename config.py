import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Lamix Configuration
LAMIX_URL      = os.getenv("LAMIX_URL")
LAMIX_USERNAME = os.getenv("LAMIX_USERNAME")
LAMIX_PASSWORD = os.getenv("LAMIX_PASSWORD")

# Limit Configuration
DAILY_LIMIT       = 120
LIMIT_RESET_HOUR  = 6  # সকাল ৬টা
MAX_PER_ORDER     = 30

# Database
DATABASE_NAME = "sa_sms_work.db"
