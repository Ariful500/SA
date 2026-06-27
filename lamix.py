"""
lamix.py — Lamix scraping + async wrappers (fixed v5)

v5 fix:
- allocate delay 0.5s → 0.2s (faster number allocation)
- সব অন্য logic same থেকেছে
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

_COUNTRY_CODES = {
    "afghanistan": "93", "albania": "355", "algeria": "213", "united states": "1",
    "andorra": "376", "angola": "244", "antigua and barbuda": "1", "argentina": "54",
    "armenia": "374", "australia": "61", "austria": "43", "azerbaijan": "994",
    "bahamas": "1", "bahrain": "973", "bangladesh": "880", "barbados": "1",
    "belarus": "375", "belgium": "32", "belize": "501", "benin": "229",
    "bhutan": "975", "bolivia": "591", "bosnia and herzegovina": "387", "bosnia": "387",
    "botswana": "267", "brazil": "55", "brunei": "673", "bulgaria": "359",
    "burkina faso": "226", "burundi": "257", "cambodia": "855", "cameroon": "237",
    "canada": "1", "cape verde": "238", "central african republic": "236", "chad": "235",
    "chile": "56", "china": "86", "colombia": "57", "comoros": "269",
    "dr congo": "243", "democratic republic of congo": "243", "congo": "242",
    "costa rica": "506", "croatia": "385", "cuba": "53", "cyprus": "357",
    "czech republic": "420", "czechia": "420", "denmark": "45", "djibouti": "253",
    "dominica": "1", "dominican republic": "1", "ecuador": "593", "egypt": "20",
    "el salvador": "503", "equatorial guinea": "240", "eritrea": "291",
    "estonia": "372", "ethiopia": "251", "eswatini": "268", "fiji": "679",
    "finland": "358", "france": "33", "gabon": "241", "gambia": "220",
    "georgia": "995", "germany": "49", "ghana": "233", "greece": "30",
    "grenada": "1", "guatemala": "502", "guinea-bissau": "245", "guinea bissau": "245",
    "guinea": "224", "guyana": "592", "haiti": "509", "honduras": "504",
    "hungary": "36", "iceland": "354", "india": "91", "indonesia": "62",
    "iran": "98", "iraq": "964", "ireland": "353", "israel": "972",
    "italy": "39", "ivory coast": "225", "cote d'ivoire": "225", "jamaica": "1",
    "japan": "81", "jordan": "962", "kazakhstan": "7", "kenya": "254",
    "kiribati": "686", "north korea": "850", "south korea": "82", "korea": "82",
    "kuwait": "965", "kyrgyzstan": "996", "laos": "856", "latvia": "371",
    "lebanon": "961", "lesotho": "266", "liberia": "231", "libya": "218",
    "liechtenstein": "423", "lithuania": "370", "luxembourg": "352", "madagascar": "261",
    "malawi": "265", "malaysia": "60", "maldives": "960", "mali": "223",
    "malta": "356", "marshall islands": "692", "mauritania": "222", "mauritius": "230",
    "mexico": "52", "micronesia": "691", "moldova": "373", "monaco": "377",
    "mongolia": "976", "montenegro": "382", "morocco": "212", "mozambique": "258",
    "myanmar": "95", "namibia": "264", "nauru": "674", "nepal": "977",
    "netherlands": "31", "new zealand": "64", "nicaragua": "505", "nigeria": "234",
    "niger": "227", "norway": "47", "oman": "968", "pakistan": "92",
    "palau": "680", "palestine": "970", "panama": "507", "papua new guinea": "675",
    "paraguay": "595", "peru": "51", "philippines": "63", "poland": "48",
    "portugal": "351", "qatar": "974", "romania": "40", "russia": "7",
    "rwanda": "250", "saint kitts and nevis": "1", "saint lucia": "1",
    "saint vincent and the grenadines": "1", "samoa": "685", "san marino": "378",
    "sao tome and principe": "239", "saudi arabia": "966", "saudi": "966",
    "senegal": "221", "serbia": "381", "seychelles": "248", "sierra leone": "232",
    "singapore": "65", "slovakia": "421", "slovenia": "386", "solomon islands": "677",
    "somalia": "252", "south africa": "27", "spain": "34", "sri lanka": "94",
    "sudan": "249", "suriname": "597", "sweden": "46", "switzerland": "41",
    "syria": "963", "taiwan": "886", "tajikistan": "992", "tanzania": "255",
    "thailand": "66", "timor-leste": "670", "timor leste": "670", "togo": "228",
    "tonga": "676", "trinidad and tobago": "1", "tunisia": "216", "turkey": "90",
    "turkmenistan": "993", "tuvalu": "688", "uganda": "256", "ukraine": "380",
    "united arab emirates": "971", "uae": "971", "united kingdom": "44", "uk": "44",
    "uruguay": "598", "uzbekistan": "998", "vanuatu": "678", "vatican city": "379",
    "venezuela": "58", "vietnam": "84", "yemen": "967", "zambia": "260",
    "zimbabwe": "263",
}


def _get_country_code(range_name: str) -> str:
    name = range_name.lower()
    for country in sorted(_COUNTRY_CODES.keys(), key=len, reverse=True):
        if country in name:
            return _COUNTRY_CODES[country]
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
#  ALLOCATE NUMBERS  (v5 — delay 0.5s → 0.2s)
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
        params = _numbers_params(echo="3", length=10000, frange="")
        resp = s.get(
            f"{LAMIX_URL}/ints/agent/res/data_smsnumbers.php",
            params=params,
            timeout=30,
        )
        all_rows = resp.json().get("aaData", [])
        rows = [r for r in all_rows if len(r) > 1 and str(r[1]).strip() == range_name]
        print(f"[Allocate] '{range_name}' rows: {len(rows)} (total: {len(all_rows)})")

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

        assigned = []
        mysms_referer = f"{LAMIX_URL}/ints/agent/MySMSNumbers?fclient=&frange="

        for num_id, number, payterm_val in available[:quantity]:
            success = False
            for attempt in range(2):
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
                            "X-Requested-With": None,
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "Content-Type": "application/x-www-form-urlencoded",
                            "Referer": mysms_referer,
                            "Origin": LAMIX_URL,
                            "Upgrade-Insecure-Requests": "1",
                        },
                        timeout=15,
                        allow_redirects=False,
                    )
                    print(f"[Allocate] Assign {number} (id:{num_id}) → {alloc_resp.status_code}")

                    if alloc_resp.status_code in (401, 403) or "login" in alloc_resp.headers.get("Location", "").lower():
                        print(f"[Allocate] Session invalid for {number}, re-login...")
                        s = _reset_session()
                        if not s:
                            break
                        continue

                    if alloc_resp.status_code == 302:
                        location = alloc_resp.headers.get("Location", mysms_referer)
                        if location.startswith("/"):
                            location = f"{LAMIX_URL}{location}"
                        elif not location.startswith("http"):
                            location = f"{LAMIX_URL}/ints/agent/{location}"
                        try:
                            s.get(location, headers={"Referer": mysms_referer}, timeout=15)
                        except Exception as e:
                            print(f"[Allocate] Follow-up GET error: {e}")
                        success = True
                        break
                    elif alloc_resp.status_code == 200:
                        success = True
                        break
                    else:
                        print(f"[Allocate] Unexpected status for {number}: {alloc_resp.status_code}")
                        break

                except Exception as e:
                    print(f"[Allocate] Error [{number}]: {e}")
                    break

            if success:
                assigned.append(number)

            # ✅ v5: 0.5s → 0.2s (faster allocation)
            time.sleep(0.2)

        print(f"[Allocate] Final result: {len(assigned)}/{quantity} assigned")

        if not assigned:
            return {"status": "failed", "numbers": [], "reason": "All assign requests failed"}

        return {"status": "success", "numbers": assigned}

    except Exception as e:
        print(f"[Allocate] Error: {e}")
        return None


async def allocate_numbers_async(client_id: str, range_name: str, quantity: int) -> dict | None:
    return await asyncio.to_thread(allocate_numbers, client_id, range_name, quantity)

# ══════════════════════════════════════════════
#  FETCH ACTIVE COUNT (ইউজারের currently active numbers)
# ══════════════════════════════════════════════

def fetch_active_count(lamix_username: str) -> int:
    s = _get_session()
    if not s:
        return 0
    try:
        params = _numbers_params(echo="4", length=10000)
        resp = s.get(
            f"{LAMIX_URL}/ints/agent/res/data_smsnumbers.php",
            params=params,
            timeout=30,
        )

        if resp.status_code in (302, 401, 403) or "login" in resp.url.lower():
            s = _reset_session()
            if not s:
                return 0
            resp = s.get(
                f"{LAMIX_URL}/ints/agent/res/data_smsnumbers.php",
                params=params,
                timeout=30,
            )

        rows = resp.json().get("aaData", [])
        count = 0
        for row in rows:
            if len(row) < 6:
                continue
            client_cell = str(row[5])
            soup = BeautifulSoup(client_cell, "html.parser")

            # unallocate link না থাকলে এটা assigned না
            if not soup.find("a", id="unallocate"):
                continue

            # unallocate link বাদ দিয়ে বাকি text = client username
            for tag in soup.find_all("a"):
                tag.decompose()
            client_name = soup.get_text(strip=True)

            if client_name.lower() == lamix_username.lower():
                count += 1

        print(f"[ActiveCount] {lamix_username}: {count} active numbers")
        return count

    except Exception as e:
        print(f"[ActiveCount] Error: {e}")
        return 0


async def fetch_active_count_async(lamix_username: str) -> int:
    return await asyncio.to_thread(fetch_active_count, lamix_username)
