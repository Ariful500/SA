"""
lamix.py — Lamix ওয়েবসাইট স্ক্রেপিং + অ্যাসিঙ্ক র‍্যাপার
"""
import re
import time
import asyncio
import requests
from bs4 import BeautifulSoup

from config import LAMIX_URL, LAMIX_USERNAME, LAMIX_PASSWORD

# ── Global Session ─────────────────────────────────────────────────────────────
_session: requests.Session | None = None


# ══════════════════════════════════════════════
#  CAPTCHA + LOGIN  (proven method)
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    try:
        # Step 1: GET login page — cookie + captcha নেওয়া
        resp = session.get(f"{LAMIX_URL}/ints/login", timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        captcha = _solve_captcha(soup)
        print(f"[Login] Captcha solved: {captcha}")

        # Step 2: POST credentials
        resp = session.post(
            f"{LAMIX_URL}/ints/signin",
            data={
                "username": LAMIX_USERNAME,
                "password": LAMIX_PASSWORD,
                "capt": captcha,
            },
            timeout=15,
            allow_redirects=True,
        )
        print(f"[Login] POST → {resp.url}")

        # Step 3: Success check
        # signin → 302 → agent/ → 302 → SMSDashboard (200)
        # ব্যর্থ হলে /ints/login এ ফিরে আসবে
        if "login" in resp.url.lower():
            print("❌ Lamix Login Failed!")
            print(f"[Login] Response preview: {resp.text[:400]}")
            _session = None
            return None

        print(f"✅ Login success! Landed on: {resp.url}")

        # Step 4: API headers সেট
        session.headers.update({
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{LAMIX_URL}/ints/agent/SMSDashboard",
            "Origin": LAMIX_URL,
        })
        _session = session
        print("✅ Lamix Login OK")
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
#  DATA TABLE PARAMS
# ══════════════════════════════════════════════

def _base_params(echo: str = "1", length: int = 10000) -> dict:
    return {
        "frange": "", "fclient": "", "totnum": "220",
        "sEcho": echo,
        "iColumns": "8",
        "sColumns": "%2C%2C%2C%2C%2C%2C%2C",
        "iDisplayStart": "0",
        "iDisplayLength": str(length),
        **{f"mDataProp_{i}": str(i) for i in range(8)},
        **{f"sSearch_{i}": "" for i in range(8)},
        **{f"bRegex_{i}": "false" for i in range(8)},
        **{f"bSearchable_{i}": "true" for i in range(8)},
        **{f"bSortable_{i}": "false" if i in (0, 7) else "true" for i in range(8)},
        "sSearch": "", "bRegex": "false",
        "iSortCol_0": "0", "sSortDir_0": "asc", "iSortingCols": "1",
        "_": str(int(time.time() * 1000)),
    }


# ══════════════════════════════════════════════
#  USERNAME VERIFY
# ══════════════════════════════════════════════

def verify_username(username: str) -> tuple[str | None, bool]:
    s = _get_session()
    if not s:
        return None, False
    try:
        params = {
            "sEcho": "1",
            "iColumns": "8",
            "sColumns": "%2C%2C%2C%2C%2C%2C%2C",
            "iDisplayStart": "0",
            "iDisplayLength": "1000",
            **{f"mDataProp_{i}": str(i) for i in range(8)},
            **{f"sSearch_{i}": "" for i in range(8)},
            **{f"bRegex_{i}": "false" for i in range(8)},
            **{f"bSearchable_{i}": "true" for i in range(8)},
            **{f"bSortable_{i}": "false" if i in (0, 7) else "true" for i in range(8)},
            "sSearch": "", "bRegex": "false",
            "iSortCol_0": "0", "sSortDir_0": "asc", "iSortingCols": "1",
            "_": str(int(time.time() * 1000)),
        }
        headers = {
            "Referer": f"{LAMIX_URL}/ints/agent/Clients",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }
        resp = s.get(
            f"{LAMIX_URL}/ints/agent/res/data_clients.php",
            params=params,
            headers=headers,
            timeout=15,
        )
        print(f"[Verify] Clients API: {resp.status_code}")

        # Session expire হলে re-login
        if resp.status_code in (302, 401, 403) or "login" in resp.url.lower():
            print("[Verify] Session expired, re-logging in...")
            s = _reset_session()
            if not s:
                return None, False
            resp = s.get(
                f"{LAMIX_URL}/ints/agent/res/data_clients.php",
                params=params,
                headers=headers,
                timeout=15,
            )

        if resp.status_code != 200:
            return None, False

        data = resp.json()
        rows = data.get("aaData", [])
        print(f"[Verify] Clients found: {len(rows)}")

        for row in rows:
            row_username = str(row[1]).strip()
            if row_username.lower() == username.lower():
                inp = BeautifulSoup(str(row[0]), "html.parser").find("input")
                client_id = inp["value"] if inp else row_username
                print(f"[Verify] ✅ Matched: {row_username}, client_id: {client_id}")
                return client_id, True

        print(f"[Verify] ❌ Not found: {username}")
        return None, False

    except Exception as e:
        print(f"[Verify] Error: {e}")
        return None, False


async def verify_username_async(username: str) -> tuple[str | None, bool]:
    return await asyncio.to_thread(verify_username, username)


# ══════════════════════════════════════════════
#  FETCH RANGES
# ══════════════════════════════════════════════

def _is_available(client_cell: str) -> bool:
    text = BeautifulSoup(client_cell, "html.parser").get_text(strip=True)
    return text in ("", "/", "✏")


def _get_country_code(range_name: str) -> str:
    codes = {
        "algeria": "213", "afghanistan": "93", "angola": "244",
        "comoros": "269", "malaysia": "60", "oman": "968",
        "nigeria": "234", "kenya": "254", "egypt": "20",
        "iraq": "964", "jordan": "962", "morocco": "212",
        "pakistan": "92", "saudi": "966", "tunisia": "216",
        "uganda": "256", "ukraine": "380", "uzbekistan": "998",
        "vietnam": "84", "zimbabwe": "263", "myanmar": "95",
        "nepal": "977", "indonesia": "62", "ethiopia": "251",
        "cameroon": "237", "tanzania": "255", "sudan": "249",
        "syria": "963", "russia": "7", "georgia": "995",
        "kazakhstan": "7", "bangladesh": "880",
    }
    name = range_name.lower()
    for country, code in codes.items():
        if country in name:
            return code
    return ""


def fetch_ranges() -> list[dict]:
    s = _get_session()
    if not s:
        return []
    try:
        params = _base_params(echo="2", length=10000)
        headers = {
            "Referer": f"{LAMIX_URL}/ints/agent/Numbers",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }
        resp = s.get(
            f"{LAMIX_URL}/ints/agent/res/data_smsnumbers.php",
            params=params,
            headers=headers,
            timeout=30,
        )

        if resp.status_code == 403 or "login" in resp.url.lower():
            print("[Ranges] Session expired, re-logging in...")
            s = _reset_session()
            if not s:
                return []
            resp = s.get(
                f"{LAMIX_URL}/ints/agent/res/data_smsnumbers.php",
                params=params,
                headers=headers,
                timeout=30,
            )

        rows = resp.json().get("aaData", [])
        range_dict: dict[str, dict] = {}

        for row in rows:
            range_name = str(row[0]).strip()
            number     = str(row[2]).strip()
            payout_raw = BeautifulSoup(str(row[3]), "html.parser").get_text(" ", strip=True) if len(row) > 3 else "Weekly $0.019"
            payterm    = "Weekly" if "weekly" in payout_raw.lower() else payout_raw.split()[0]
            payout     = next((p for p in payout_raw.split() if p.startswith("$")), "$0.019").replace("$", "")
            client     = str(row[4]).strip() if len(row) > 4 else ""

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
                }

            range_dict[range_name]["total"] += 1
            if _is_available(client):
                range_dict[range_name]["available"] += 1
                range_dict[range_name]["numbers"].append(number)

        return [r for r in range_dict.values() if r["available"] > 0]

    except Exception as e:
        print(f"[Ranges] Error: {e}")
        return []


async def fetch_ranges_async() -> list[dict]:
    return await asyncio.to_thread(fetch_ranges)


# ══════════════════════════════════════════════
#  ALLOCATE NUMBERS
# ══════════════════════════════════════════════

def allocate_numbers(client_id: str, range_name: str, quantity: int) -> dict | None:
    s = _get_session()
    if not s:
        return None
    try:
        params = _base_params(echo="3", length=10000)
        params["frange"] = range_name
        headers = {
            "Referer": f"{LAMIX_URL}/ints/agent/Numbers",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }
        resp = s.get(
            f"{LAMIX_URL}/ints/agent/res/data_smsnumbers.php",
            params=params,
            headers=headers,
            timeout=30,
        )
        rows = resp.json().get("aaData", [])

        available_numbers, number_ids = [], []
        for row in rows:
            client = str(row[4]).strip() if len(row) > 4 else ""
            if _is_available(client):
                number = str(row[2]).strip()
                inp = BeautifulSoup(str(row[0]), "html.parser").find("input")
                num_id = inp["value"] if inp else ""
                available_numbers.append(number)
                number_ids.append(num_id)
            if len(available_numbers) >= quantity:
                break

        if len(available_numbers) < quantity:
            return {"status": "failed", "numbers": []}

        assigned = []
        for num_id, number in zip(number_ids[:quantity], available_numbers[:quantity]):
            try:
                r = s.post(
                    f"{LAMIX_URL}/ints/agent/Numbers",
                    data={"action": "assign", "eid": num_id, "client_id": client_id},
                    timeout=15,
                )
                if r.status_code == 200:
                    assigned.append(number)
            except Exception as e:
                print(f"[Allocate] Error [{number}]: {e}")

        if not assigned:
            return {"status": "failed", "numbers": []}

        return {"status": "success", "numbers": assigned}

    except Exception as e:
        print(f"[Allocate] Error: {e}")
        return None


async def allocate_numbers_async(client_id: str, range_name: str, quantity: int) -> dict | None:
    return await asyncio.to_thread(allocate_numbers, client_id, range_name, quantity)
    
