"""
bot.py — SA SMS WORK Bot মেইন ফাইল
"""
import logging
from telegram import Update, BotCommand, BotCommandScopeChat
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import BOT_TOKEN, ADMIN_ID, LIMIT_RESET_HOUR, DAILY_LIMIT
from database import init_db, reset_all_limits
from handlers import (
    # user
    start_command, link_command, unlink_command,
    account_command, cancel_command, handle_text,
    # admin
    refresh_command, addlimit_command, leaderboard_command,
    fetchlimit_command, broadcast_command, ban_command,
    unban_command, userlist_command,
    # allocation
    add_nums_command, handle_callback,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
#  SCHEDULED JOBS
# ══════════════════════════════════════════════

async def auto_reset_limits(app: Application):
    count = await reset_all_limits()
    await app.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🔄 অটো লিমিট রিসেট সম্পন্ন!\n\n✅ {count} জন ইউজারের লিমিট {DAILY_LIMIT} হয়েছে।",
    )
    logger.info(f"Auto reset done for {count} users")


# ══════════════════════════════════════════════
#  BOT COMMANDS MENU
# ══════════════════════════════════════════════

_USER_CMDS = [
    BotCommand("start",    "বট শুরু করুন"),
    BotCommand("link",     "Lamix অ্যাকাউন্ট কানেক্ট"),
    BotCommand("unlink",   "অ্যাকাউন্ট ডিসকানেক্ট"),
    BotCommand("account",  "অ্যাকাউন্ট তথ্য দেখুন"),
    BotCommand("add_nums", "নম্বর ব্রাউজ ও নিন"),
]

_ADMIN_CMDS = _USER_CMDS + [
    BotCommand("refresh",    "সবার লিমিট রিসেট"),
    BotCommand("addlimit",   "ইউজারের লিমিট বাড়ান"),
    BotCommand("leaderboard","SMS র‍্যাংকিং"),
    BotCommand("fetchlimit", "লিমিট সেটিংস"),
    BotCommand("broadcast",  "সবাইকে মেসেজ"),
    BotCommand("ban",        "ইউজার ব্যান"),
    BotCommand("unban",      "ইউজার আনব্যান"),
    BotCommand("userlist",   "সব ইউজার তালিকা"),
]


async def post_init(app: Application):
    await init_db()
    await app.bot.set_my_commands(_USER_CMDS)
    await app.bot.set_my_commands(_ADMIN_CMDS, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
    logger.info("✅ DB ও Commands initialized")


# ══════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # User
    app.add_handler(CommandHandler("start",    start_command))
    app.add_handler(CommandHandler("link",     link_command))
    app.add_handler(CommandHandler("unlink",   unlink_command))
    app.add_handler(CommandHandler("account",  account_command))
    app.add_handler(CommandHandler("add_nums", add_nums_command))
    app.add_handler(CommandHandler("cancel",   cancel_command))

    # Admin
    app.add_handler(CommandHandler("refresh",    refresh_command))
    app.add_handler(CommandHandler("addlimit",   addlimit_command))
    app.add_handler(CommandHandler("leaderboard",leaderboard_command))
    app.add_handler(CommandHandler("fetchlimit", fetchlimit_command))
    app.add_handler(CommandHandler("broadcast",  broadcast_command))
    app.add_handler(CommandHandler("ban",        ban_command))
    app.add_handler(CommandHandler("unban",      unban_command))
    app.add_handler(CommandHandler("userlist",   userlist_command))

    # Callback & Text
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        auto_reset_limits,
        CronTrigger(hour=LIMIT_RESET_HOUR, minute=0),
        args=[app],
    )
    scheduler.start()

    logger.info("🚀 SA SMS WORK Bot চালু হয়েছে!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
    
