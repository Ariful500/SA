import datetime
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import ADMIN_ID
from database import (
    get_user, reset_all_limits, reset_user_usage, add_user_limit,
    ban_user, unban_user, get_all_users, reset_member,
    get_daily_limit, get_max_per_order, set_daily_limit, set_max_per_order,
    get_user_by_telegram_username, get_leaderboard, get_total_sms,
)
from user_commands import is_admin, _extract_username_arg


# ══════════════════════════════════════════════
#  ADMIN COMMANDS
# ══════════════════════════════════════════════

async def refresh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 শুধু অ্যাডমিনের জন্য।")
        return
    count = await reset_all_limits()
    current_limit = await get_daily_limit()
    await update.message.reply_text(
        f"🔄 *All Limits Reset!*\n\n✅ {count} জন ইউজারের লিমিট {current_limit} হয়েছে।",
        parse_mode="Markdown",
    )


async def addlimit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 শুধু অ্যাডমিনের জন্য।")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ সঠিকভাবে লিখুন:\n`/addlimit @Username AMOUNT`",
            parse_mode="Markdown",
        )
        return

    tg_username = _extract_username_arg(args[0])
    try:
        amount = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ AMOUNT সংখ্যা হতে হবে।")
        return

    user = await get_user_by_telegram_username(tg_username)
    if not user:
        await update.message.reply_text(f"❌ `@{tg_username}` ইউজার পাওয়া যায়নি।", parse_mode="Markdown")
        return

    target_id = user["user_id"]
    await add_user_limit(target_id, amount)
    await context.bot.send_message(
        chat_id=target_id,
        text=f"🎉 *লিমিট বাড়ানো হয়েছে!*\n\n➕ Added: *{amount}*\n📊 New Limit: *{user['daily_limit'] + amount}*",
        parse_mode="Markdown",
    )
    await update.message.reply_text(
        f"✅ *Limit Added!*\n\n👤 User: @{tg_username}\n➕ Added: *{amount}*",
        parse_mode="Markdown",
    )


# নতুন
async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import datetime
    import json

    # সরাসরি JSON থেকে পড়া
    try:
        with open("leaderboard_sms.json", "r") as f:
            _leaderboard_counts = {
                k: v for k, v in json.load(f).get("counts", {}).items()
                if k and k.lower() != "none"
            }
    except Exception:
        _leaderboard_counts = {}

    try:
        with open("alltime_leaderboard.json", "r") as f:
            _alltime_counts = {
                k: v for k, v in json.load(f).get("counts", {}).items()
                if k and k.lower() != "none"
            }
    except Exception:
        _alltime_counts = {}

    bd_time = datetime.datetime.utcnow() + datetime.timedelta(hours=6)
    now_str = bd_time.strftime("%I:%M %p")
    date_str = bd_time.strftime("%d %B %Y")

    medals = ["🥇", "🥈", "🥉"]

    # ── Today ──
    today_text = "🏆 *Today SMS Leaderboard* 🏆\n\n"
    if _leaderboard_counts:
        sorted_today = sorted(_leaderboard_counts.items(), key=lambda x: x[1], reverse=True)
        for i, (client, count) in enumerate(sorted_today[:20]):
            masked = client[:-3] + "×××" if len(client) > 3 else "×××"
            prefix = medals[i] if i < 3 else f"{i+1}\\."
            today_text += f"{prefix} {masked} — *{count}*\n"
    else:
        today_text += "আজকে এখনো কোনো SMS আসেনি।"

    # ── All Time ──
    alltime_text = "🌟 *All Time Leaderboard* 🌟\n\n"
    if _alltime_counts:
        sorted_alltime = sorted(_alltime_counts.items(), key=lambda x: x[1], reverse=True)
        for i, (client, count) in enumerate(sorted_alltime[:20]):
            masked = client[:-3] + "×××" if len(client) > 3 else "×××"
            prefix = medals[i] if i < 3 else f"{i+1}\\."
            alltime_text += f"{prefix} {masked} — *{count:,}*\n"
    else:
        alltime_text += "এখনো কোনো data নেই।"

    text = (
        f"{today_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{alltime_text}\n\n"
        f"⏰ {now_str} | {date_str}"
    )

    await update.message.reply_text(text, parse_mode="Markdown")

    bd_time = datetime.datetime.utcnow() + datetime.timedelta(hours=6)
    now_str = bd_time.strftime("%I:%M %p")
    date_str = bd_time.strftime("%d %B %Y")

    # ── Today ──
    text = "🏆 *Today SMS Leaderboard*\n\n"
    if _leaderboard_counts:
        sorted_today = sorted(_leaderboard_counts.items(), key=lambda x: x[1], reverse=True)
        total_today = sum(c for _, c in sorted_today)
        medals = ["🥇", "🥈", "🥉"]
        for i, (client, count) in enumerate(sorted_today[:20]):
            masked = (client[:-3] + "***") if len(client) > 3 else "***"
            prefix = medals[i] if i < 3 else f"{i+1}."
            text += f"{prefix} {masked} — *{count}*\n"
        text += f"\n📊 Total: *{total_today:,} SMS*\n"
        text += f"⏰ {now_str} | {date_str}"
    else:
        text += "আজকে এখনো কোনো SMS আসেনি।"

    # ── All Time ──
    text += "\n\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n\n"
    text += "🌟 *All Time Leaderboard*\n\n"
    if _alltime_counts:
        sorted_alltime = sorted(_alltime_counts.items(), key=lambda x: x[1], reverse=True)
        total_alltime = sum(c for _, c in sorted_alltime)
        medals = ["🥇", "🥈", "🥉"]
        for i, (client, count) in enumerate(sorted_alltime[:20]):
            masked = (client[:-3] + "***") if len(client) > 3 else "***"
            prefix = medals[i] if i < 3 else f"{i+1}."
            text += f"{prefix} {masked} — *{count:,}*\n"
        text += f"\n📊 Total: *{total_alltime:,} SMS*"
    else:
        text += "এখনো কোনো data নেই।"

    await update.message.reply_text(text, parse_mode="Markdown")

async def fetchlimit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 শুধু অ্যাডমিনের জন্য।")
        return
    current_daily_limit = await get_daily_limit()
    current_max_per_order = await get_max_per_order()
    keyboard = [
        [InlineKeyboardButton("✏️ Daily Limit বদলান", callback_data="edit_daily_limit")],
        [InlineKeyboardButton("✏️ Max Per Order বদলান", callback_data="edit_max_per_order")],
    ]
    await update.message.reply_text(
        f"⚙️ *Limit Settings*\n\n"
        f"📊 Daily Limit: *{current_daily_limit}*\n"
        f"⏰ Auto Reset: সকাল *৬:০০ AM*\n"
        f"🔢 Max per order: *{current_max_per_order}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 শুধু অ্যাডমিনের জন্য।")
        return
    if not context.args:
        await update.message.reply_text("⚠️ `/broadcast আপনার মেসেজ`", parse_mode="Markdown")
        return
    message = " ".join(context.args)
    users = await get_all_users()
    sent = failed = 0
    for u in users:
        try:
            await context.bot.send_message(
                chat_id=u["user_id"],
                text=f"📢 *Admin Broadcast*\n\n{message}",
                parse_mode="Markdown",
            )
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(
        f"📢 *Broadcast Complete!*\n\n✅ Sent: *{sent}*\n❌ Failed: *{failed}*",
        parse_mode="Markdown",
    )


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 শুধু অ্যাডমিনের জন্য।")
        return
    if not context.args:
        await update.message.reply_text("⚠️ `/ban @Username`", parse_mode="Markdown")
        return

    tg_username = _extract_username_arg(context.args[0])
    user = await get_user_by_telegram_username(tg_username)
    if not user:
        await update.message.reply_text(f"❌ `@{tg_username}` ইউজার পাওয়া যায়নি।", parse_mode="Markdown")
        return

    target_id = user["user_id"]
    await ban_user(target_id)
    try:
        await context.bot.send_message(chat_id=target_id, text="🚫 আপনাকে ব্যান করা হয়েছে।")
    except Exception:
        pass
    await update.message.reply_text(
        f"🚫 *User Banned!*\n\n👤 User: @{tg_username}\n🧑 Username: *{user['username']}*",
        parse_mode="Markdown",
    )


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 শুধু অ্যাডমিনের জন্য।")
        return
    if not context.args:
        await update.message.reply_text("⚠️ `/unban @Username`", parse_mode="Markdown")
        return

    tg_username = _extract_username_arg(context.args[0])
    user = await get_user_by_telegram_username(tg_username)
    if not user:
        await update.message.reply_text(f"❌ `@{tg_username}` ইউজার পাওয়া যায়নি।", parse_mode="Markdown")
        return

    target_id = user["user_id"]
    await unban_user(target_id)
    try:
        await context.bot.send_message(chat_id=target_id, text="✅ ব্যান তুলে নেওয়া হয়েছে।")
    except Exception:
        pass
    await update.message.reply_text(
        f"✅ *User Unbanned!*\n\n👤 User: @{tg_username}\n🧑 Username: *{user['username']}*",
        parse_mode="Markdown",
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 শুধু অ্যাডমিনের জন্য।")
        return
    if not context.args:
        await update.message.reply_text("⚠️ `/reset @Username`", parse_mode="Markdown")
        return

    tg_username = _extract_username_arg(context.args[0])
    user = await get_user_by_telegram_username(tg_username)
    if not user:
        await update.message.reply_text(f"❌ `@{tg_username}` ইউজার পাওয়া যায়নি।", parse_mode="Markdown")
        return

    target_id = user["user_id"]
    keyboard = [[
        InlineKeyboardButton("✅ Confirm Reset", callback_data=f"confirm_reset_{target_id}"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
    ]]
    await update.message.reply_text(
        f"⚠️ *@{tg_username}* কে সম্পূর্ণ রিসেট করবেন?\n\n"
        f"🧑 Lamix Username: *{user['username']}*\n"
        f"📊 Used: {user['daily_used']}/{user['daily_limit']}\n"
        f"🔄 Total Allocated: {user['total_allocated']}\n\n"
        f"⚠️ এটি করলে তার লিঙ্ক, লিমিট, ইউসেজ — সবকিছু মুছে যাবে। তাকে আবার /link করতে হবে।",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def userlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 শুধু অ্যাডমিনের জন্য।")
        return
    try:
        users = await get_all_users()
        if not users:
            await update.message.reply_text("📋 এখনো কোনো ইউজার নেই।")
            return
        text = f"👥 User List ({len(users)} জন)\n\n"
        for i, u in enumerate(users, 1):
            status = "🚫" if u["is_banned"] else "✅"
            tg_uname = u.get("telegram_username") or "N/A"
            uname = f"@{tg_uname}"
            lamix_uname = u.get("username") or "Not Linked"
            text += (
                f"{i}. {status} {uname}\n"
                f"   🧑 {lamix_uname} | 📊 {u['daily_used']}/{u['daily_limit']} | 🔄 {u['total_allocated']}\n\n"
            )
        if len(text) > 4000:
            for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"❌ Userlist Error: {e}")


async def autoapprove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 শুধু অ্যাডমিনের জন্য।")
        return
    from database import get_auto_approve, set_auto_approve
    current = await get_auto_approve()
    new_state = not current
    await set_auto_approve(new_state)
    state_text = "✅ চালু" if new_state else "❌ বন্ধ"
    await update.message.reply_text(
        f"🤖 *Auto-Approve এখন {state_text}!*\n\n"
        f"{'ON থাকলে Request Limit Reset এ ১০ সেকেন্ড পর অটো রিসেট হবে।' if new_state else 'OFF থাকলে Admin কে manually Approve/Deny করতে হবে।'}",
        parse_mode="Markdown",
    )
