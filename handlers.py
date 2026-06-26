import datetime
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import ADMIN_ID
from database import (
    get_user, add_user, unlink_user,
    update_usage, reset_all_limits, reset_user_usage, add_user_limit,
    ban_user, unban_user, get_all_users, get_leaderboard, get_total_sms,
    is_username_taken, get_user_by_telegram_username, reset_member,
    get_daily_limit, get_max_per_order, set_daily_limit, set_max_per_order,
    has_pending_reset_request, set_pending_reset_request,
)
import lamix

# handlers_logic.py থেকে সব helper import করা হচ্ছে
from handlers_logic import (
    is_admin, _check_linked,
    _show_ranges, _show_search_results,
    _handle_quantity_input,
)


# ══════════════════════════════════════════════
#  USER COMMANDS
# ══════════════════════════════════════════════

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🔗 Link Account", callback_data="link"),
            InlineKeyboardButton("❌ Unlink", callback_data="unlink"),
        ],
        [InlineKeyboardButton("➕ Browse Ranges", callback_data="add_nums")],
    ]
    await update.message.reply_text(
        "👋 *Welcome to SA SMS WORK*\n\n"
        "📌 *Commands*\n"
        "🔗 /link — Lamix অ্যাকাউন্ট কানেক্ট\n"
        "❌ /unlink — অ্যাকাউন্ট ডিসকানেক্ট\n"
        "👤 /account — অ্যাকাউন্ট তথ্য\n"
        "➕ /add\\_nums — রেঞ্জ ব্রাউজ করুন\n\n"
        "🔍 যেকোনো টেক্সট পাঠিয়ে রেঞ্জ সার্চ করুন।",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    if user:
        await update.message.reply_text(
            f"⚠️ ইতিমধ্যে লিঙ্ক করা আছেন!\nঅ্যাকাউন্ট: *{user['username']}*\n\nআনলিঙ্ক করতে /unlink দিন।",
            parse_mode="Markdown",
        )
        return
    context.user_data["waiting_for_username"] = True
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
    await update.message.reply_text(
        "👤 *Lamix username পাঠান:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def unlink_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    if not user:
        await update.message.reply_text("⚠️ কোনো অ্যাকাউন্ট লিঙ্ক নেই।")
        return
    keyboard = [[
        InlineKeyboardButton("✅ Confirm", callback_data="confirm_unlink"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
    ]]
    await update.message.reply_text(
        f"⚠️ *{user['username']}* আনলিঙ্ক করবেন?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_linked(update):
        return
    user = await get_user(update.effective_user.id)
    keyboard = [[InlineKeyboardButton("❌ Unlink Account", callback_data="confirm_unlink")]]
    await update.message.reply_text(
        f"👤 *Account Information*\n"
        f"{'━' * 22}\n\n"
        f"🧑 Username: *{user['username']}*\n\n"
        f"📊 *Today's Usage*\n"
        f"• 🔢 Used: *{user['daily_used']}/{user['daily_limit']}*\n"
        f"• 🔄 Total Allocated: *{user['total_allocated']}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ বাতিল করা হয়েছে।")


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

    tg_username = args[0].strip().lstrip("@")
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
        prefix = medals[i] if i < 3 else f"{i+1}️⃣"
        text += f"{prefix} {uname} — *{row['total_allocated']}*\n"
    now = datetime.datetime.now().strftime("%I:%M %p")
    text += f"\n📊 Total SMS: *{total:,}*\n⏰ Updated: {now}"
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

    tg_username = context.args[0].strip().lstrip("@")
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

    tg_username = context.args[0].strip().lstrip("@")
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

    tg_username = context.args[0].strip().lstrip("@")
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
        f"⚠️ এটি করলে তার লিঙ্ক, লিমিট, ইউসেজ — সবকিছু মুছে যাবে।",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def userlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 শুধু অ্যাডমিনের জন্য।")
        return
    users = await get_all_users()
    if not users:
        await update.message.reply_text("📋 এখনো কোনো ইউজার নেই।")
        return
    text = f"👥 *User List* ({len(users)} জন)\n\n"
    for i, u in enumerate(users, 1):
        status = "🚫" if u["is_banned"] else "✅"
        uname = f"@{u['telegram_username']}" if u["telegram_username"] else "N/A"
        text += (
            f"{i}. {status} {uname}\n"
            f"   🧑 `{u['username']}` | 📊 {u['daily_used']}/{u['daily_limit']} | 🔄 {u['total_allocated']}\n\n"
        )
    if len(text) > 4000:
        for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
            await update.message.reply_text(chunk, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")


# ══════════════════════════════════════════════
#  ADD NUMS COMMAND
# ══════════════════════════════════════════════

async def add_nums_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    if not user:
        await update.message.reply_text("⚠️ /link দিয়ে আগে অ্যাকাউন্ট লিঙ্ক করুন।")
        return
    if user["is_banned"]:
        await update.message.reply_text("🚫 আপনি ব্যান হয়েছেন।")
        return
    if user["daily_used"] >= user["daily_limit"]:
        keyboard = [[InlineKeyboardButton("🔄 Request Limit Reset", callback_data="request_reset")]]
        await update.message.reply_text(
            f"⚠️ *Daily Limit Exceeded!*\n\nআজকের {user['daily_limit']}টি লিমিট শেষ।\nকাল সকাল ৬টায় অটো রিসেট হবে।",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return
    await _show_ranges(update, context, page=0)


# ══════════════════════════════════════════════
#  TEXT HANDLER
# ══════════════════════════════════════════════

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if context.user_data.get("waiting_for_new_daily_limit"):
        context.user_data.clear()
        try:
            new_limit = int(text)
            if new_limit < 1:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ ১ বা তার বেশি একটা সংখ্যা দিন।")
            return
        affected = await set_daily_limit(new_limit)
        await update.message.reply_text(
            f"✅ *Daily Limit বদলানো হয়েছে!*\n\n"
            f"📊 নতুন Daily Limit: *{new_limit}*\n"
            f"👥 {affected} জন ইউজারের লিমিট এখনই আপডেট হয়েছে।",
            parse_mode="Markdown",
        )
        return

    if context.user_data.get("waiting_for_new_max_per_order"):
        context.user_data.clear()
        try:
            new_max = int(text)
            if new_max < 1:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ ১ বা তার বেশি একটা সংখ্যা দিন।")
            return
        await set_max_per_order(new_max)
        await update.message.reply_text(
            f"✅ *Max Per Order বদলানো হয়েছে!*\n\n"
            f"🔢 নতুন Max Per Order: *{new_max}*\n"
            f"⏰ পরের অর্ডার থেকেই কার্যকর হবে।",
            parse_mode="Markdown",
        )
        return

    if context.user_data.get("waiting_for_username"):
        context.user_data.clear()
        lamix_username = text.strip()

        if await is_username_taken(lamix_username):
            keyboard = [[InlineKeyboardButton("🔗 অন্য Username দিন", callback_data="link")]]
            await update.message.reply_text(
                f"❌ *এই username টি অন্য কেউ ব্যবহার করছে!*\n\n"
                f"`{lamix_username}` ইতিমধ্যে লিঙ্ক করা আছে।",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        await update.message.reply_text("⏳ যাচাই করা হচ্ছে...")
        client_id, ok = await lamix.verify_username_async(lamix_username)

        if ok:
            tg_username = update.effective_user.username or str(user_id)
            await add_user(user_id, tg_username, lamix_username, client_id)
            await update.message.reply_text(
                f"✅ *সফলভাবে লিঙ্ক হয়েছে!*\n\n"
                f"👤 Lamix Account: *{lamix_username}*\n"
                f"🆔 Client ID: `{client_id}`\n\n"
                f"এখন /add\_nums দিয়ে নম্বর নিন। 🎉",
                parse_mode="Markdown",
            )
        else:
            keyboard = [[InlineKeyboardButton("🔗 আবার চেষ্টা করুন", callback_data="link")]]
            await update.message.reply_text(
                "❌ *Username সঠিক নয়!*\n\nএডমিনের দেওয়া সঠিক Lamix username দিন।",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        return

    user = await get_user(user_id)
    if not user:
        await update.message.reply_text("⚠️ /link দিয়ে আগে অ্যাকাউন্ট লিঙ্ক করুন।")
        return
    if user["is_banned"]:
        await update.message.reply_text("🚫 আপনি ব্যান হয়েছেন।")
        return

    if context.user_data.get("waiting_for_quantity"):
        await _handle_quantity_input(update, context)
        return

    context.user_data["search_query"] = text
    await _show_search_results(update, context, text, page=0)


# ══════════════════════════════════════════════
#  CALLBACK HANDLER
# ══════════════════════════════════════════════

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    user = await get_user(user_id)

    if data == "cancel":
        context.user_data.clear()
        await query.edit_message_text("❌ বাতিল করা হয়েছে।")
        return

    if data == "link":
        context.user_data["waiting_for_username"] = True
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        await query.edit_message_text(
            "👤 *Lamix username পাঠান:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data == "unlink":
        if not user:
            await query.edit_message_text("⚠️ কোনো অ্যাকাউন্ট লিঙ্ক নেই।")
            return
        keyboard = [[
            InlineKeyboardButton("✅ Confirm", callback_data="confirm_unlink"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ]]
        await query.edit_message_text(
            f"⚠️ *{user['username']}* আনলিঙ্ক করবেন?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data == "confirm_unlink":
        await unlink_user(user_id)
        await query.edit_message_text("✅ অ্যাকাউন্ট আনলিঙ্ক হয়েছে।")
        return

    if data.startswith("confirm_reset_"):
        if user_id != ADMIN_ID:
            await query.answer("🚫 শুধু অ্যাডমিন পারবেন।")
            return
        target_id = int(data[len("confirm_reset_"):])
        removed = await reset_member(target_id)
        if removed:
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text="♻️ আপনাকে রিসেট করা হয়েছে। নতুন করে /link দিয়ে অ্যাকাউন্ট কানেক্ট করুন।",
                )
            except Exception:
                pass
            tg_uname = removed.get("telegram_username", str(target_id))
            await query.edit_message_text(f"✅ *@{tg_uname}* সম্পূর্ণ রিসেট করা হয়েছে।", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ ইউজার পাওয়া যায়নি।")
        return

    if data == "edit_daily_limit":
        if user_id != ADMIN_ID:
            await query.answer("🚫 শুধু অ্যাডমিন পারবেন।")
            return
        context.user_data.clear()
        context.user_data["waiting_for_new_daily_limit"] = True
        current = await get_daily_limit()
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        await query.edit_message_text(
            f"📊 *বর্তমান Daily Limit:* {current}\n\nনতুন Daily Limit সংখ্যা পাঠান:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data == "edit_max_per_order":
        if user_id != ADMIN_ID:
            await query.answer("🚫 শুধু অ্যাডমিন পারবেন।")
            return
        context.user_data.clear()
        context.user_data["waiting_for_new_max_per_order"] = True
        current = await get_max_per_order()
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        await query.edit_message_text(
            f"🔢 *বর্তমান Max Per Order:* {current}\n\nনতুন Max Per Order সংখ্যা পাঠান:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data == "add_nums":
        if not user:
            await query.edit_message_text("⚠️ /link দিয়ে আগে লিঙ্ক করুন।")
            return
        if user["is_banned"]:
            await query.edit_message_text("🚫 আপনি ব্যান হয়েছেন।")
            return
        if user["daily_used"] >= user["daily_limit"]:
            keyboard = [[InlineKeyboardButton("🔄 Request Limit Reset", callback_data="request_reset")]]
            await query.edit_message_text(
                f"⚠️ *Daily Limit Exceeded!*\nআজকের লিমিট শেষ।",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return
        await _show_ranges(update, context, page=0)
        return

    if data.startswith("range_page_"):
        await _show_ranges(update, context, page=int(data.split("_")[-1]))
        return

    if data.startswith("search_page_"):
        q = context.user_data.get("search_query", "")
        await _show_search_results(update, context, q, page=int(data.split("_")[-1]))
        return

    if data.startswith("range_"):
        range_id = data[len("range_"):]
        ranges = await lamix.fetch_ranges_async()
        selected = next((r for r in ranges if str(r["id"]) == range_id), None)
        if not selected:
            await query.edit_message_text("❌ রেঞ্জ পাওয়া যায়নি।")
            return
        context.user_data["selected_range"] = selected
        context.user_data["waiting_for_quantity"] = True
        max_per_order = await get_max_per_order()
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        await query.edit_message_text(
            f"📦 *{selected['name']}*\n"
            f"Available: {selected.get('available', 0)} ✅\n\n"
            f"🔢 কতটি নম্বর চান? (১–{max_per_order})\nসংখ্যা পাঠান:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data == "request_reset":
        if not user:
            return
        if await has_pending_reset_request(user_id):
            await query.answer("⏳ আগের রিকোয়েস্ট পেন্ডিং আছে।", show_alert=True)
            return
        keyboard = [[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_reset_{user_id}"),
            InlineKeyboardButton("❌ Deny", callback_data=f"deny_reset_{user_id}"),
        ]]
        raw_uname = update.effective_user.username
        if raw_uname:
            safe_uname = re.sub(r'([_*`\[])', r'\\\1', raw_uname)
            tg_uname = f"@{safe_uname}"
        else:
            tg_uname = str(user_id)
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🔔 *Limit Reset Request!*\n\n👤 {tg_uname}\n🆔 `{user_id}`\n📊 {user['daily_used']}/{user['daily_limit']}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            await set_pending_reset_request(user_id, True)
            await query.edit_message_text("✅ রিকোয়েস্ট পাঠানো হয়েছে!\n⏳ এডমিনের রেসপন্সের জন্য অপেক্ষা করুন।")
        except Exception as e:
            print(f"[request_reset] Admin notify failed: {e}")
            await query.edit_message_text("⚠️ রিকোয়েস্ট পাঠাতে সমস্যা হয়েছে। এডমিনকে সরাসরি যোগাযোগ করুন।")
        return

    if data.startswith("approve_reset_") or data.startswith("deny_reset_"):
        if user_id != ADMIN_ID:
            await query.answer("🚫 শুধু অ্যাডমিন পারবেন।")
            return
        parts = data.split("_")
        action = parts[0]
        target_id = int(parts[-1])
        target_user = await get_user(target_id)
        target_label = (
            f"@{target_user['telegram_username']}" if target_user and target_user.get("telegram_username")
            else str(target_id)
        )
        if action == "approve":
            new_limit = await reset_user_usage(target_id)
            await set_pending_reset_request(target_id, False)
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"✅ *Limit Reset!*\n\nআপনার আজকের ব্যবহার রিসেট হয়েছে।\n📊 লিমিট: {new_limit}",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
            await query.edit_message_text(
                f"✅ *Approved!*\n\n👤 {target_label}\n📊 রিসেট হয়েছে (Limit: {new_limit})",
                parse_mode="Markdown",
            )
        else:
            await set_pending_reset_request(target_id, False)
            try:
                await context.bot.send_message(chat_id=target_id, text="❌ Limit Reset Request Deny করা হয়েছে।")
            except Exception:
                pass
            await query.edit_message_text(f"❌ *Denied!*\n\n👤 {target_label}", parse_mode="Markdown")
        return

    if data.startswith("request_range_"):
        range_name = data[len("request_range_"):]
        raw_uname = update.effective_user.username
        if raw_uname:
            safe_uname = re.sub(r'([_*`\[])', r'\\\1', raw_uname)
            tg_uname = f"@{safe_uname}"
        else:
            tg_uname = str(user_id)
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🔔 *Range Request!*\n\n👤 {tg_uname}\n🆔 `{user_id}`\n📦 *{range_name}*",
                parse_mode="Markdown",
            )
            await query.edit_message_text("✅ রেঞ্জ রিকোয়েস্ট পাঠানো হয়েছে!")
        except Exception as e:
            print(f"[request_range] Admin notify failed: {e}")
            await query.edit_message_text("⚠️ রিকোয়েস্ট পাঠাতে সমস্যা হয়েছে।")
        return

    # ── Number format buttons — handled in handlers_logic ──
    from handlers_logic import handle_number_format_callback
    await handle_number_format_callback(query, context)
