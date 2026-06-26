"""
database.py — JSON ফাইল ভিত্তিক ডেটাবেস (GitHub Actions compatible)
"""
import json
import os
import asyncio
from datetime import datetime
from config import DAILY_LIMIT

DB_FILE = "users.json"


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


def _save(data: dict):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════
#  INIT (SQLite এর মতো compatibility রাখা)
# ══════════════════════════════════════════════

async def init_db():
    if not os.path.exists(DB_FILE):
        _save({})


# ══════════════════════════════════════════════
#  GET USER
# ══════════════════════════════════════════════

async def get_user(user_id: int) -> dict | None:
    data = await asyncio.to_thread(_load)
    return data.get(str(user_id))


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
    def _do():
        data = _load()
        data[str(user_id)] = {
            "user_id": user_id,
            "username": lamix_username,
            "telegram_username": telegram_username,
            "client_id": client_id,
            "daily_used": 0,
            "daily_limit": DAILY_LIMIT,
            "total_allocated": 0,
            "is_banned": False,
            "created_at": datetime.now().isoformat(),
        }
        _save(data)
    await asyncio.to_thread(_do)


# ══════════════════════════════════════════════
#  UNLINK USER
# ══════════════════════════════════════════════

async def unlink_user(user_id: int):
    def _do():
        data = _load()
        data.pop(str(user_id), None)
        _save(data)
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
            _save(data)
    await asyncio.to_thread(_do)


# ══════════════════════════════════════════════
#  RESET ALL LIMITS
# ══════════════════════════════════════════════

async def reset_all_limits() -> int:
    def _do():
        data = _load()
        for uid in data:
            data[uid]["daily_used"] = 0
            data[uid]["daily_limit"] = DAILY_LIMIT
        _save(data)
        return len(data)
    return await asyncio.to_thread(_do)


# ══════════════════════════════════════════════
#  RESET USER LIMIT
# ══════════════════════════════════════════════

async def reset_user_limit(user_id: int):
    def _do():
        data = _load()
        uid = str(user_id)
        if uid in data:
            data[uid]["daily_used"] = 0
            data[uid]["daily_limit"] = DAILY_LIMIT
            _save(data)
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
            _save(data)
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
            _save(data)
    await asyncio.to_thread(_do)


async def unban_user(user_id: int):
    def _do():
        data = _load()
        uid = str(user_id)
        if uid in data:
            data[uid]["is_banned"] = False
            _save(data)
    await asyncio.to_thread(_do)


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
    
