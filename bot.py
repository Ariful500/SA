"""
bot.py — SA SMS WORK Bot মেইন ফাইল
"""
import logging
import asyncio
from telegram import Update, BotCommand, BotCommandScopeChat, BotCommandScopeAllGroupChats
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
import lamix
from database import init_db, reset_all_limits, get_daily_limit
from handlers import (
    # user
    start_command, link_command, unlink_command,
    account_command, cancel_command, handle_text,
    # admin
    refresh_command, addlimit_command, leaderboard_command,
    fetchlimit_command, broadcast_command, ban_command,
    unban_command, userlist_command, reset_command,
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
    current_limit = await get_daily_limit()
    await app.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🔄 অটো লিমিট রিসেট সম্পন্ন!\n\n✅ {count} জন ইউজারের লিমিট {current_limit} হয়েছে।",
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
    BotCommand("reset",      "ইউজার সম্পূর্ণ রিসেট"),
    BotCommand("leaderboard","SMS র‍্যাংকিং"),
    BotCommand("fetchlimit", "লিমিট সেটিংস"),
    BotCommand("broadcast",  "সবাইকে মেসেজ"),
    BotCommand("ban",        "ইউজার ব্যান"),
    BotCommand("unban",      "ইউজার আনব্যান"),
    BotCommand("userlist",   "সব ইউজার তালিকা"),
]

# গ্রুপ চ্যাটে শুধু /leaderboard কমান্ডটাই দেখানো ও কাজ করানো হবে
_GROUP_CMDS = [
    BotCommand("leaderboard", "SMS র‍্যাংকিং"),
]


async def post_init(app: Application):
    await init_db()
    await app.bot.set_my_commands(_USER_CMDS)
    await app.bot.set_my_commands(_ADMIN_CMDS, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
    await app.bot.set_my_commands(_GROUP_CMDS, scope=BotCommandScopeAllGroupChats())

    # bot start হওয়ার সাথে সাথে Lamix login
    session = await asyncio.to_thread(lamix._do_login)
    if session:
        logger.info("Lamix Login OK")
        await app.bot.send_message(chat_id=ADMIN_ID, text="Bot চালু! Lamix Login সফল।")
    else:
        logger.error("Lamix Login Failed")
        await app.bot.send_message(chat_id=ADMIN_ID, text="Lamix Login ব্যর্থ! Username/Password চেক করুন।")

    logger.info("DB & Commands initialized")


# ══════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # ══════════════════════════════════════════════
    #  গ্রুপ চ্যাটে শুধু /leaderboard কাজ করবে,
    #  বাকি সব কমান্ড ও টেক্সট মেসেজ চুপ থাকবে (no reply)।
    #  প্রাইভেট (DM) চ্যাটে সবকিছু আগের মতোই কাজ করবে।
    # ══════════════════════════════════════════════
    PRIVATE_ONLY = filters.ChatType.PRIVATE

    # User
    app.add_handler(CommandHandler("start",    start_command,    filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("link",     link_command,     filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("unlink",   unlink_command,   filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("account",  account_command,  filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("add_nums", add_nums_command, filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("cancel",   cancel_command,   filters=PRIVATE_ONLY))

    # Admin
    app.add_handler(CommandHandler("refresh",    refresh_command,    filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("addlimit",   addlimit_command,   filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("reset",      reset_command,      filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("leaderboard",leaderboard_command))  # গ্রুপ + প্রাইভেট দুটোতেই কাজ করবে
    app.add_handler(CommandHandler("fetchlimit", fetchlimit_command, filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("broadcast",  broadcast_command,  filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("ban",        ban_command,        filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("unban",      unban_command,      filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("userlist",   userlist_command,   filters=PRIVATE_ONLY))

    # Callback & Text — শুধু প্রাইভেট চ্যাটে
    app.add_handler(CallbackQueryHandler(handle_callback))  # callback সাধারণত DM থেকেই আসা বাটনের, তাই unrestricted রাখা হয়েছে
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & PRIVATE_ONLY, handle_text))

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
