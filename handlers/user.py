from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_ID
from database import get_user, add_user, unlink_user, reset_user_limit
import aiohttp
from config import LAMIX_API_KEY, LAMIX_API_URL

# ✅ লিঙ্ক চেক ডেকোরেটর
async def check_linked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    if not user:
        await update.message.reply_text(
            "⚠️ আপনার অ্যাকাউন্ট লিঙ্ক করা নেই!\n"
            "আগে /link দিয়ে Lamix অ্যাকাউন্ট কানেক্ট করুন।"
        )
        return False
    if user["is_banned"]:
        await update.message.reply_text("🚫 আপনি ব্যান হয়েছেন। এডমিনের সাথে যোগাযোগ করুন।")
        return False
    return True


# ✅ /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🔗 Link Account", callback_data="link"),
            InlineKeyboardButton("❌ Unlink", callback_data="unlink"),
        ],
        [InlineKeyboardButton("➕ Browse Ranges", callback_data="add_nums")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👋 *Welcome to SA SMS WORK*\n\n"
        "📌 *Available Commands*\n"
        "🔗 /link — Connect your Lamix account\n"
        "❌ /unlink — Disconnect current account\n"
        "👤 /account — View account details and limits\n"
        "➕ /add\\_nums — Browse available ranges\n\n"
        "🔍 *Text Search*\n"
        "Simply send any text to search ranges instantly\n\n"
        "🚀 *Quick Start*\n"
        "1\\. Use /link\n"
        "2\\. Use /add\\_nums or send text to search",
        parse_mode="MarkdownV2",
        reply_markup=reply_markup,
    )


# ✅ /link
async def link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)

    if user:
        await update.message.reply_text(
            f"⚠️ আপনি ইতিমধ্যে লিঙ্ক করা আছেন!\n"
            f"অ্যাকাউন্ট: *{user['username']}*\n\n"
            f"আনলিঙ্ক করতে /unlink দিন।",
            parse_mode="Markdown",
        )
        return

    context.user_data["waiting_for_username"] = True
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
    await update.message.reply_text(
        "👤 *Send your Lamix username to continue:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ✅ /unlink
async def unlink_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)

    if not user:
        await update.message.reply_text("⚠️ আপনার কোনো অ্যাকাউন্ট লিঙ্ক নেই।")
        return

    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data="confirm_unlink"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ]
    ]
    await update.message.reply_text(
        f"⚠️ আপনি কি *{user['username']}* অ্যাকাউন্ট আনলিঙ্ক করতে চান?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ✅ /account
async def account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_linked(update, context):
        return

    user_id = update.effective_user.id
    user = await get_user(user_id)

    keyboard = [[InlineKeyboardButton("❌ Unlink Account", callback_data="confirm_unlink")]]

    await update.message.reply_text(
        f"👤 *Account Information*\n"
        f"{'━' * 24}\n\n"
        f"🧑 Username: *{user['username']}*\n\n"
        f"📊 *Today's Usage*\n"
        f"• 🔢 Quantity: *{user['daily_used']}/{user['daily_limit']}*\n"
        f"• 🔄 Total Allocated: *{user['total_allocated']}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ✅ /cancel
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ বাতিল করা হয়েছে।")


# ✅ Lamix API তে Username ভেরিফাই
async def verify_lamix_username(username: str):
    try:
        async with aiohttp.ClientSession() as session:
            params = {
                "api_key": LAMIX_API_KEY,
                "username": username,
            }
            async with session.get(LAMIX_API_URL, params=params) as resp:
                data = await resp.json()
                if data.get("status") == "success":
                    return data.get("client_id"), True
                return None, False
    except Exception:
        return None, False


# ✅ Text Handler — Username Input + Search
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Username ইনপুট অপেক্ষায় আছে
    if context.user_data.get("waiting_for_username"):
        context.user_data.clear()

        await update.message.reply_text("⏳ যাচাই করা হচ্ছে...")

        client_id, success = await verify_lamix_username(text)

        if success:
            tg_username = update.effective_user.username or str(user_id)
            await add_user(user_id, tg_username, text, client_id)
            await update.message.reply_text(
                f"✅ *Successfully linked!*\n\n"
                f"Account: *{text}*\n"
                f"Client ID: *{client_id}*\n\n"
                f"এখন /add\\_nums দিয়ে numbers নিন।",
                parse_mode="MarkdownV2",
            )
        else:
            keyboard = [[InlineKeyboardButton("🔗 Try Again", callback_data="link")]]
            await update.message.reply_text(
                "❌ *Username সঠিক নয়!*\n\n"
                "এডমিনের দেওয়া সঠিক username দিন।",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        return

    # লিঙ্ক না থাকলে সার্চ করতে দেবে না
    user = await get_user(user_id)
    if not user:
        await update.message.reply_text(
            "⚠️ আপনার অ্যাকাউন্ট লিঙ্ক করা নেই!\n"
            "আগে /link দিয়ে Lamix অ্যাকাউন্ট কানেক্ট করুন।"
        )
        return

    if user["is_banned"]:
        await update.message.reply_text("🚫 আপনি ব্যান হয়েছেন।")
        return

    # Quantity ইনপুট অপেক্ষায় আছে
    if context.user_data.get("waiting_for_quantity"):
        from handlers.allocation import handle_quantity_input
        await handle_quantity_input(update, context)
        return

    # Text Search
    context.user_data["search_query"] = text
    context.user_data["search_page"] = 0
    await show_search_results(update, context, text, page=0)


# ✅ Search Results দেখানো
async def show_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str, page: int):
    from handlers.allocation import fetch_ranges

    ranges = await fetch_ranges()
    filtered = [r for r in ranges if query.lower() in r["name"].lower()]

    if not filtered:
        await update.message.reply_text(
            f"🔍 *Search: {query}*\n\n❌ কোনো রেঞ্জ পাওয়া যায়নি।",
            parse_mode="Markdown",
        )
        return

    per_page = 8
    total_pages = (len(filtered) + per_page - 1) // per_page
    start = page * per_page
    end = start + per_page
    page_ranges = filtered[start:end]

    keyboard = []
    for r in page_ranges:
        keyboard.append([InlineKeyboardButton(f"📦 {r['name']}", callback_data=f"range_{r['id']}")])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"search_page_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"search_page_{page + 1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    await update.message.reply_text(
        f"🔍 *Search: {query}* (Page {page + 1}/{total_pages})",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ✅ Limit Reset Request — Admin Approve/Deny Callback
async def handle_limit_request(query, context, action, target_user_id):
    if action == "approve":
        await reset_user_limit(int(target_user_id))
        await context.bot.send_message(
            chat_id=int(target_user_id),
            text="✅ *Limit Reset Successfully!*\n\n"
                 "আপনার লিমিট আবার ১২০ হয়েছে।\n"
                 "📊 0/120 numbers used today",
            parse_mode="Markdown",
        )
        await query.edit_message_text(
            query.message.text + "\n\n✅ *Approved!*",
            parse_mode="Markdown",
        )
    elif action == "deny":
        await context.bot.send_message(
            chat_id=int(target_user_id),
            text="❌ আপনার Limit Reset Request এডমিন Deny করেছেন।",
        )
        await query.edit_message_text(
            query.message.text + "\n\n❌ *Denied!*",
            parse_mode="Markdown",
  )
  
