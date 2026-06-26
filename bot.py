import logging
import asyncio
from telegram import Update, BotCommand, BotCommandScopeChat
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import BOT_TOKEN, ADMIN_ID, LIMIT_RESET_HOUR
from database import init_db, reset_all_limits
from handlers.user import (
    start_command,
    link_command,
    unlink_command,
    account_command,
    cancel_command,
    handle_text,
)
from handlers.admin import (
    refresh_command,
    addlimit_command,
    leaderboard_command,
    fetchlimit_command,
    broadcast_command,
    ban_command,
    unban_command,
    userlist_command,
)
from handlers.allocation import (
    add_nums_command,
    handle_callback,
)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ✅ অটো লিমিট রিসেট — সকাল ৬টা
async def auto_reset_limits(app: Application):
    count = await reset_all_limits()
    await app.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🔄 অটো লিমিট রিসেট সম্পন্ন!\n\n✅ {count} জন ইউজারের লিমিট 120 হয়েছে।",
    )
    logger.info(f"Auto reset done for {count} users")


# ✅ ইউজার মেনু সেট
async def set_user_commands(app: Application):
    user_commands = [
        BotCommand("start", "বট শুরু করুন"),
        BotCommand("link", "Lamix অ্যাকাউন্ট কানেক্ট করুন"),
        BotCommand("unlink", "অ্যাকাউন্ট ডিসকানেক্ট করুন"),
        BotCommand("account", "অ্যাকাউন্ট তথ্য দেখুন"),
        BotCommand("add_nums", "নম্বর ব্রাউজ ও নিন"),
    ]
    await app.bot.set_my_commands(user_commands)


# ✅ অ্যাডমিন মেনু সেট
async def set_admin_commands(app: Application):
    admin_commands = [
        BotCommand("start", "বট শুরু করুন"),
        BotCommand("link", "Lamix অ্যাকাউন্ট কানেক্ট করুন"),
        BotCommand("unlink", "অ্যাকাউন্ট ডিসকানেক্ট করুন"),
        BotCommand("account", "অ্যাকাউন্ট তথ্য দেখুন"),
        BotCommand("add_nums", "নম্বর ব্রাউজ ও নিন"),
        BotCommand("refresh", "সবার লিমিট রিসেট করুন"),
        BotCommand("addlimit", "ইউজারের লিমিট বাড়ান"),
        BotCommand("leaderboard", "SMS র‍্যাংকিং দেখুন"),
        BotCommand("fetchlimit", "লিমিট সেটিংস দেখুন"),
        BotCommand("broadcast", "সবাইকে মেসেজ পাঠান"),
        BotCommand("ban", "ইউজার ব্যান করুন"),
        BotCommand("unban", "ইউজার আনব্যান করুন"),
        BotCommand("userlist", "সব ইউজারের তালিকা"),
    ]
    await app.bot.set_my_commands(
        admin_commands,
        scope=BotCommandScopeChat(chat_id=ADMIN_ID),
    )


async def post_init(app: Application):
    await init_db()
    await set_user_commands(app)
    await set_admin_commands(app)
    logger.info("✅ Database & Commands initialized")


def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # ✅ User Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("link", link_command))
    app.add_handler(CommandHandler("unlink", unlink_command))
    app.add_handler(CommandHandler("account", account_command))
    app.add_handler(CommandHandler("add_nums", add_nums_command))
    app.add_handler(CommandHandler("cancel", cancel_command))

    # ✅ Admin Handlers
    app.add_handler(CommandHandler("refresh", refresh_command))
    app.add_handler(CommandHandler("addlimit", addlimit_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CommandHandler("fetchlimit", fetchlimit_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("userlist", userlist_command))

    # ✅ Callback Query Handler (বাটন প্রেস)
    app.add_handler(CallbackQueryHandler(handle_callback))

    # ✅ Text Handler (Search + Link username input)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )

    # ✅ Scheduler — সকাল ৬টায় অটো রিসেট
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
                   
