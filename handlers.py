import datetime
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import ADMIN_ID, DAILY_LIMIT, MAX_PER_ORDER
from database import (
    get_user, add_user, unlink_user,
    update_usage, reset_all_limits, reset_user_limit, add_user_limit,
    ban_user, unban_user, get_all_users, get_leaderboard, get_total_sms,
    is_username_taken,
)
import lamix


# ══════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


async def _check_linked(update: Update) -> bool:
    user_id = update.effective_user.id
    user = await get_user(user_id)
    if not user:
        await update.message.reply_text(
            "⚠️ অ্যাকাউন্ট লিঙ্ক করা নেই!\n/link দিয়ে Lamix অ্যাকাউন্ট কানেক্ট করুন।"
        )
        return False
    if user["is_banned"]:
        await update.message.reply_text("🚫 আপনি ব্যান হয়েছেন। এডমিনের সাথে যোগাযোগ করুন।")
        return False
    return True


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
    await update.message.reply_text(
        f"🔄 *All Limits Reset!*\n\n✅ {count} জন ইউজারের লিমিট {DAILY_LIMIT} হয়েছে।",
        parse_mode="Markdown",
    )


async def addlimit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 শুধু অ্যাডমিনের জন্য।")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ সঠিকভাবে লিখুন:\n`/addlimit USER_ID AMOUNT`",
            parse_mode="Markdown",
        )
        return
    try:
        target_id, amount = int(args[0]), int(args[1])
    except ValueError:
        await update.message.reply_text("❌ USER_ID ও AMOUNT সংখ্যা হতে হবে।")
        return
    user = await get_user(target_id)
    if not user:
        await update.message.reply_text("❌ ইউজার পাওয়া যায়নি।")
        return
    await add_user_limit(target_id, amount)
    await context.bot.send_message(
        chat_id=target_id,
        text=f"🎉 *লিমিট বাড়ানো হয়েছে!*\n\n➕ Added: *{amount}*\n📊 New Limit: *{user['daily_limit'] + amount}*",
        parse_mode="Markdown",
    )
    await update.message.reply_text(
        f"✅ *Limit Added!*\n\n👤 User: `{target_id}`\n➕ Added: *{amount}*",
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
    await update.message.reply_text(
        f"⚙️ *Limit Settings*\n\n"
        f"📊 Daily Limit: *{DAILY_LIMIT}*\n"
        f"⏰ Auto Reset: সকাল *৬:০০ AM*\n"
        f"🔢 Max per order: *{MAX_PER_ORDER}*",
        parse_mode="Markdown",
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
        await update.message.reply_text("⚠️ `/ban USER_ID`", parse_mode="Markdown")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ USER_ID সংখ্যা হতে হবে।")
        return
    user = await get_user(target_id)
    if not user:
        await update.message.reply_text("❌ ইউজার পাওয়া যায়নি।")
        return
    await ban_user(target_id)
    try:
        await context.bot.send_message(chat_id=target_id, text="🚫 আপনাকে ব্যান করা হয়েছে।")
    except Exception:
        pass
    await update.message.reply_text(
        f"🚫 *User Banned!*\n\n👤 User: `{target_id}`\n🧑 Username: *{user['username']}*",
        parse_mode="Markdown",
    )


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 শুধু অ্যাডমিনের জন্য।")
        return
    if not context.args:
        await update.message.reply_text("⚠️ `/unban USER_ID`", parse_mode="Markdown")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ USER_ID সংখ্যা হতে হবে।")
        return
    user = await get_user(target_id)
    if not user:
        await update.message.reply_text("❌ ইউজার পাওয়া যায়নি।")
        return
    await unban_user(target_id)
    try:
        await context.bot.send_message(chat_id=target_id, text="✅ ব্যান তুলে নেওয়া হয়েছে।")
    except Exception:
        pass
    await update.message.reply_text(
        f"✅ *User Unbanned!*\n\n👤 User: `{target_id}`\n🧑 Username: *{user['username']}*",
        parse_mode="Markdown",
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
#  RANGE / ALLOCATION HELPERS
# ══════════════════════════════════════════════

async def _show_ranges(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    ranges = await lamix.fetch_ranges_async()
    if not ranges:
        msg = "❌ কোনো রেঞ্জ পাওয়া যায়নি।"
        if update.callback_query:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return

    per_page = 8
    total_pages = max(1, (len(ranges) + per_page - 1) // per_page)
    page_ranges = ranges[page * per_page:(page + 1) * per_page]

    keyboard = [[InlineKeyboardButton(f"📦 {r['name']} ({r['available']})", callback_data=f"range_{r['id']}")] for r in page_ranges]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"range_page_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"range_page_{page+1}"))
    if nav:
        keyboard.append(nav)

    text = f"📋 *Select Range (Page {page+1}/{total_pages})*"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def _show_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str, page: int = 0):
    ranges = await lamix.fetch_ranges_async()
    filtered = [r for r in ranges if query.lower() in r["name"].lower()]
    if not filtered:
        await update.message.reply_text(f"🔍 *{query}*\n\n❌ কোনো রেঞ্জ পাওয়া যায়নি।", parse_mode="Markdown")
        return

    per_page = 8
    total_pages = max(1, (len(filtered) + per_page - 1) // per_page)
    page_ranges = filtered[page * per_page:(page + 1) * per_page]

    keyboard = [[InlineKeyboardButton(f"📦 {r['name']} ({r['available']})", callback_data=f"range_{r['id']}")] for r in page_ranges]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"search_page_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"search_page_{page+1}"))
    if nav:
        keyboard.append(nav)

    await update.message.reply_text(
        f"🔍 *{query}* (Page {page+1}/{total_pages})",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


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

    # ── Username input ──
    if context.user_data.get("waiting_for_username"):
        context.user_data.clear()
        lamix_username = text.strip()

        # ── ১. Username আগে নেওয়া আছে কিনা চেক ──
        if await is_username_taken(lamix_username):
            keyboard = [[InlineKeyboardButton("🔗 অন্য Username দিন", callback_data="link")]]
            await update.message.reply_text(
                f"❌ *এই username টি অন্য কেউ ব্যবহার করছে!*\n\n"
                f"`{lamix_username}` ইতিমধ্যে লিঙ্ক করা আছে।\n"
                f"এডমিনের দেওয়া আপনার নিজের username দিন।",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        # ── ২. Lamix এ verify ──
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
                "❌ *Username সঠিক নয়!*\n\n"
                "এডমিনের দেওয়া সঠিক Lamix username দিন।",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        return

    # ── লিঙ্ক চেক ──
    user = await get_user(user_id)
    if not user:
        await update.message.reply_text("⚠️ /link দিয়ে আগে অ্যাকাউন্ট লিঙ্ক করুন।")
        return
    if user["is_banned"]:
        await update.message.reply_text("🚫 আপনি ব্যান হয়েছেন।")
        return

    # ── Quantity input ──
    if context.user_data.get("waiting_for_quantity"):
        await _handle_quantity_input(update, context)
        return

    # ── Search ──
    context.user_data["search_query"] = text
    await _show_search_results(update, context, text, page=0)


# ══════════════════════════════════════════════
#  QUANTITY INPUT
# ══════════════════════════════════════════════

async def _handle_quantity_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    text = update.message.text.strip()
    selected = context.user_data.get("selected_range")

    try:
        quantity = int(text)
    except ValueError:
        await update.message.reply_text("❌ সংখ্যা লিখুন। উদাহরণ: 10")
        return

    if quantity < 1 or quantity > MAX_PER_ORDER:
        await update.message.reply_text(f"❌ ১ থেকে {MAX_PER_ORDER} এর মধ্যে সংখ্যা দিন।")
        return

    remaining = user["daily_limit"] - user["daily_used"]
    if quantity > remaining:
        await update.message.reply_text(
            f"❌ আজকের মাত্র *{remaining}টি* নম্বর নেওয়ার সুযোগ আছে।",
            parse_mode="Markdown",
        )
        return

    context.user_data.clear()
    await update.message.reply_text("⏳ নম্বর অ্যালোকেট করা হচ্ছে...")

    result = await lamix.allocate_numbers_async(user["client_id"], selected["id"], quantity)

    if not result or result.get("status") != "success":
        keyboard = [[InlineKeyboardButton("📩 Request Range", callback_data=f"request_range_{selected['name']}")]]
        await update.message.reply_text(
            f"❌ *Allocation Failed!*\n\n📦 Range: *{selected['name']}*\n🔢 Quantity: *{quantity}*\n\n⚠️ No numbers available",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    numbers = result.get("numbers", [])
    await update_usage(user_id, len(numbers))
    updated_user = await get_user(user_id)

    await update.message.reply_text(
        f"✅ *Order Created Successfully*\n\n"
        f"📦 Range: *{selected['name']}*\n"
        f"🔢 Quantity: *{len(numbers)}*\n"
        f"💳 Payterm: *{selected.get('payterm', 'Weekly')}*\n"
        f"💰 Payout: *${selected.get('payout', '0.01')}*\n\n"
        f"📊 {updated_user['daily_used']}/{updated_user['daily_limit']} used today",
        parse_mode="Markdown",
    )

    country_code = selected.get("country_code", "")
    numbers_text = "\n".join([f"`{n}`" for n in numbers])
    keyboard = []
    if country_code:
        keyboard.append([InlineKeyboardButton(f"➕ Add Country Code (+{country_code})", callback_data=f"add_code_{country_code}")])

    context.user_data["last_numbers"] = "\n".join(numbers)
    context.user_data["country_code"] = country_code

    await update.message.reply_text(
        f"📱 *Allocated Numbers ({len(numbers)}):*\n\n{numbers_text}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
    )


# ══════════════════════════════════════════════
#  CALLBACK HANDLER
# ══════════════════════════════════════════════

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    user = await get_user(user_id)

    # ── Cancel ──
    if data == "cancel":
        context.user_data.clear()
        await query.edit_message_text("❌ বাতিল করা হয়েছে।")
        return

    # ── Link ──
    if data == "link":
        context.user_data["waiting_for_username"] = True
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        await query.edit_message_text(
            "👤 *Lamix username পাঠান:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # ── Unlink ──
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

    # ── Confirm Unlink ──
    if data == "confirm_unlink":
        await unlink_user(user_id)
        await query.edit_message_text("✅ অ্যাকাউন্ট আনলিঙ্ক হয়েছে।")
        return

    # ── Browse Ranges ──
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

    # ── Range Page ──
    if data.startswith("range_page_"):
        await _show_ranges(update, context, page=int(data.split("_")[-1]))
        return

    # ── Search Page ──
    if data.startswith("search_page_"):
        q = context.user_data.get("search_query", "")
        await _show_search_results(update, context, q, page=int(data.split("_")[-1]))
        return

    # ── Range Selected ──
    if data.startswith("range_"):
        range_id = data[len("range_"):]
        ranges = await lamix.fetch_ranges_async()
        selected = next((r for r in ranges if str(r["id"]) == range_id), None)
        if not selected:
            await query.edit_message_text("❌ রেঞ্জ পাওয়া যায়নি।")
            return
        context.user_data["selected_range"] = selected
        context.user_data["waiting_for_quantity"] = True
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        await query.edit_message_text(
            f"📦 *{selected['name']}*\n"
            f"Available: {selected.get('available', 0)} ✅\n\n"
            f"🔢 কতটি নম্বর চান? (১–{MAX_PER_ORDER})\n"
            f"সংখ্যা পাঠান:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # ── Limit Reset Request ──
    if data == "request_reset":
        if not user:
            return
        keyboard = [[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_reset_{user_id}"),
            InlineKeyboardButton("❌ Deny", callback_data=f"deny_reset_{user_id}"),
        ]]
        tg_uname = f"@{update.effective_user.username}" if update.effective_user.username else str(user_id)
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔔 *Limit Reset Request!*\n\n👤 {tg_uname}\n🆔 `{user_id}`\n📊 {user['daily_used']}/{user['daily_limit']}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        await query.edit_message_text("✅ রিকোয়েস্ট পাঠানো হয়েছে!")
        return

    # ── Admin Approve/Deny ──
    if data.startswith("approve_reset_") or data.startswith("deny_reset_"):
        if user_id != ADMIN_ID:
            await query.answer("🚫 শুধু অ্যাডমিন পারবেন।")
            return
        parts = data.split("_")
        action = parts[0]
        target_id = int(parts[-1])
        if action == "approve":
            await reset_user_limit(target_id)
            await context.bot.send_message(
                chat_id=target_id,
                text=f"✅ *Limit Reset!*\n\nআপনার লিমিট {DAILY_LIMIT} হয়েছে।",
                parse_mode="Markdown",
            )
            await query.edit_message_text(query.message.text + "\n\n✅ *Approved!*", parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=target_id, text="❌ Limit Reset Request Deny করা হয়েছে।")
            await query.edit_message_text(query.message.text + "\n\n❌ *Denied!*", parse_mode="Markdown")
        return

    # ── Range Request ──
    if data.startswith("request_range_"):
        range_name = data[len("request_range_"):]
        tg_uname = f"@{update.effective_user.username}" if update.effective_user.username else str(user_id)
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔔 *Range Request!*\n\n👤 {tg_uname}\n🆔 `{user_id}`\n📦 *{range_name}*",
            parse_mode="Markdown",
        )
        await query.edit_message_text("✅ রেঞ্জ রিকোয়েস্ট পাঠানো হয়েছে!")
        return

    # ── Add Country Code ──
    if data.startswith("add_code_"):
        code = data[len("add_code_"):]
        numbers_text = context.user_data.get("last_numbers", "")
        lines = [f"+{code}{l.strip()}" for l in numbers_text.strip().split("\n") if l.strip()]
        context.user_data["last_numbers"] = "\n".join(lines)
        nums_md = "\n".join([f"`{n}`" for n in lines])
        keyboard = [[InlineKeyboardButton("➖ Remove Country Code", callback_data=f"remove_code_{code}")]]
        await query.message.reply_text(
            f"📱 *Numbers ({len(lines)}):*\n\n{nums_md}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # ── Remove Country Code ──
    if data.startswith("remove_code"):
        numbers_text = context.user_data.get("last_numbers", "")
        code = context.user_data.get("country_code", "")
        lines = []
        for l in numbers_text.strip().split("\n"):
            l = l.strip()
            if l.startswith(f"+{code}"):
                lines.append(l[len(code)+1:])
            else:
                lines.append(l)
        context.user_data["last_numbers"] = "\n".join(lines)
        nums_md = "\n".join([f"`{n}`" for n in lines])
        keyboard = [[InlineKeyboardButton(f"➕ Add Country Code (+{code})", callback_data=f"add_code_{code}")]]
        await query.message.reply_text(
            f"📱 *Numbers ({len(lines)}):*\n\n{nums_md}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return
