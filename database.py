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

import threading
_db_lock = threading.RLock()
_settings_lock = threading.RLock()
_git_lock = threading.Lock()


# ══════════════════════════════════════════════
#  GIT SAVE (real-time commit + push)
# ══════════════════════════════════════════════

def _git_commit_push(filepath: str, message: str):
    """Git push আলাদা lock দিয়ে সিরিয়ালাইজড — DB lock এর বাইরে চলে,
    তাই কারো ধীর push অন্য কারো read/write ব্লক করে না, আর দুইটা
    push একসাথে চললে .git/index.lock কনফ্লিক্টও হবে না।"""
    with _git_lock:
        try:
            subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=False)
            subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=False)
            subprocess.run(["git", "pull", "origin", "main", "--rebase"], check=False)
            subprocess.run(["git", "add", filepath], check=False)
            result = subprocess.run(
                ["git", "diff", "--staged", "--quiet"],
                capture_output=True
            )
            if result.returncode != 0:
                subprocess.run(["git", "commit", "-m", message], check=False)
                subprocess.run(["git", "push", "origin", "main"], check=False)
                print(f"[Git] ✅ Saved: {message}")
            else:
                print("[Git] No changes to save.")
        except Exception as e:
            print(f"[Git] Save error: {e}")


# ══════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════

def _load() -> dict:
    with _db_lock:
        if not os.path.exists(DB_FILE):
            return {}
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}


def _save(data: dict, git_message: str = "💾 Auto-save: users data updated"):
    with _db_lock:
        tmp_file = f"{DB_FILE}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, DB_FILE)
    # ✅ lock ছাড়ার পরে push হচ্ছে — অন্য ইউজারের read/write আটকাবে না
    _git_commit_push(DB_FILE, git_message)


def _load_settings() -> dict:
    with _settings_lock:
        if not os.path.exists(SETTINGS_FILE):
            return {}
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}


def _save_settings(settings: dict, git_message: str = "⚙️ Settings updated"):
    with _settings_lock:
        tmp_file = f"{SETTINGS_FILE}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, SETTINGS_FILE)
    _git_commit_push(SETTINGS_FILE, git_message)


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
                "auto_approve": False,
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
    def _do():
        with _settings_lock, _db_lock:
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
    def _do():
        with _settings_lock:
            settings = _load_settings()
            settings["max_per_order"] = new_max
            _save_settings(settings, f"⚙️ Max per order changed to {new_max}")
    await asyncio.to_thread(_do)


# ══════════════════════════════════════════════
#  AUTO-APPROVE TOGGLE
#  ON থাকলে "Request Limit Reset" রিকোয়েস্ট ১০ সেকেন্ড পর
#  স্বয়ংক্রিয়ভাবে approve হয়ে যায়।
# ══════════════════════════════════════════════

async def get_auto_approve() -> bool:
    settings = await asyncio.to_thread(_load_settings)
    return bool(settings.get("auto_approve", False))


async def set_auto_approve(enabled: bool):
    def _do():
        with _settings_lock:
            settings = _load_settings()
            settings["auto_approve"] = enabled
            _save_settings(settings, f"⚙️ Auto-approve set to {enabled}")
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
        existing = user.get("username")
        if existing and existing.lower() == username.lower():
            return True
    return False


# ══════════════════════════════════════════════
#  REGISTER START USER
#  /start কমান্ডে কল হয়। ইউজার যদি প্রথমবার বট চালু করে,
#  তাহলে একটা স্থায়ী রেকর্ড তৈরি হয় (lamix link ছাড়াই)।
#  এই রেকর্ড কখনো ডিলিট হয় না — unlink/reset শুধু lamix
#  link ফিল্ড মুছে দেয়, পুরো রেকর্ড না।
# ══════════════════════════════════════════════

async def register_start_user(user_id: int, telegram_username: str):
    current_limit = await get_daily_limit()

    def _do():
        with _db_lock:
            data = _load()
            uid = str(user_id)
            if uid in data:
                data[uid]["telegram_username"] = telegram_username
                _save(data, f"👋 User re-started bot: {telegram_username}")
            else:
                data[uid] = {
                    "user_id": user_id,
                    "username": None,
                    "telegram_username": telegram_username,
                    "client_id": None,
                    "is_linked": False,
                    "daily_used": 0,
                    "daily_limit": current_limit,
                    "total_allocated": 0,
                    "is_banned": False,
                    "pending_reset_request": False,
                    "created_at": datetime.now().isoformat(),
                }
                _save(data, f"👋 New user started bot: {telegram_username}")
    await asyncio.to_thread(_do)

# ══════════════════════════════════════════════
#  ADD USER (LINK)
#  /start এর কারণে রেকর্ড আগে থেকেই থাকতে পারে (limit/total সহ)।
#  তাই এখানে নতুন রেকর্ড না বানিয়ে existing রেকর্ড আপডেট করা হয়,
#  যাতে পুরনো daily_limit/total_allocated হারিয়ে না যায়।
# ══════════════════════════════════════════════

async def add_user(user_id: int, telegram_username: str, lamix_username: str, client_id: str):
    """⚠️ পুরনো ফাংশন — নতুন কোডে try_link_user() ব্যবহার করুন (race-free)।"""
    current_limit = await get_daily_limit()

    def _do():
        with _db_lock:
            data = _load()
            uid = str(user_id)
            if uid in data:
                data[uid]["username"] = lamix_username
                data[uid]["telegram_username"] = telegram_username
                data[uid]["client_id"] = client_id
                data[uid]["is_linked"] = True
            else:
                data[uid] = {
                    "user_id": user_id,
                    "username": lamix_username,
                    "telegram_username": telegram_username,
                    "client_id": client_id,
                    "is_linked": True,
                    "daily_used": 0,
                    "daily_limit": current_limit,
                    "total_allocated": 0,
                    "is_banned": False,
                    "pending_reset_request": False,
                    "created_at": datetime.now().isoformat(),
                }
            _save(data, f"👤 User linked: {lamix_username}")
    await asyncio.to_thread(_do)


# ══════════════════════════════════════════════
#  ATOMIC LINK — username-taken চেক + link একসাথে এক lock এ
#  (দুজন একসাথে একই Lamix username link করার race বন্ধ করে)
# ══════════════════════════════════════════════

async def try_link_user(user_id: int, telegram_username: str, lamix_username: str, client_id: str) -> bool:
    current_limit = await get_daily_limit()

    def _do():
        with _db_lock:
            data = _load()
            uid = str(user_id)

            for other_uid, other_user in data.items():
                if other_uid == uid:
                    continue
                existing = other_user.get("username")
                if existing and existing.lower() == lamix_username.lower():
                    return False  # ❌ অন্য কেউ ইতিমধ্যে নিয়ে নিয়েছে

            if uid in data:
                data[uid]["username"] = lamix_username
                data[uid]["telegram_username"] = telegram_username
                data[uid]["client_id"] = client_id
                data[uid]["is_linked"] = True
            else:
                data[uid] = {
                    "user_id": user_id,
                    "username": lamix_username,
                    "telegram_username": telegram_username,
                    "client_id": client_id,
                    "is_linked": True,
                    "daily_used": 0,
                    "daily_limit": current_limit,
                    "total_allocated": 0,
                    "is_banned": False,
                    "pending_reset_request": False,
                    "created_at": datetime.now().isoformat(),
                }
            _save(data, f"👤 User linked: {lamix_username}")
            return True

    return await asyncio.to_thread(_do)


# ══════════════════════════════════════════════
#  UNLINK USER
#  পুরো রেকর্ড ডিলিট হয় না — শুধু lamix-link তথ্য
#  (username, client_id) মুছে যায়, daily_limit/daily_used/
#  total_allocated/is_banned অপরিবর্তিত থাকে।
# ══════════════════════════════════════════════

async def unlink_user(user_id: int):
    def _do():
        with _db_lock:
            data = _load()
            uid = str(user_id)
            if uid in data:
                data[uid]["username"] = None
                data[uid]["client_id"] = None
                data[uid]["is_linked"] = False
                _save(data, "❌ User unlinked (limit/usage preserved)")
    await asyncio.to_thread(_do)

# ══════════════════════════════════════════════
#  UPDATE USAGE
# ══════════════════════════════════════════════

async def update_usage(user_id: int, quantity: int):
    def _do():
        with _db_lock:
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
        with _db_lock:
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
        with _db_lock:
            data = _load()
            uid = str(user_id)
            if uid in data:
                data[uid]["daily_used"] = 0
                data[uid]["daily_limit"] = current_limit
                _save(data, f"🔄 User limit reset: {uid}")
    await asyncio.to_thread(_do)


# ══════════════════════════════════════════════
#  RESET USER USAGE ONLY (limit অপরিবর্তিত থাকে)
#  Individual "Request Limit Reset" approve করার জন্য —
#  ইউজারের কাস্টম daily_limit (যেমন /addlimit দিয়ে সেট করা)
#  না বদলে শুধু আজকের ব্যবহার (daily_used) শূন্য করে।
#  রিটার্ন করে ইউজারের (অপরিবর্তিত) daily_limit।
# ══════════════════════════════════════════════

async def reset_user_usage(user_id: int) -> int | None:
    def _do():
        with _db_lock:
            data = _load()
            uid = str(user_id)
            if uid in data:
                data[uid]["daily_used"] = 0
                _save(data, f"🔄 User usage reset (limit unchanged): {uid}")
                return data[uid]["daily_limit"]
            return None
    return await asyncio.to_thread(_do)

# ══════════════════════════════════════════════
#  PENDING RESET REQUEST FLAG
#  "Request Limit Reset" বাটনে একবারে একটাই পেন্ডিং রিকোয়েস্ট
#  রাখার জন্য — Admin approve/deny না করা পর্যন্ত নতুন
#  রিকোয়েস্ট পাঠানো ব্লক করতে এই ফ্ল্যাগ ব্যবহার হয়।
# ══════════════════════════════════════════════

async def has_pending_reset_request(user_id: int) -> bool:
    data = await asyncio.to_thread(_load)
    user = data.get(str(user_id))
    return bool(user and user.get("pending_reset_request"))


async def set_pending_reset_request(user_id: int, pending: bool):
    def _do():
        with _db_lock:
            data = _load()
            uid = str(user_id)
            if uid in data:
                data[uid]["pending_reset_request"] = pending
                _save(data, f"🔔 Pending reset request flag set to {pending} for {uid}")
    await asyncio.to_thread(_do)

# ══════════════════════════════════════════════
#  ADD USER LIMIT
# ══════════════════════════════════════════════

async def add_user_limit(user_id: int, amount: int):
    def _do():
        with _db_lock:
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
        with _db_lock:
            data = _load()
            uid = str(user_id)
            if uid in data:
                data[uid]["is_banned"] = True
                _save(data, f"🚫 User banned: {uid}")
    await asyncio.to_thread(_do)


async def unban_user(user_id: int):
    def _do():
        with _db_lock:
            data = _load()
            uid = str(user_id)
            if uid in data:
                data[uid]["is_banned"] = False
                _save(data, f"✅ User unbanned: {uid}")
    await asyncio.to_thread(_do)

# ══════════════════════════════════════════════
#  RESET MEMBER (lamix-link মুছে দেয়, /unlink এর মতোই)
#  /reset @Username কমান্ডের জন্য — daily_limit, daily_used,
#  total_allocated, is_banned অপরিবর্তিত থাকে। শুধু lamix
#  username ও client_id মুছে যায়, ইউজারকে আবার /link করতে হবে।
# ══════════════════════════════════════════════

async def reset_member(user_id: int) -> dict | None:
    def _do():
        with _db_lock:
            data = _load()
            uid = str(user_id)
            if uid in data:
                snapshot = dict(data[uid])
                data[uid]["username"] = None
                data[uid]["client_id"] = None
                data[uid]["is_linked"] = False
                _save(data, f"♻️ User lamix-link reset (limit/usage preserved): {uid}")
                return snapshot
            return None
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
        
# ══════════════════════════════════════════════
#  SYNC TOTAL ALLOCATED (Lamix থেকে live count আপডেট)
# ══════════════════════════════════════════════

async def sync_total_allocated(user_id: int, lamix_username: str) -> int:
    import lamix
    active_count = await lamix.fetch_active_count_async(lamix_username)

    def _do():
        with _db_lock:
            data = _load()
            uid = str(user_id)
            if uid in data:
                data[uid]["total_allocated"] = active_count
                _save(data, f"🔄 Total allocated synced: {lamix_username} = {active_count}")
            return active_count

    return await asyncio.to_thread(_do)

# ══════════════════════════════════════════════
#  GET USER BY LAMIX USERNAME (SMS limit overage এর জন্য)
# ══════════════════════════════════════════════

async def get_user_by_lamix_username(lamix_username: str) -> dict | None:
    clean = lamix_username.strip().lower()

    def _do():
        data = _load()
        for user in data.values():
            uname = (user.get("username") or "").lower()
            if uname == clean:
                return user
        return None

    return await asyncio.to_thread(_do)
