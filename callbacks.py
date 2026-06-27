import re
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import ADMIN_ID
from database import (
    get_user, unlink_user, update_usage, reset_user_usage,
    add_user, is_username_taken, set_pending_reset_request,
    has_pending_reset_request, set_daily_limit, set_max_per_order,
    get_daily_limit, get_max_per_order, reset_member,
)
import lamix
from user_commands import (
    is_admin,
    _num_has_code, _strip_code, _strip_plus,
    _post_process_numbers, _build_number_buttons,
)


# ══════════════════════════════════════════════
#  RANGE HELPERS
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

    keyboard = [
        [InlineKeyboardButton(f"📦 {r['name']} ({r['available']})", callback_data=f"range_{r['id']}")]
        for r in page_ranges
    ]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"range_page_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"range_page_{page+1}"))
    if nav:
        keyboard.append(nav)

    text = f"📋 *Select Range (Page {page+1}/{total_pages})*"
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def _show_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str, page: int = 0):
    ranges = await lamix.fetch_ranges_async()
    filtered = [r for r in ranges if query.lower() in r["name"].lower()]

    if not filtered:
        msg = f"🔍 *{query}*\n\n❌ কোনো রেঞ্জ পাওয়া যায়নি।"
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(msg, parse_mode="Markdown")
        return

    per_page = 8
    total_pages = max(1, (len(filtered) + per_page - 1) // per_page)
    page_ranges = filtered[page * per_page:(page + 1) * per_page]

    keyboard = [
        [InlineKeyboardButton(f"📦 {r['name']} ({r['available']})", callback_data=f"range_{r['id']}")]
        for r in page_ranges
    ]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"search_page_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"search_page_{page+1}"))
    if nav:
        keyboard.append(nav)

    text = f"🔍 *{query}* (Page {page+1}/{total_pages})"
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )


# ══════════════════════════════════════════════
#  TEXT HANDLER
# ══════════════════════════════════════════════

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # ── New Daily Limit input (Admin) ──
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

    # ── New Max Per Order input (Admin) ──
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

    # ── Username input ──
    if context.user_data.get("waiting_for_username"):
        context.user_data.clear()
        lamix_username = text.strip()

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
    max_per_order = await get_max_per_order()

    try:
        quantity = int(text)
    except ValueError:
        await update.message.reply_text("❌ সংখ্যা লিখুন। উদাহরণ: 10")
        return

    if quantity < 1 or quantity > max_per_order:
        await update.message.reply_text(f"❌ ১ থেকে {max_per_order} এর মধ্যে সংখ্যা দিন।")
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
            f"❌ *Allocation Failed!*\n\n📦 Range: *{selected['name']}*\n"
            f"🔢 Quantity: *{quantity}*\n\n⚠️ No numbers available",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    numbers = result.get("numbers", [])
    await update_usage(user_id, len(numbers))
    updated_user = await get_user(user_id)

    shortfall_note = ""
    if len(numbers) < quantity:
        shortfall_note = f"\n⚠️ চাওয়া হয়েছিল *{quantity}*, পাওয়া গেছে *{len(numbers)}*"

    await update.message.reply_text(
        f"✅ *Order Created Successfully*\n\n"
        f"📦 Range: *{selected['name']}*\n"
        f"🔢 Quantity: *{len(numbers)}*\n"
        f"💳 Payterm: *{selected.get('payterm', 'Weekly')}*\n"
        f"💰 Payout: *${selected.get('payout', '0.01')}*"
        f"{shortfall_note}\n\n"
        f"📊 {updated_user['daily_used']}/{updated_user['daily_limit']} used today",
        parse_mode="Markdown",
    )

    country_code = selected.get("country_code", "")
    numbers = _post_process_numbers(numbers, country_code)

    context.user_data["last_numbers"] = "\n".join(numbers)
    context.user_data["country_code"] = country_code

    code_already_in = (
        bool(country_code) and
        len(numbers) > 0 and
        all(_num_has_code(n, country_code) for n in numbers)
    )
    has_plus = len(numbers) > 0 and all(n.startswith("+") for n in numbers)
    context.user_data["code_embedded"] = code_already_in
    context.user_data["has_plus"] = has_plus

    numbers_text = "\n".join([f"`{n}`" for n in numbers])
    keyboard = _build_number_buttons(country_code, code_already_in, has_plus)

    await update.message.reply_text(
        f"📱 *Allocated Numbers ({len(numbers)}):*\n\n{numbers_text}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
    )


# ══════════════════════════════════════════════
#  CALLBACK HANDLER
# ══════════════════════════════════════════════

async def _auto_approve_reset(context, user_id: int):
    await asyncio.sleep(10)
    from database import reset_user_usage, set_pending_reset_request
    new_limit = await reset_user_usage(user_id)
    await set_pending_reset_request(user_id, False)
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ *Limit Reset সফল!*\n\n"
                f"🎉 আপনার আজকের লিমিট রিসেট হয়ে গেছে।\n"
                f"📊 নতুন লিমিট: *{new_limit}*\n\n"
                f"এখন /add\_nums দিয়ে নম্বর নিন।"
            ),
            parse_mode="Markdown",
        )
    except Exception as e:
        print(f"[auto_approve] User notify failed: {e}")


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

    # ── Confirm Reset (Admin) ──
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
            await query.edit_message_text(
                f"✅ *@{tg_uname}* সম্পূর্ণ রিসেট করা হয়েছে।", parse_mode="Markdown"
            )
        else:
            await query.edit_message_text("❌ ইউজার পাওয়া যায়নি (হয়তো আগেই রিসেট হয়েছে)।")
        return

    # ── Edit Daily Limit (Admin) ──
    if data == "edit_daily_limit":
        if user_id != ADMIN_ID:
            await query.answer("🚫 শুধু অ্যাডমিন পারবেন।")
            return
        context.user_data.clear()
        context.user_data["waiting_for_new_daily_limit"] = True
        current = await get_daily_limit()
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        await query.edit_message_text(
            f"📊 *বর্তমান Daily Limit:* {current}\n\n"
            f"নতুন Daily Limit সংখ্যা পাঠান:\n"
            f"⚠️ এটি সবার (পুরনো ইউজার সহ) লিমিট এখনই বদলে দেবে।",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # ── Edit Max Per Order (Admin) ──
    if data == "edit_max_per_order":
        if user_id != ADMIN_ID:
            await query.answer("🚫 শুধু অ্যাডমিন পারবেন।")
            return
        context.user_data.clear()
        context.user_data["waiting_for_new_max_per_order"] = True
        current = await get_max_per_order()
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        await query.edit_message_text(
            f"🔢 *বর্তমান Max Per Order:* {current}\n\n"
            f"নতুন Max Per Order সংখ্যা পাঠান:\n"
            f"⚠️ এটি পরের অর্ডার থেকেই কার্যকর হবে।",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
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
        max_per_order = await get_max_per_order()
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        await query.edit_message_text(
            f"📦 *{selected['name']}*\n"
            f"Available: {selected.get('available', 0)} ✅\n\n"
            f"🔢 কতটি নম্বর চান? (১–{max_per_order})\n"
            f"সংখ্যা পাঠান:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

# ── Limit Reset Request ──
    if data == "request_reset":
        if user_id == ADMIN_ID:
            await query.answer("🚫 এডমিন নিজে রিকোয়েস্ট করতে পারবেন না।", show_alert=True)
            return
        if not user:
            return
        if await has_pending_reset_request(user_id):
            await query.answer(
                "⏳ আপনার আগের রিকোয়েস্ট এখনো পেন্ডিং আছে। এডমিনের রেসপন্সের জন্য অপেক্ষা করুন।",
                show_alert=True,
            )
            return

    raw_uname = update.effective_user.username
    if raw_uname:
        safe_uname = re.sub(r'([_*`\[])', r'\\\1', raw_uname)
        tg_uname = f"@{safe_uname}"
    else:
        tg_uname = str(user_id)

    from database import get_auto_approve
    auto_approve = await get_auto_approve()

    if auto_approve:
        await set_pending_reset_request(user_id, True)
        await query.edit_message_text(
            "✅ রিকোয়েস্ট পাঠানো হয়েছে!\n⏳ এডমিনের রেসপন্সের জন্য অপেক্ষা করুন।"
        )
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"🤖 *Auto-Approve Reset!*\n\n"
                    f"👤 {tg_uname}\n"
                    f"🆔 `{user_id}`\n"
                    f"📊 {user['daily_used']}/{user['daily_limit']}"
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass
        # ✅ background এ 10 সেকেন্ড পরে approve হবে, কিছু block হবে না
        asyncio.create_task(_auto_approve_reset(context, user_id))
        return

    # Manual approve
    keyboard = [[
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_reset_{user_id}"),
        InlineKeyboardButton("❌ Deny", callback_data=f"deny_reset_{user_id}"),
    ]]
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🔔 *Limit Reset Request!*\n\n"
                f"👤 {tg_uname}\n"
                f"🆔 `{user_id}`\n"
                f"📊 {user['daily_used']}/{user['daily_limit']}"
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        await set_pending_reset_request(user_id, True)
        await query.edit_message_text(
            "✅ রিকোয়েস্ট পাঠানো হয়েছে!\n⏳ এডমিনের রেসপন্সের জন্য অপেক্ষা করুন।"
        )
    except Exception as e:
        print(f"[request_reset] Admin notify failed: {e}")
        await query.edit_message_text(
            "⚠️ রিকোয়েস্ট পাঠাতে সমস্যা হয়েছে।\nএডমিনকে সরাসরি যোগাযোগ করুন।"
        )
        return

    # ── Add Country Code ──
    if data.startswith("add_code_"):
        code = data[len("add_code_"):]
        numbers_text = context.user_data.get("last_numbers", "")
        lines = []
        for l in numbers_text.strip().split("\n"):
            l = l.strip()
            if not l:
                continue
            plain = _strip_code(l, code)
            lines.append(f"+{code}{plain}")

        context.user_data["last_numbers"] = "\n".join(lines)
        context.user_data["code_embedded"] = True
        context.user_data["has_plus"] = True
        nums_md = "\n".join([f"`{n}`" for n in lines])
        keyboard = _build_number_buttons(code, True, True)
        await query.edit_message_text(
            f"📱 *Allocated Numbers ({len(lines)}):*\n\n{nums_md}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # ── Remove Country Code ──
    if data.startswith("remove_code_"):
        code = data[len("remove_code_"):]
        numbers_text = context.user_data.get("last_numbers", "")
        lines = []
        for l in numbers_text.strip().split("\n"):
            l = l.strip()
            if not l:
                continue
            lines.append(_strip_code(l, code))

        context.user_data["last_numbers"] = "\n".join(lines)
        context.user_data["code_embedded"] = False
        context.user_data["has_plus"] = False
        nums_md = "\n".join([f"`{n}`" for n in lines])
        keyboard = _build_number_buttons(code, False, False)
        await query.edit_message_text(
            f"📱 *Allocated Numbers ({len(lines)}):*\n\n{nums_md}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # ── Remove + only ──
    if data == "remove_plus":
        code = context.user_data.get("country_code", "")
        numbers_text = context.user_data.get("last_numbers", "")
        lines = []
        for l in numbers_text.strip().split("\n"):
            l = l.strip()
            if not l:
                continue
            lines.append(_strip_plus(l))

        context.user_data["last_numbers"] = "\n".join(lines)
        context.user_data["has_plus"] = False
        nums_md = "\n".join([f"`{n}`" for n in lines])
        keyboard = _build_number_buttons(code, context.user_data.get("code_embedded", False), False)
        await query.edit_message_text(
            f"📱 *Allocated Numbers ({len(lines)}):*\n\n{nums_md}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # ── Add + only ──
    if data == "add_plus":
        code = context.user_data.get("country_code", "")
        numbers_text = context.user_data.get("last_numbers", "")
        lines = []
        for l in numbers_text.strip().split("\n"):
            l = l.strip()
            if not l:
                continue
            lines.append(f"+{l}" if not l.startswith("+") else l)

        context.user_data["last_numbers"] = "\n".join(lines)
        context.user_data["has_plus"] = True
        nums_md = "\n".join([f"`{n}`" for n in lines])
        keyboard = _build_number_buttons(code, context.user_data.get("code_embedded", False), True)
        await query.edit_message_text(
            f"📱 *Allocated Numbers ({len(lines)}):*\n\n{nums_md}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # ── Approve Reset (Admin) ──
    if data.startswith("approve_reset_"):
        if user_id != ADMIN_ID:
            await query.answer("🚫 শুধু অ্যাডমিন পারবেন।", show_alert=True)
            return
        target_id = int(data[len("approve_reset_"):])
        new_limit = await reset_user_usage(target_id)
        await set_pending_reset_request(target_id, False)
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    f"✅ *Limit Reset সফল!*\n\n"
                    f"🎉 আপনার আজকের লিমিট রিসেট হয়ে গেছে।\n"
                    f"📊 নতুন লিমিট: *{new_limit}*\n\n"
                    f"এখন /add\_nums দিয়ে নম্বর নিন।"
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass
        await query.edit_message_text("✅ Approved! ইউজারের লিমিট রিসেট হয়েছে।")
        return

    # ── Deny Reset (Admin) ──
    if data.startswith("deny_reset_"):
        if user_id != ADMIN_ID:
            await query.answer("🚫 শুধু অ্যাডমিন পারবেন।", show_alert=True)
            return
        target_id = int(data[len("deny_reset_"):])
        await set_pending_reset_request(target_id, False)
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="❌ *Limit Reset অস্বীকৃত!*\n\nআপনার রিকোয়েস্ট এডমিন deny করেছেন।",
                parse_mode="Markdown",
            )
        except Exception:
            pass
        await query.edit_message_text("❌ Denied! ইউজারকে জানানো হয়েছে।")
        return
