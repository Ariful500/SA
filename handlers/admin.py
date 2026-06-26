from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_ID, DAILY_LIMIT
from database import (
    reset_all_limits,
    add_user_limit,
    get_leaderboard,
    get_total_sms,
    get_all_users,
    ban_user,
    unban_user,
    get_user,
)


# ✅ অ্যাডমিন চেক
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ✅ /refresh — সবার লিমিট রিসেট
async def refresh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 এই কমান্ড শুধু অ্যাডমিনের জন্য।")
        return

    count = await reset_all_limits()
    await update.message.reply_text(
        f"🔄 *All Limits Reset Successfully!*\n\n"
        f"✅ {count} জন ইউজারের লিমিট {DAILY_LIMIT} হয়েছে।",
        parse_mode="Markdown",
    )


# ✅ /addlimit — ইউজারের লিমিট বাড়ানো
async def addlimit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 এই কমান্ড শুধু অ্যাডমিনের জন্য।")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ সঠিকভাবে লিখুন:\n`/addlimit USER_ID AMOUNT`\n\nউদাহরণ: `/addlimit 123456789 50`",
            parse_mode="Markdown",
        )
        return

    try:
        target_id = int(args[0])
        amount = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ USER_ID এবং AMOUNT অবশ্যই সংখ্যা হতে হবে।")
        return

    user = await get_user(target_id)
    if not user:
        await update.message.reply_text("❌ এই User ID তে কোনো ইউজার পাওয়া যায়নি।")
        return

    await add_user_limit(target_id, amount)

    # ইউজারকে নোটিফাই করো
    await context.bot.send_message(
        chat_id=target_id,
        text=f"🎉 *আপনার লিমিট বাড়ানো হয়েছে!*\n\n"
             f"➕ Added: *{amount}*\n"
             f"📊 New Limit: *{user['daily_limit'] + amount}*",
        parse_mode="Markdown",
    )

    await update.message.reply_text(
        f"✅ *Limit Added!*\n\n"
        f"👤 User: `{target_id}`\n"
        f"➕ Added: *{amount}*",
        parse_mode="Markdown",
    )


# ✅ /leaderboard — SMS র‍্যাংকিং
async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await get_leaderboard()
    total = await get_total_sms()

    if not rows:
        await update.message.reply_text("📊 এখনো কোনো ডেটা নেই।")
        return

    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 *SMS Leaderboard*\n\n"

    for i, row in enumerate(rows):
        uname = f"@{row['telegram_username']}" if row['telegram_username'] else row['username']
        if i < 3:
            text += f"{medals[i]} {uname} — *{row['total_allocated']}*\n"
        else:
            text += f"{i + 1}️⃣ {uname} — *{row['total_allocated']}*\n"

    text += f"\n📊 Total SMS Allocated: *{total:,}*"

    import datetime
    now = datetime.datetime.now().strftime("%I:%M %p")
    text += f"\n⏰ Updated: {now}"

    await update.message.reply_text(text, parse_mode="Markdown")


# ✅ /fetchlimit — লিমিট সেটিংস দেখা
async def fetchlimit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 এই কমান্ড শুধু অ্যাডমিনের জন্য।")
        return

    await update.message.reply_text(
        f"⚙️ *Limit Settings*\n\n"
        f"📊 Daily Limit: *{DAILY_LIMIT}*\n"
        f"⏰ Auto Reset: প্রতিদিন সকাল *৬:০০ AM*\n"
        f"🔢 Max per order: *30*",
        parse_mode="Markdown",
    )


# ✅ /broadcast — সবাইকে মেসেজ
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 এই কমান্ড শুধু অ্যাডমিনের জন্য।")
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ সঠিকভাবে লিখুন:\n`/broadcast আপনার মেসেজ`",
            parse_mode="Markdown",
        )
        return

    message = " ".join(context.args)
    users = await get_all_users()

    sent = 0
    failed = 0
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user["user_id"],
                text=f"📢 *Admin Broadcast*\n\n{message}",
                parse_mode="Markdown",
            )
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"📢 *Broadcast Complete!*\n\n"
        f"✅ Sent: *{sent}*\n"
        f"❌ Failed: *{failed}*",
        parse_mode="Markdown",
    )


# ✅ /ban — ইউজার ব্যান
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 এই কমান্ড শুধু অ্যাডমিনের জন্য।")
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ সঠিকভাবে লিখুন:\n`/ban USER_ID`",
            parse_mode="Markdown",
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ USER_ID অবশ্যই সংখ্যা হতে হবে।")
        return

    user = await get_user(target_id)
    if not user:
        await update.message.reply_text("❌ এই User ID তে কোনো ইউজার পাওয়া যায়নি।")
        return

    await ban_user(target_id)

    try:
        await context.bot.send_message(
            chat_id=target_id,
            text="🚫 আপনাকে ব্যান করা হয়েছে। এডমিনের সাথে যোগাযোগ করুন।",
        )
    except Exception:
        pass

    await update.message.reply_text(
        f"🚫 *User Banned!*\n\n"
        f"👤 User: `{target_id}`\n"
        f"🧑 Username: *{user['username']}*",
        parse_mode="Markdown",
    )


# ✅ /unban — ইউজার আনব্যান
async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 এই কমান্ড শুধু অ্যাডমিনের জন্য।")
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ সঠিকভাবে লিখুন:\n`/unban USER_ID`",
            parse_mode="Markdown",
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ USER_ID অবশ্যই সংখ্যা হতে হবে।")
        return

    user = await get_user(target_id)
    if not user:
        await update.message.reply_text("❌ এই User ID তে কোনো ইউজার পাওয়া যায়নি।")
        return

    await unban_user(target_id)

    try:
        await context.bot.send_message(
            chat_id=target_id,
            text="✅ আপনার ব্যান তুলে নেওয়া হয়েছে। এখন বট ব্যবহার করতে পারবেন।",
        )
    except Exception:
        pass

    await update.message.reply_text(
        f"✅ *User Unbanned!*\n\n"
        f"👤 User: `{target_id}`\n"
        f"🧑 Username: *{user['username']}*",
        parse_mode="Markdown",
    )


# ✅ /userlist — সব ইউজারের তালিকা
async def userlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 এই কমান্ড শুধু অ্যাডমিনের জন্য।")
        return

    users = await get_all_users()

    if not users:
        await update.message.reply_text("📋 এখনো কোনো ইউজার নেই।")
        return

    text = f"👥 *User List* ({len(users)} জন)\n\n"
    for i, user in enumerate(users, 1):
        status = "🚫" if user["is_banned"] else "✅"
        uname = f"@{user['telegram_username']}" if user["telegram_username"] else "N/A"
        text += (
            f"{i}. {status} {uname}\n"
            f"   🧑 `{user['username']}` | 📊 {user['daily_used']}/{user['daily_limit']} | 🔄 {user['total_allocated']}\n\n"
        )

    # মেসেজ বড় হলে ভাগ করে পাঠাও
    if len(text) > 4000:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")
  
