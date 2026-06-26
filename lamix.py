"""
lamix.py — Lamix scraping + async wrappers (fixed v4)

v4 fix: allocate_numbers() এখন সঠিক endpoint ব্যবহার করে।
Network tab capture থেকে কনফার্ম হয়েছে যে actual allocate request যায়:
    POST /ints/agent/MySMSNumbers?fclient=&frange=
(আগের res/allocatesmsnumber.php endpoint টা ভুল ছিল — সেটা শুধু modal/preview দেখায়,
আসল submit হয় MySMSNumbers পেজেই, normal form POST হিসেবে — তাই X-Requested-With
header ছাড়া পাঠাতে হবে এবং success বোঝা যায় 302 redirect দিয়ে, 200 দিয়ে না)
"""
import re
import time
import asyncio
import requests
from bs4 import BeautifulSoup

from config import LAMIX_URL, LAMIX_USERNAME, LAMIX_PASSWORD

_session: requests.Session | None = None


# ══════════════════════════════════════════════
#  LOGIN
# ══════════════════════════════════════════════

def _solve_captcha(soup: BeautifulSoup) -> str:
    text = soup.get_text(" ", strip=True)
    match = re.search(r'(\d+)\s*([+\-])\s*(\d+)', text)
    if match:
        a, op, b = int(match.group(1)), match.group(2), int(match.group(3))
        return str(a + b if op == '+' else a - b)
    return "0"


def _do_login() -> requests.Session | None:
    global _session
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        resp = session.get(f"{LAMIX_URL}/ints/login", timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        captcha = _solve_captcha(soup)
        print(f"[Login] Captcha: {captcha}")

        resp = session.post(
            f"{LAMIX_URL}/ints/signin",
            data={"username": LAMIX_USERNAME, "password": LAMIX_PASSWORD, "capt": captcha},
            timeout=15,
            allow_redirects=True,
        )
        if "login" in resp.url.lower():
            print("❌ Login Failed!")
            _session = None
            return None

        session.headers.update({
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": f"{LAMIX_URL}/ints/agent/MySMSNumbers",
            "Origin": LAMIX_URL,
        })
        _session = session
        print(f"✅ Login OK → {resp.url}")
        return session
    except Exception as e:
        print(f"[Login] Error: {e}")
        _session = None
        return None


def _get_session() -> requests.Session | None:
    global _session
    return _session if _session else _do_login()


def _reset_session() -> requests.Session | None:
    global _session
    _session = None
    return _do_login()


# ══════════════════════════════════════════════
#  NUMBERS API PARAMS
# ══════════════════════════════════════════════

def _numbers_params(echo: str = "1", length: int = 10000, frange: str = "") -> dict:
    params = {
        "frange": frange,
        "fclient": "",
        "totnum": "220",
        "sEcho": echo,
        "iColumns": "8",
        "sColumns": "%2C%2C%2C%2C%2C%2C%2C",
        "iDisplayStart": "0",
        "iDisplayLength": str(length),
        "sSearch": "",
        "bRegex": "false",
        "iSortCol_0": "0",
        "sSortDir_0": "asc",
        "iSortingCols": "1",
        "_": str(int(time.time() * 1000)),
    }
    for i in range(8):
        params[f"mDataProp_{i}"] = str(i)
        params[f"sSearch_{i}"] = ""
        params[f"bRegex_{i}"] = "false"
        params[f"bSearchable_{i}"] = "true"
        params[f"bSortable_{i}"] = "false" if i in (0, 7) else "true"
    return params


# ══════════════════════════════════════════════
#  AVAILABLE CHECK
# available = allocate link আছে, client নাম নেই
# assigned = client নাম আছে + unallocate link আছে
# ══════════════════════════════════════════════

def _is_available(client_cell: str) -> bool:
    soup = BeautifulSoup(client_cell, "html.parser")
    has_allocate   = bool(soup.find("a", id="allocate"))
    has_unallocate = bool(soup.find("a", id="unallocate"))
    return has_allocate and not has_unallocate


# ══════════════════════════════════════════════
#  COUNTRY CODE
# ══════════════════════════════════════════════

def _get_country_code(range_name: str) -> str:
    codes = {
        "malaysia": "60", "algeria": "213", "afghanistan": "93",
        "angola": "244", "comoros": "269", "oman": "968",
        "nigeria": "234", "kenya": "254", "egypt": "20",
        "iraq": "964", "jordan": "962", "morocco": "212",
        "pakistan": "92", "saudi": "966", "tunisia": "216",
        "uganda": "256", "ukraine": "380", "uzbekistan": "998",
        "vietnam": "84", "zimbabwe": "263", "myanmar": "95",
        "nepal": "977", "indonesia": "62", "ethiopia": "251",
        "cameroon": "237", "tanzania": "255", "sudan": "249",
        "syria": "963", "russia": "7", "georgia": "995",
        "kazakhstan": "7", "bangladesh": "880", "sri lanka": "94",
    }
    name = range_name.lower()
    for country, code in codes.items():
        if country in name:
            return code
    return ""


# ══════════════════════════════════════════════
#  FETCH RANGES (A→Z sorted, only truly available)
# ══════════════════════════════════════════════

def fetch_ranges() -> list[dict]:
    s = _get_session()
    if not s:
        return []
    try:
        params = _numbers_params(echo="2", length=10000)
        resp = s.get(
            f"{LAMIX_URL}/ints/agent/res/data_smsnumbers.php",
            params=params,
            timeout=30,
        )

        if resp.status_code in (302, 401, 403) or "login" in resp.url.lower():
            print("[Ranges] Session expired, re-login...")
            s = _reset_session()
            if not s:
                return []
            resp = s.get(
                f"{LAMIX_URL}/ints/agent/res/data_smsnumbers.php",
                params=params,
                timeout=30,
            )

        rows = resp.json().get("aaData", [])
        print(f"[Ranges] Total rows: {len(rows)}")

        range_dict: dict[str, dict] = {}

        for row in rows:
            if len(row) < 6:
                continue

            inp        = BeautifulSoup(str(row[0]), "html.parser").find("input")
            num_id     = inp["value"] if inp else ""
            range_name = str(row[1]).strip()
            number     = str(row[3]).strip()
            client_cell = str(row[5])

            payout_text = BeautifulSoup(str(row[4]), "html.parser").get_text(" ", strip=True)
            payterm = "Weekly" if "weekly" in payout_text.lower() else payout_text.split()[0]
            payout  = next((p for p in payout_text.split() if p.startswith("$")), "$0.019").replace("$", "")

            if range_name not in range_dict:
                range_dict[range_name] = {
                    "id": range_name,
                    "name": range_name,
                    "available": 0,
                    "total": 0,
                    "payterm": payterm,
                    "payout": payout,
                    "country_code": _get_country_code(range_name),
                    "numbers": [],
                    "number_ids": [],
                }

            range_dict[range_name]["total"] += 1

            if _is_available(client_cell) and num_id and number:
                range_dict[range_name]["available"] += 1
                range_dict[range_name]["numbers"].append(number)
                range_dict[range_name]["number_ids"].append(num_id)

        result = [r for r in range_dict.values() if r["available"] > 0]
        result.sort(key=lambda x: x["name"].upper())

        print(f"[Ranges] Available ranges (A→Z): {len(result)}")
        return result

    except Exception as e:
        print(f"[Ranges] Error: {e}")
        return []


async def fetch_ranges_async() -> list[dict]:
    return await asyncio.to_thread(fetch_ranges)


# ══════════════════════════════════════════════
#  VERIFY USERNAME
# ══════════════════════════════════════════════

def verify_username(username: str) -> tuple[str | None, bool]:
    s = _get_session()
    if not s:
        return None, False
    try:
        params = {
            "sEcho": "1", "iColumns": "8",
            "sColumns": "%2C%2C%2C%2C%2C%2C%2C",
            "iDisplayStart": "0", "iDisplayLength": "1000",
            "sSearch": "", "bRegex": "false",
            "iSortCol_0": "0", "sSortDir_0": "asc", "iSortingCols": "1",
            "_": str(int(time.time() * 1000)),
        }
        for i in range(8):
            params[f"mDataProp_{i}"] = str(i)
            params[f"sSearch_{i}"] = ""
            params[f"bRegex_{i}"] = "false"
            params[f"bSearchable_{i}"] = "true"
            params[f"bSortable_{i}"] = "false" if i in (0, 7) else "true"

        resp = s.get(
            f"{LAMIX_URL}/ints/agent/res/data_clients.php",
            params=params,
            headers={"Referer": f"{LAMIX_URL}/ints/agent/Clients"},
            timeout=15,
        )

        if resp.status_code in (302, 401, 403) or "login" in resp.url.lower():
            s = _reset_session()
            if not s:
                return None, False
            resp = s.get(
                f"{LAMIX_URL}/ints/agent/res/data_clients.php",
                params=params,
                headers={"Referer": f"{LAMIX_URL}/ints/agent/Clients"},
                timeout=15,
            )

        rows = resp.json().get("aaData", [])
        print(f"[Verify] Clients: {len(rows)}")

        for row in rows:
            row_username = str(row[1]).strip()
            if row_username.lower() == username.lower():
                inp = BeautifulSoup(str(row[0]), "html.parser").find("input")
                client_id = inp["value"] if inp else row_username
                print(f"[Verify] ✅ Found: {row_username}, ID: {client_id}")
                return client_id, True

        print(f"[Verify] ❌ Not found: {username}")
        return None, False

    except Exception as e:
        print(f"[Verify] Error: {e}")
        return None, False


async def verify_username_async(username: str) -> tuple[str | None, bool]:
    return await asyncio.to_thread(verify_username, username)


# ══════════════════════════════════════════════
#  ALLOCATE NUMBERS
#
#  ✅ FIXED (v4): Network tab capture থেকে কনফার্ম হয়েছে real endpoint:
#     POST /ints/agent/MySMSNumbers?fclient=&frange=
#     (NOT /ints/agent/res/allocatesmsnumber.php — সেটা ভুল ছিল)
#
#  Form fields (exact, ব্রাউজার থেকে capture করা):
#     action=allocate
#     id=<num_id>
#     frange=
#     fclient=
#     client=<client_id>
#     payterm=2        (Weekly)
#     payout=0
#
#  Success signal: HTTP 302 redirect (Location: MySMSNumbers?fclient=&frange=)
#  — এটা normal form POST, তাই X-Requested-With header পাঠানো হয়নি এখানে
#  (session-level X-Requested-With override করে None সেট করা হয়েছে)
# ══════════════════════════════════════════════

PAYTERM_MAP = {
    "daily": "1", "weekly": "2", "weekly7": "3",
    "biweekly": "4", "biweekly30": "5",
    "monthly15": "6", "monthly30": "7",
    "monthly45": "8", "monthly60": "9",
}


def allocate_numbers(client_id: str, range_name: str, quantity: int) -> dict | None:
    s = _get_session()
    if not s:
        return None
    try:
        # frange filter কাজ করে না, তাই সব data এনে range_name দিয়ে filter করি
        params = _numbers_params(echo="3", length=10000, frange="")
        resp = s.get(
            f"{LAMIX_URL}/ints/agent/res/data_smsnumbers.php",
            params=params,
            timeout=30,
        )
        all_rows = resp.json().get("aaData", [])
        rows = [r for r in all_rows if len(r) > 1 and str(r[1]).strip() == range_name]
        print(f"[Allocate] '{range_name}' rows: {len(rows)} (total: {len(all_rows)})")

        # Step 2: Available numbers collect
        available = []
        for row in rows:
            if len(row) < 6:
                continue
            if not _is_available(str(row[5])):
                continue
            inp = BeautifulSoup(str(row[0]), "html.parser").find("input")
            num_id = inp["value"] if inp else ""
            number = str(row[3]).strip()
            payout_text = BeautifulSoup(str(row[4]), "html.parser").get_text(" ", strip=True).lower()
            payterm_val = "2"  # default Weekly
            for key, val in PAYTERM_MAP.items():
                if key in payout_text:
                    payterm_val = val
                    break
            if num_id and number:
                available.append((num_id, number, payterm_val))
            if len(available) >= quantity:
                break

        print(f"[Allocate] '{range_name}' available: {len(available)}, requested: {quantity}")

        if len(available) < quantity:
            return {
                "status": "failed",
                "numbers": [],
                "reason": f"Only {len(available)} available, requested {quantity}",
            }

        # Step 3: প্রতিটা number সঠিক endpoint দিয়ে allocate করুন
        assigned = []
        mysms_referer = f"{LAMIX_URL}/ints/agent/MySMSNumbers?fclient=&frange="

        for num_id, number, payterm_val in available[:quantity]:
            try:
                alloc_resp = s.post(
                    f"{LAMIX_URL}/ints/agent/MySMSNumbers",
                    params={"fclient": "", "frange": ""},
                    data={
                        "action":  "allocate",
                        "id":      num_id,
                        "frange":  "",
                        "fclient": "",
                        "client":  client_id,
                        "payterm": payterm_val,
                        "payout":  "0",
                    },
                    headers={
                        # browser capture-এ এই request টা plain form submit ছিল,
                        # XHR না — তাই AJAX headers override করে বাদ দেওয়া হলো
                        "X-Requested-With": None,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Referer": mysms_referer,
                        "Origin": LAMIX_URL,
                        "Upgrade-Insecure-Requests": "1",
                    },
                    timeout=15,
                    allow_redirects=False,  # 302 ধরার জন্য, follow করব না
                )
                print(f"[Allocate] Assign {number} (id:{num_id}) → {alloc_resp.status_code}")
                print(f"[Allocate] Location: {alloc_resp.headers.get('Location', '')}")

                # ✅ Success signal = 302 redirect (capture-এ এটাই দেখা গেছে)
                # কিছু সার্ভার configuration এ 200 ও আসতে পারে, তাই দুটোই allow
                if alloc_resp.status_code in (302, 200):
                    assigned.append(number)
                else:
                    print(f"[Allocate] Unexpected status for {number}: {alloc_resp.status_code}")

            except Exception as e:
                print(f"[Allocate] Error [{number}]: {e}")

        if not assigned:
            return {"status": "failed", "numbers": [], "reason": "All assign requests failed"}

        return {"status": "success", "numbers": assigned}

    except Exception as e:
        print(f"[Allocate] Error: {e}")
        return None


async def allocate_numbers_async(client_id: str, range_name: str, quantity: int) -> dict | None:
    return await asyncio.to_thread(allocate_numbers, client_id, range_name, quantity)
