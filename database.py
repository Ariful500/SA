import aiosqlite
from config import DATABASE_NAME, DAILY_LIMIT


# ✅ ডেটাবেস ইনিশিয়ালাইজ
async def init_db():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                telegram_username TEXT,
                client_id TEXT,
                daily_used INTEGER DEFAULT 0,
                daily_limit INTEGER DEFAULT 120,
                total_allocated INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


# ✅ ইউজার আছে কিনা চেক
async def get_user(user_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            return await cursor.fetchone()


# ✅ নতুন ইউজার অ্যাড
async def add_user(user_id: int, telegram_username: str, lamix_username: str, client_id: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users 
            (user_id, username, telegram_username, client_id, daily_used, daily_limit, total_allocated, is_banned)
            VALUES (?, ?, ?, ?, 0, 120, 0, 0)
        """, (user_id, lamix_username, telegram_username, client_id))
        await db.commit()


# ✅ ইউজার আনলিঙ্ক
async def unlink_user(user_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "DELETE FROM users WHERE user_id = ?", (user_id,)
        )
        await db.commit()


# ✅ নম্বর ব্যবহার আপডেট
async def update_usage(user_id: int, quantity: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            UPDATE users 
            SET daily_used = daily_used + ?,
                total_allocated = total_allocated + ?
            WHERE user_id = ?
        """, (quantity, quantity, user_id))
        await db.commit()


# ✅ সব ইউজারের লিমিট রিসেট (অটো বা /refresh)
async def reset_all_limits():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            UPDATE users SET daily_used = 0, daily_limit = 120
        """)
        await db.commit()
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            return row[0]


# ✅ নির্দিষ্ট ইউজারের লিমিট রিসেট (Approve)
async def reset_user_limit(user_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            UPDATE users SET daily_used = 0, daily_limit = 120
            WHERE user_id = ?
        """, (user_id,))
        await db.commit()


# ✅ নির্দিষ্ট ইউজারের লিমিট বাড়ানো
async def add_user_limit(user_id: int, amount: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            UPDATE users SET daily_limit = daily_limit + ?
            WHERE user_id = ?
        """, (amount, user_id))
        await db.commit()


# ✅ ইউজার ব্যান
async def ban_user(user_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,)
        )
        await db.commit()


# ✅ ইউজার আনব্যান
async def unban_user(user_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,)
        )
        await db.commit()


# ✅ সব ইউজারের লিস্ট
async def get_all_users():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users ORDER BY total_allocated DESC"
        ) as cursor:
            return await cursor.fetchall()


# ✅ লিডারবোর্ড
async def get_leaderboard():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT telegram_username, username, total_allocated
            FROM users
            WHERE is_banned = 0
            ORDER BY total_allocated DESC
            LIMIT 20
        """) as cursor:
            return await cursor.fetchall()


# ✅ টোটাল SMS কাউন্ট
async def get_total_sms():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT SUM(total_allocated) FROM users"
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] or 0
      
