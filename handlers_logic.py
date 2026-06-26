import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import ADMIN_ID
from database import get_user, update_usage, get_max_per_order
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


def _num_has_code(number: str, code: str) -> bool:
    """Check whether a number already contains the country code (with or without +)."""
    if not code:
        return False
    return number.startswith(f"+{code}") or number.startswith(code)


def _strip_code(number: str, code: str) -> str:
    """Remove country code prefix (+ variant or plain) from a number."""
    if number.startswith(f"+{code}"):
        return number[len(code) + 1:]
    if number.startswith(code):
        return number[len(code):]
    return number


def _strip_plus(number: str) -> str:
    """Remove only the leading + sign, keep everything else."""
    return number.lstrip("+")


def _fix_malaysia(number: str) -> str:
    """
    Malaysia country code = 60.
    Lamix panel bug: কখনো কখনো 600XXXXXXXXX আসে (একটা বাড়তি 0)।
    +600125608118 → +60125608118 (60 এর পরে বাড়তি 0 বাদ)
    Plain format: 600125608118 → 60125608118
    """
    for prefix in ("+600", "600"):
        if number.startswith(prefix):
            rest = number[len(prefix):]
            replacement = ("+60" if prefix.startswith("+") else "60") + rest
            return replacement
    return number


def _post_process_numbers(numbers: list[str], country_code: str) -> list[str]:
    """Apply any country-specific fixes after allocation."""
    if country_code == "60":
        return [_fix_malaysia(n) for n in numbers]
    return numbers


def _build_number_buttons(country_code: str, code_embedded: bool, has_plus: bool) -> list:
    """
    বাটন logic:
    - code নেই, + নেই  → [➕ Add Country Code]
    - code আছে, + আছে  → [➖ Remove Country Code] [➖ Remove +]
    - code আছে, + নেই  → [➖ Remove Country Code] [➕ Add +]
    - code নেই, + আছে  → [➖ Remove +]
    """
    keyboard = []
    if country_code:
        if code_embedded:
            keyboard.append([InlineKeyboardButton(
                f"➖ Remove Country Code (+{country_code})",
                callback_data=f"remove_code_{country_code}"
            )])
        else:
            keyboard.append([InlineKeyboardButton(
                f"➕ Add Country Code (+{country_code})",
                callback_data=f"add_code_{country_code}"
            )])

    if has_plus:
        keyboard.append([InlineKeyboardButton("➖ Remove +", callback_data="remove_plus")])
    elif code_embedded:
        keyboard.append([InlineKeyboardButton("➕ Add +", callback_data="add_plus")])

    return keyboard


# ══════════════════════════════════════════════
#  RANGE / SEARCH DISPLAY
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


async def _show_search_results(
    update: Update, context: ContextTypes.DEFAULT_TYPE, query: str, page: int = 0
):
    ranges = await lamix.fetch_ranges_async()
    filtered = [r for r in ranges if query.lower() in r["name"].lower()]
    if not filtered:
        target = update.callback_query or update.message
        send = (
            target.edit_message_text if update.callback_query else target.reply_text
        )
        await send(f"🔍 *{query}*\n\n❌ কোনো রেঞ্জ পাওয়া যায়নি।", parse_mode="Markdown")
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
        keyboard = [[InlineKeyboardButton(
            "📩 Request Range", callback_data=f"request_range_{selected['name']}"
        )]]
        await update.message.reply_text(
            f"❌ *Allocation Failed!*\n\n"
            f"📦 Range: *{selected['name']}*\n"
            f"🔢 Quantity: *{quantity}*\n\n"
            f"⚠️ No numbers available",
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

    # ══ Country-specific fix (e.g. Malaysia 600→60) ══
    numbers = _post_process_numbers(numbers, country_code)

    context.user_data["last_numbers"] = "\n".join(numbers)
    context.user_data["country_code"] = country_code

    # ══ Smart detect ══
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
#  NUMBER FORMAT CALLBACKS
# ══════════════════════════════════════════════

async def handle_number_format_callback(query, context: ContextTypes.DEFAULT_TYPE):
    """
    add_code_XX / remove_code_XX / remove_plus / add_plus
    handlers.py এর handle_callback() এর শেষে এটি call করা হয়।
    """
    data = query.data

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

    # ── Remove Country Code (code + + দুটোই সরায়) ──
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
        keyboard = _build_number_buttons(
            code, context.user_data.get("code_embedded", False), False
        )
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
        keyboard = _build_number_buttons(
            code, context.user_data.get("code_embedded", False), True
        )
        await query.edit_message_text(
            f"📱 *Allocated Numbers ({len(lines)}):*\n\n{nums_md}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return
