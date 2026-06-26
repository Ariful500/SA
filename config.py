import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Lamix API Configuration
LAMIX_API_KEY = os.getenv("LAMIX_API_KEY")
LAMIX_API_URL = os.getenv("LAMIX_API_URL")

# Limit Configuration
DAILY_LIMIT = 120
LIMIT_RESET_HOUR = 6  # সকাল ৬টা

# Database
DATABASE_NAME = "sa_sms_work.db"
