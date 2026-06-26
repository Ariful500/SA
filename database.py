"""
database.py — JSON ফাইল ভিত্তিক ডেটাবেস (real-time git save)
"""
import json
import os
import asyncio
import subprocess
from datetime import datetime
from config import DAILY_LIMIT as _DEFAULT_DAILY_LIMIT, MAX_PER_ORDER as _DEFAULT_MAX_PER_ORDER

DB_FILE = "users.json"
SETTINGS_FILE = "settings.json"


# ══════════════════════════════════════════════
#  GIT SAVE (real-time commit + push)
# ══════════════════════════════════════════════

def _git_save(message: str = "💾 Auto-save: users data updated"):
    """প্রতিটা পরিবর্তনের পর git commit + push করে"""
    try:
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=False)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=False)
        subprocess.run(["git", "pull", "origin", "main", "--rebase"], check=False)
        subprocess.run(["git", "add", DB_FILE], check=False)
        result = subprocess.run(
            ["git", "diff", "--staged", "--quiet"],
            capture_output=True
        )
        if result.returncode != 0:  # পরিবর্তন আছে
            subprocess.run(["git", "commit", "-m", message], check=False)
            subprocess.run(["git", "push", "origin", "main"], check=False)
            print(f"[DB] ✅ Git saved: {message}")
        else:
            print("[DB] No changes to save.")
    except Exception as e:
        print(f"[DB] Git save error: {e}")


# ══════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════

def _load() -> dict:
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict, git_message: str = "💾 Auto-save: users data updated"):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _git_save(git_message)


def _load_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_settings(settings: dict, git_message: str = "⚙️ Settings updated"):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    try:
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=False)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=False)
        subprocess.run(["git", "pull", "origin", "main", "--rebase"], check=False)
        subprocess.run(["git", "add", SETTINGS_FILE], check=False)
        result = subprocess.run(["git", "diff", "--staged", "--quiet"], capture_output=True)
        if result.returncode != 0:
            subprocess.run(["git", "commit", "-m", git_message], check=False)
            subprocess.run(["git", "push", "origin", "main"], check=False)
            print(f"[Settings] ✅ Git saved: {git_message}")
        else:
            print("[Settings] No changes to save.")
    except Exception as e:
        print(f"[Settings] Git save error: {e}")


# ══════════════════════════════════════════════
#  INIT
# ══════════════════════════════════════════════

async def init_db():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f:
            json.dump({}, f)
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w") as f:
            json.dump({
                "daily_limit": _DEFAULT_DAILY_LIMIT,
                "max_per_order": _DEFAULT_MAX_PER_ORDER,
            }, f, indent=2)


# ══════════════════════════════════════════════
#  SETTINGS (Daily Limit / Max Per Order)
#  config.py এর ডিফল্ট ভ্যালুর বদলে এখন settings.json থেকে
#  রানটাইম ভ্যালু লোড হয়, যাতে /fetchlimit বাটন দিয়ে বদলালে
#  bot restart হলেও মান টিকে থাকে।
# ══════════════════════════════════════════════

async def get_daily_limit() -> int:
    settings = await asyncio.to_thread(_load_settings)
    return settings.get("daily_limit", _DEFAULT_DAILY_LIMIT)


async def get_max_per_order() -> int:
    settings = await asyncio.to_thread(_load_settings)
    return settings.get("max_per_order", _DEFAULT_MAX_PER_ORDER)


async def set_daily_limit(new_limit: int) -> int:
    """
    নতুন Daily Limit সেট করে এবং সবার (পুরনো ইউজার সহ) বর্তমান
    daily_limit এখনই নতুন ভ্যালুতে আপডেট করে দেয়। কতজন ইউজার
    আপডেট হলো তা রিটার্ন করে।
    """
    def _do():
        settings = _load_settings()
        settings["daily_limit"] = new_limit
        _save_settings(settings, f"⚙️ Daily limit changed to {new_limit}")

        data = _load()
        for uid in data:
            data[uid]["daily_limit"] = new_limit
        _save(data, f"⚙️ Daily limit applied to all users: {new_limit}")
        return len(data)
    return await asyncio.to_thread(_do)


async def set_max_per_order(new_max: int):
    """নতুন Max Per Order সেট করে। পরের অর্ডার থেকেই কার্যকর হবে।"""
    def _do():
        settings = _load_settings()
        settings["max_per_order"] = new_max
        _save_settings(settings, f"⚙️ Max per order changed to {new_max}")
    await asyncio.to_thread(_do)


# ══════════════════════════════════════════════
#  GET USER
# ══════════════════════════════════════════════

async def get_user(user_id: int) -> dict | None:
    data = await asyncio.to_thread(_load)
    return data.get(str(user_id))


# ══════════════════════════════════════════════
#  GET USER BY TELEGRAM USERNAME
#  (/addlimit, /ban, /unban, /reset কমান্ডে @Username ব্যবহারের জন্য)
# ══════════════════════════════════════════════

async def get_user_by_telegram_username(telegram_username: str) -> dict | None:
    """
    telegram_username — '@' চিহ্ন থাকুক বা না থাকুক, উভয়ই কাজ করবে।
    Telegram username case-insensitive, তাই lower() দিয়ে compare করা হয়েছে।
    """
    clean_username = telegram_username.lstrip("@").lower()

    def _do():
        data = _load()
        for user in data.values():
            tg_uname = (user.get("telegram_username") or "").lower()
            if tg_uname == clean_username:
                return user
        return None

    return await asyncio.to_thread(_do)


# ══════════════════════════════════════════════
#  USERNAME TAKEN CHECK
# ══════════════════════════════════════════════

async def is_username_taken(username: str) -> bool:
    data = await asyncio.to_thread(_load)
    for user in data.values():
        if user.get("username", "").lower() == username.lower():
            return True
    return False


# ══════════════════════════════════════════════
#  ADD USER
# ══════════════════════════════════════════════

async def add_user(user_id: int, telegram_username: str, lamix_username: str, client_id: str):
    current_limit = await get_daily_limit()

    def _do():
        data = _load()
        data[str(user_id)] = {
            "user_id": user_id,
            "username": lamix_username,
            "telegram_username": telegram_username,
            "client_id": client_id,
            "daily_used": 0,
            "daily_limit": current_limit,
            "total_allocated": 0,
            "is_banned": False,
            "created_at": datetime.now().isoformat(),
        }
        _save(data, f"👤 New user linked: {lamix_username}")
    await asyncio.to_thread(_do)


# ══════════════════════════════════════════════
#  UNLINK USER
# ══════════════════════════════════════════════

async def unlink_user(user_id: int):
    def _do():
        data = _load()
        data.pop(str(user_id), None)
        _save(data, "❌ User unlinked")
    await asyncio.to_thread(_do)


# ══════════════════════════════════════════════
#  UPDATE USAGE
# ══════════════════════════════════════════════

async def update_usage(user_id: int, quantity: int):
    def _do():
        data = _load()
        uid = str(user_id)
        if uid in data:
            data[uid]["daily_used"] += quantity
            data[uid]["total_allocated"] += quantity
            _save(data, f"📊 Usage updated: {quantity} numbers allocated")
    await asyncio.to_thread(_do)


# ══════════════════════════════════════════════
#  RESET ALL LIMITS
# ══════════════════════════════════════════════

async def reset_all_limits() -> int:
    current_limit = await get_daily_limit()

    def _do():
        data = _load()
        for uid in data:
            data[uid]["daily_used"] = 0
            data[uid]["daily_limit"] = current_limit
        _save(data, "🔄 All limits reset")
        return len(data)
    return await asyncio.to_thread(_do)


# ══════════════════════════════════════════════
#  RESET USER LIMIT
# ══════════════════════════════════════════════

async def reset_user_limit(user_id: int):
    current_limit = await get_daily_limit()

    def _do():
        data = _load()
        uid = str(user_id)
        if uid in data:
            data[uid]["daily_used"] = 0
            data[uid]["daily_limit"] = current_limit
            _save(data, f"🔄 User limit reset: {uid}")
    await asyncio.to_thread(_do)


# ══════════════════════════════════════════════
#  ADD USER LIMIT
# ══════════════════════════════════════════════

async def add_user_limit(user_id: int, amount: int):
    def _do():
        data = _load()
        uid = str(user_id)
        if uid in data:
            data[uid]["daily_limit"] += amount
            _save(data, f"➕ Limit added: {amount} for {uid}")
    await asyncio.to_thread(_do)


# ══════════════════════════════════════════════
#  BAN / UNBAN
# ══════════════════════════════════════════════

async def ban_user(user_id: int):
    def _do():
        data = _load()
        uid = str(user_id)
        if uid in data:
            data[uid]["is_banned"] = True
            _save(data, f"🚫 User banned: {uid}")
    await asyncio.to_thread(_do)


async def unban_user(user_id: int):
    def _do():
        data = _load()
        uid = str(user_id)
        if uid in data:
            data[uid]["is_banned"] = False
            _save(data, f"✅ User unbanned: {uid}")
    await asyncio.to_thread(_do)


# ══════════════════════════════════════════════
#  RESET MEMBER (পুরো ডেটা মুছে দেয় — unlink এর মতোই)
#  /reset @Username কমান্ডের জন্য
# ══════════════════════════════════════════════

async def reset_member(user_id: int):
    """ইউজারের সব ডেটা (লিমিট, ইউসেজ, লিঙ্ক) মুছে দেয়। আবার /link করতে হবে।"""
    def _do():
        data = _load()
        uid = str(user_id)
        removed = data.pop(uid, None)
        if removed is not None:
            _save(data, f"♻️ User fully reset: {uid}")
        return removed
    return await asyncio.to_thread(_do)


# ══════════════════════════════════════════════
#  GET ALL USERS
# ══════════════════════════════════════════════

async def get_all_users() -> list[dict]:
    data = await asyncio.to_thread(_load)
    return sorted(data.values(), key=lambda u: u.get("total_allocated", 0), reverse=True)


# ══════════════════════════════════════════════
#  LEADERBOARD
# ══════════════════════════════════════════════

async def get_leaderboard() -> list[dict]:
    data = await asyncio.to_thread(_load)
    users = [u for u in data.values() if not u.get("is_banned")]
    return sorted(users, key=lambda u: u.get("total_allocated", 0), reverse=True)[:20]


# ══════════════════════════════════════════════
#  TOTAL SMS
# ══════════════════════════════════════════════

async def get_total_sms() -> int:
    data = await asyncio.to_thread(_load)
    return sum(u.get("total_allocated", 0) for u in data.values())
