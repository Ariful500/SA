"""
bot.py — SA SMS WORK Bot মেইন ফাইল
"""
import logging
import asyncio
import os
import json
import subprocess
from collections import Counter
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

from config import BOT_TOKEN, ADMIN_ID, LIMIT_RESET_HOUR, DAILY_LIMIT, GROUP_CHAT_ID
import lamix
from database import (
    init_db, reset_all_limits, get_daily_limit,
    log_overage, get_user_by_lamix_username,
)
from user_commands import (
    start_command, link_command, unlink_command,
    account_command, cancel_command, add_nums_command,
)
from callbacks import handle_text, handle_callback
from admin_commands import (
    refresh_command, addlimit_command, leaderboard_command,
    fetchlimit_command, broadcast_command, ban_command,
    unban_command, userlist_command, reset_command,
    autoapprove_command,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

SHUTDOWN_AFTER_SECONDS = 5 * 3600 + 59 * 60  # 5h 59m


# ══════════════════════════════════════════════
#  SMS MONITOR
# ══════════════════════════════════════════════

SEEN_SMS_FILE = "seen_sms.json"
_seen_sms: set[str] = set()
_number_sms_count: dict[str, int] = {}


def _sms_unique_id(row: list) -> str:
    return f"{row[0]}|{row[2]}|{row[3]}|{str(row[5])[:20]}"


def _load_seen_sms():
    """JSON ফাইল থেকে seen SMS ও per-number count লোড করো"""
    global _seen_sms, _number_sms_count
    try:
        if os.path.exists(SEEN_SMS_FILE):
            with open(SEEN_SMS_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    _seen_sms = set(data.get("seen", []))
                    _number_sms_count = dict(data.get("counts", {}))
                else:
                    # পুরনো ফরম্যাট (শুধু লিস্ট) — ব্যাকওয়ার্ড কম্প্যাটিবিলিটি
                    _seen_sms = set(data)
                    _number_sms_count = {}
                logger.info(
                    f"✅ Seen SMS লোড হয়েছে: {len(_seen_sms)}টি, "
                    f"Counts: {len(_number_sms_count)}টি নম্বর"
                )
        else:
            _seen_sms = set()
            _number_sms_count = {}
    except Exception as e:
        logger.error(f"[SeenSMS] Load error: {e}")
        _seen_sms = set()
        _number_sms_count = {}


def _save_seen_sms():
    try:
        with open(SEEN_SMS_FILE, "w") as f:
            json.dump({"seen": list(_seen_sms), "counts": _number_sms_count}, f)
        subprocess.run(["git", "add", SEEN_SMS_FILE], check=False)
        result = subprocess.run(["git", "diff", "--staged", "--quiet"], capture_output=True)
        if result.returncode != 0:
            subprocess.run(["git", "commit", "-m", "💾 SMS seen list updated"], check=False)
            subprocess.run(["git", "push", "origin", "main"], check=False)
    except Exception as e:
        logger.error(f"[SeenSMS] Save error: {e}")


def _reset_seen_sms():
    """সকাল ৬টায় seen SMS ও per-number count রিসেট করো"""
    global _seen_sms, _number_sms_count
    _seen_sms = set()
    _number_sms_count = {}
    try:
        with open(SEEN_SMS_FILE, "w") as f:
            json.dump({"seen": [], "counts": {}}, f)
    except Exception as e:
        logger.error(f"[SeenSMS] Reset error: {e}")
    logger.info("🔄 SMS seen list রিসেট হয়েছে।")

async def sms_monitor_loop(app: Application):
    import datetime
    global _seen_sms

    logger.info("📡 SMS Monitor চালু হয়েছে...")

    while True:
        try:
            now_bd = datetime.datetime.utcnow() + datetime.timedelta(hours=6)

            if now_bd.hour < 6:
                start_bd = (now_bd - datetime.timedelta(days=1)).replace(
                    hour=6, minute=0, second=0, microsecond=0)
            else:
                start_bd = now_bd.replace(hour=6, minute=0, second=0, microsecond=0)

            start_utc = start_bd - datetime.timedelta(hours=6)
            end_utc = datetime.datetime.utcnow()

            fdate1 = start_utc.strftime("%Y-%m-%d %H:%M:%S")
            fdate2 = end_utc.strftime("%Y-%m-%d %H:%M:%S")

            rows = await lamix.fetch_sms_rows_async(fdate1, fdate2)

            new_rows = []
            for row in rows:
                uid = _sms_unique_id(row)
                if uid not in _seen_sms:
                    _seen_sms.add(uid)
                    new_rows.append(row)

            new_rows.sort(key=lambda r: str(r[0]))  # পুরনো → নতুন (chronological)

            number_limits = {}
            if new_rows:
                number_limits = await lamix.fetch_number_limits_async()

            for i, row in enumerate(new_rows):
                try:
                    date_str = str(row[0])
                    dt_utc = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    dt_bd = dt_utc + datetime.timedelta(hours=6)
                    time_str = dt_bd.strftime("%I:%M %p | %d.%m.%y")

                    range_name = str(row[1])
                    number     = str(row[2])
                    cli        = str(row[3])
                    sms_text   = str(row[5])

                    _number_sms_count[number] = _number_sms_count.get(number, 0) + 1
                    today_count = _number_sms_count[number]
                    info        = number_limits.get(number, {})
                    max_limit   = info.get("limit")
                    client_uname = info.get("client")

                    if max_limit is not None and today_count > max_limit:
                        # ── লিমিট ক্রস হয়ে গেছে ──
                        msg = (
                            f"⚠️ Limit Exceeded!\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"📞 Number : {number}\n"
                            f"📍 Range  : {range_name}\n"
                            f"📊 Today  : {today_count} SMS || Max - {max_limit} SMS\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"🚫 এই নম্বরের আজকের লিমিট শেষ।\n"
                            f"অন্য নম্বর ব্যবহার করুন।\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"🕐 {time_str}"
                        )
                        await app.bot.send_message(chat_id=GROUP_CHAT_ID, text=msg)

                        if client_uname:
                            await log_overage(client_uname, range_name)
                            target_user = await get_user_by_lamix_username(client_uname)
                            if target_user:
                                try:
                                    await app.bot.send_message(
                                        chat_id=target_user["user_id"],
                                        text=(
                                            f"⚠️ আপনার নম্বরের লিমিট শেষ!\n\n"
                                            f"📞 Number : {number}\n"
                                            f"📊 আজকে এসেছে : {today_count} SMS (Max: {max_limit})\n\n"
                                            f"এই নম্বরে আর নতুন SMS কাউন্ট হবে না।\n"
                                            f"দয়া করে /add_nums দিয়ে নতুন নম্বর নিন।"
                                        ),
                                    )
                                except Exception as e:
                                    logger.warning(f"[Overage DM] Failed: {e}")
                    else:
                        max_text = f"{max_limit} SMS" if max_limit is not None else "N/A"
                        msg = (
                            f"🔔 নতুন SMS এসেছে!\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"📞 Number : {number}\n"
                            f"📍 Range  : {range_name}\n"
                            f"🔖 CLI    : {cli}\n"
                            f"📊 Today  : {today_count} SMS || Max - {max_text}\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"💬 {sms_text}\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"🕐 {time_str}"
                        )
                        await app.bot.send_message(chat_id=GROUP_CHAT_ID, text=msg)

                    if (i + 1) % 25 == 0:
                        await asyncio.sleep(1)

                except Exception as e:
                    logger.error(f"[SMS Monitor] Send error: {e}")

            if new_rows:
                _save_seen_sms()  # এই ৫-সেকেন্ড ব্যাচের সব নতুন SMS একসাথে সেভ

        except Exception as e:
            logger.error(f"[SMS Monitor] Loop error: {e}")

        await asyncio.sleep(5)


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


async def auto_shutdown(app: Application):
    await asyncio.sleep(SHUTDOWN_AFTER_SECONDS)
    logger.info("⏰ ৫ ঘণ্টা ৫৯ মিনিট পার হয়েছে — বট গ্রেসফুলি বন্ধ হচ্ছে...")
    try:
        await app.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "⏰ ৫ ঘণ্টা ৫৯ মিনিট পার হয়ে গেছে।\n"
                "GitHub Actions এর ৬ ঘণ্টা লিমিট এড়াতে বট এখন নিজেই বন্ধ হচ্ছে "
                "(Job স্ট্যাটাস: ✅ Success)।"
            ),
        )
    except Exception as e:
        logger.warning(f"শাটডাউন নোটিস পাঠানো যায়নি: {e}")
    app.stop_running()


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
    BotCommand("refresh",     "সবার লিমিট রিসেট"),
    BotCommand("addlimit",    "ইউজারের লিমিট বাড়ান"),
    BotCommand("reset",       "ইউজার সম্পূর্ণ রিসেট"),
    BotCommand("leaderboard", "SMS র‍্যাংকিং"),
    BotCommand("fetchlimit",  "লিমিট সেটিংস"),
    BotCommand("broadcast",   "সবাইকে মেসেজ"),
    BotCommand("ban",         "ইউজার ব্যান"),
    BotCommand("unban",       "ইউজার আনব্যান"),
    BotCommand("userlist",    "সব ইউজার তালিকা"),
    BotCommand("autoapprove", "Auto-Approve টগল করুন"),
]

_GROUP_CMDS = [
    BotCommand("leaderboard", "SMS র‍্যাংকিং"),
]


async def post_init(app: Application):
    await init_db()
    _load_seen_sms()
    await app.bot.set_my_commands(_USER_CMDS)
    await app.bot.set_my_commands(_ADMIN_CMDS, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
    await app.bot.set_my_commands(_GROUP_CMDS, scope=BotCommandScopeAllGroupChats())

    session = await asyncio.to_thread(lamix._do_login)
    if session:
        logger.info("Lamix Login OK")
        await app.bot.send_message(chat_id=ADMIN_ID, text="Bot চালু! Lamix Login সফল।")
    else:
        logger.error("Lamix Login Failed")
        await app.bot.send_message(chat_id=ADMIN_ID, text="Lamix Login ব্যর্থ! Username/Password চেক করুন।")

    logger.info("DB & Commands initialized")

    asyncio.create_task(auto_shutdown(app))
    asyncio.create_task(sms_monitor_loop(app))
    logger.info("⏳ Auto-shutdown ও SMS Monitor চালু হয়েছে।")


# ══════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    PRIVATE_ONLY = filters.ChatType.PRIVATE

    # User
    app.add_handler(CommandHandler("start",    start_command,    filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("link",     link_command,     filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("unlink",   unlink_command,   filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("account",  account_command,  filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("add_nums", add_nums_command, filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("cancel",   cancel_command,   filters=PRIVATE_ONLY))

    # Admin
    app.add_handler(CommandHandler("refresh",     refresh_command,     filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("addlimit",    addlimit_command,    filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("reset",       reset_command,       filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CommandHandler("fetchlimit",  fetchlimit_command,  filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("broadcast",   broadcast_command,   filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("ban",         ban_command,         filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("unban",       unban_command,       filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("userlist",    userlist_command,    filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("autoapprove", autoapprove_command, filters=PRIVATE_ONLY))

    # Callback & Text
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & PRIVATE_ONLY, handle_text))

    # Scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        auto_reset_limits,
        CronTrigger(hour=LIMIT_RESET_HOUR, minute=0, timezone="Asia/Dhaka"),
        args=[app],
    )
    scheduler.add_job(
        _reset_seen_sms,
        CronTrigger(hour=6, minute=0, timezone="Asia/Dhaka"),
    )
    scheduler.start()

    logger.info("🚀 SA SMS WORK Bot চালু হয়েছে!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("✅ বট গ্রেসফুলি বন্ধ হয়েছে (exit code 0)।")


if __name__ == "__main__":
    main()
