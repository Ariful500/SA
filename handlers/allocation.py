import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import LAMIX_API_KEY, LAMIX_API_URL, ADMIN_ID
from database import get_user, update_usage
from handlers.user import handle_limit_request


# ✅ Lamix থেকে রেঞ্জ লিস্ট আনা
async def fetch_ranges():
    try:
        async with aiohttp.ClientSession() as session:
            params = {"api_key": LAMIX_API_KEY, "action": "get_ranges"}
            async with session.get(LAMIX_API_URL, params=params) as resp:
                data = await resp.json()
                return data.get("ranges", [])
    except Exception:
        return []


# ✅ Lamix থেকে নম্বর অ্যালোকেট করা
async def allocate_numbers(client_id: str, range_id: str, quantity: int):
    try:
        async with aiohttp.ClientSession() as session:
            params = {
                "api_key": LAMIX_API_KEY,
                "action": "allocate",
                "client_id": client_id,
                "range_id": range_id,
                "quantity": quantity,
            }
            async with session.get(LAMIX_API_URL, params=params) as resp:
                return await resp.json()
    except Exception:
        return None


# ✅ /add_nums
async def add_nums_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
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

    # লিমিট চেক
    if user["daily_used"] >= user["daily_limit"]:
        keyboard = [[InlineKeyboardButton("🔄 Request Limit Reset", callback_data="request_reset")]]
        await update.message.reply_text(
            f"⚠️ *Daily Limit Exceeded!*\n\n"
            f"আপনার আজকের {user['daily_limit']}টি নম্বরের লিমিট শেষ।\n"
            f"কাল সকাল ৬টায় অটো রিসেট হবে।\n\n"
            f"অথবা এডমিনকে রিকোয়েস্ট করুন:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    await show_ranges(update, context, page=0)


# ✅ রেঞ্জ লিস্ট দেখানো
async def show_ranges(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    ranges = await fetch_ranges()

    if not ranges:
        await update.message.reply_text("❌ কোনো রেঞ্জ পাওয়া যায়নি।")
        return

    per_page = 8
    total_pages = (len(ranges) + per_page - 1) // per_page
    start = page * per_page
    end = start + per_page
    page_ranges = ranges[start:end]

    keyboard = []
    for r in page_ranges:
        keyboard.append([InlineKeyboardButton(f"📦 {r['name']}", callback_data=f"range_{r['id']}")])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"range_page_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"range_page_{page + 1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    text = f"📋 *Select Country (Page {page + 1}/{total_pages})*"

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )


# ✅ সব Callback হ্যান্ডল করা
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    user = await get_user(user_id)

    # ─── Cancel ───
    if data == "cancel":
        context.user_data.clear()
        await query.edit_message_text("❌ বাতিল করা হয়েছে।")
        return

    # ─── Link ───
    if data == "link":
        from handlers.user import link_command
        await link_command(update, context)
        return

    # ─── Unlink Confirm ───
    if data == "confirm_unlink":
        from database import unlink_user
        await unlink_user(user_id)
        await query.edit_message_text("✅ অ্যাকাউন্ট সফলভাবে আনলিঙ্ক হয়েছে।")
        return

    # ─── Browse Ranges ───
    if data == "add_nums":
        await add_nums_command(update, context)
        return

    # ─── Range Page Navigation ───
    if data.startswith("range_page_"):
        page = int(data.split("_")[-1])
        await show_ranges(update, context, page=page)
        return

    # ─── Search Page Navigation ───
    if data.startswith("search_page_"):
        page = int(data.split("_")[-1])
        query_text = context.user_data.get("search_query", "")
        from handlers.user import show_search_results
        await show_search_results(update, context, query_text, page=page)
        return

    # ─── Range Selected ───
    if data.startswith("range_"):
        range_id = data.replace("range_", "")
        ranges = await fetch_ranges()
        selected = next((r for r in ranges if str(r["id"]) == range_id), None)

        if not selected:
            await query.edit_message_text("❌ রেঞ্জ পাওয়া যায়নি।")
            return

        context.user_data["selected_range"] = selected
        context.user_data["waiting_for_quantity"] = True

        available = selected.get("available", 0)
        keyboard = [[InlineKeyboardButton("❌ /cancel", callback_data="cancel")]]

        await query.edit_message_text(
            f"📦 *{selected['name']}*\n"
            f"Available numbers: {available} ✅\n\n"
            f"🔢 *Enter quantity*\n"
            f"Send number between 1 \\- 30",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # ─── Limit Reset Request ───
    if data == "request_reset":
        if not user:
            return
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_reset_{user_id}"),
                InlineKeyboardButton("❌ Deny", callback_data=f"deny_reset_{user_id}"),
            ]
        ]
        tg_username = f"@{update.effective_user.username}" if update.effective_user.username else str(user_id)
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔔 *Limit Reset Request!*\n\n"
                 f"👤 User: {tg_username}\n"
                 f"🆔 ID: `{user_id}`\n"
                 f"📊 Used: {user['daily_used']}/{user['daily_limit']}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        await query.edit_message_text(
            "✅ রিকোয়েস্ট পাঠানো হয়েছে! এডমিন Approve করলে লিমিট রিসেট হবে।"
        )
        return

    # ─── Admin Approve/Deny Reset ───
    if data.startswith("approve_reset_") or data.startswith("deny_reset_"):
        if user_id != ADMIN_ID:
            await query.answer("🚫 শুধু অ্যাডমিন এটা করতে পারবেন।")
            return
        parts = data.split("_")
        action = parts[0]
        target_user_id = parts[-1]
        await handle_limit_request(query, context, action, target_user_id)
        return

    # ─── Range Request ───
    if data.startswith("request_range_"):
        range_name = data.replace("request_range_", "")
        tg_username = f"@{update.effective_user.username}" if update.effective_user.username else str(user_id)
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔔 *Range Request!*\n\n"
                 f"👤 User: {tg_username}\n"
                 f"🆔 ID: `{user_id}`\n"
                 f"📦 Range: *{range_name}*",
            parse_mode="Markdown",
        )
        await query.edit_message_text("✅ রেঞ্জ রিকোয়েস্ট পাঠানো হয়েছে!")
        return

    # ─── Add/Remove Country Code ───
    if data.startswith("add_code_"):
        numbers_text = context.user_data.get("last_numbers", "")
        code = data.replace("add_code_", "")
        lines = numbers_text.strip().split("\n")
        new_lines = [f"+{code}{line.strip()}" for line in lines if line.strip()]
        context.user_data["last_numbers"] = "\n".join(new_lines)
        await send_numbers_message(query, context, new_lines, code, add_code=True)
        return

    if data == "remove_code":
        numbers_text = context.user_data.get("last_numbers", "")
        lines = numbers_text.strip().split("\n")
        new_lines = []
        for line in lines:
            line = line.strip()
            if line.startswith("+"):
                # country code সরাও
                for i, ch in enumerate(line[1:], 1):
                    if not ch.isdigit():
                        break
                    if i >= 3:
                        new_lines.append(line[i:])
                        break
            else:
                new_lines.append(line)
        context.user_data["last_numbers"] = "\n".join(new_lines)
        await send_numbers_message(query, context, new_lines, "", add_code=False)
        return


# ✅ নম্বর মেসেজ পাঠানো (monospace + বাটন)
async def send_numbers_message(query, context, numbers, country_code, add_code=True):
    numbers_text = "\n".join([f"`{n}`" for n in numbers])
    keyboard = []
    if add_code:
        keyboard.append([InlineKeyboardButton(f"➖ Remove Country Code", callback_data="remove_code")])
    else:
        keyboard.append([InlineKeyboardButton(f"➕ Add Country Code (+{country_code})", callback_data=f"add_code_{country_code}")])

    await query.message.reply_text(
        f"📱 *Allocated Numbers ({len(numbers)}/{len(numbers)}):*\n\n{numbers_text}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ✅ Quantity Input হ্যান্ডল (bot.py এর text handler থেকে কল হবে)
async def handle_quantity_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    text = update.message.text.strip()
    selected = context.user_data.get("selected_range")

    try:
        quantity = int(text)
    except ValueError:
        await update.message.reply_text("❌ সংখ্যা লিখুন। উদাহরণ: 10")
        return

    if quantity < 1 or quantity > 30:
        await update.message.reply_text("❌ ১ থেকে ৩০ এর মধ্যে সংখ্যা দিন।")
        return

    remaining = user["daily_limit"] - user["daily_used"]
    if quantity > remaining:
        await update.message.reply_text(
            f"❌ আপনার আজকের মাত্র *{remaining}টি* নম্বর নেওয়ার সুযোগ আছে।",
            parse_mode="Markdown",
        )
        return

    context.user_data.clear()
    await update.message.reply_text("⏳ নম্বর অ্যালোকেট করা হচ্ছে...")

    result = await allocate_numbers(user["client_id"], selected["id"], quantity)

    if not result or result.get("status") != "success":
        # Allocation Failed
        keyboard = [[InlineKeyboardButton("📩 Request Range", callback_data=f"request_range_{selected['name']}")]]
        await update.message.reply_text(
            f"❌ *Allocation Failed!*\n\n"
            f"📦 Range: *{selected['name']}*\n"
            f"🔢 Quantity: *{quantity}*\n"
            f"💳 Payterm: *{selected.get('payterm', 'Weekly')}*\n"
            f"💰 Payout: *${selected.get('payout', '0.01')}*\n\n"
            f"⚠️ No numbers available to allocate",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # ✅ সফল
    numbers = result.get("numbers", [])
    await update_usage(user_id, len(numbers))
    updated_user = await get_user(user_id)

    await update.message.reply_text(
        f"✅ *Order Created Successfully*\n\n"
        f"📦 Range: *{selected['name']}*\n"
        f"🔢 Quantity: *{len(numbers)}*\n"
        f"💳 Payterm: *{selected.get('payterm', 'Weekly')}*\n"
        f"💰 Payout: *${selected.get('payout', '0.01')}*\n\n"
        f"📊 {updated_user['daily_used']}/{updated_user['daily_limit']} numbers used today",
        parse_mode="Markdown",
    )

    # নম্বর পাঠাও monospace এ
    country_code = selected.get("country_code", "")
    numbers_text = "\n".join([f"`{n}`" for n in numbers])
    keyboard = []
    if country_code:
        keyboard.append([InlineKeyboardButton(f"➕ Add Country Code (+{country_code})", callback_data=f"add_code_{country_code}")])
        keyboard.append([InlineKeyboardButton("➖ Remove Country Code", callback_data="remove_code")])

    context.user_data["last_numbers"] = "\n".join(numbers)
    context.user_data["country_code"] = country_code

    await update.message.reply_text(
        f"📱 *Allocated Numbers ({len(numbers)}/{len(numbers)}):*\n\n{numbers_text}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
    )
    
