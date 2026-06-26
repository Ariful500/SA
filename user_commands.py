import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import ADMIN_ID
from database import (
    get_user, add_user, unlink_user,
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


def _num_has_code(number: str, code: str) -> bool:
    if not code:
        return False
    return number.startswith(f"+{code}") or number.startswith(code)


def _strip_code(number: str, code: str) -> str:
    if number.startswith(f"+{code}"):
        return number[len(code) + 1:]
    if number.startswith(code):
        return number[len(code):]
    return number


def _strip_plus(number: str) -> str:
    return number.lstrip("+")


def _fix_malaysia(number: str) -> str:
    for prefix in ("+600", "600"):
        if number.startswith(prefix):
            rest = number[len(prefix):]
            replacement = ("+60" if prefix.startswith("+") else "60") + rest
            return replacement
    return number


def _post_process_numbers(numbers: list[str], country_code: str) -> list[str]:
    if country_code == "60":
        return [_fix_malaysia(n) for n in numbers]
    return numbers


def _build_number_buttons(country_code: str, code_embedded: bool, has_plus: bool) -> list:
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


def _extract_username_arg(raw: str) -> str:
    return raw.strip().lstrip("@")


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
    from callbacks import _show_ranges
    await _show_ranges(update, context, page=0)
