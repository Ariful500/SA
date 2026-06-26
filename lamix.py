import re
import time
import requests
from bs4 import BeautifulSoup

from config import LAMIX_URL, LAMIX_USERNAME, LAMIX_PASSWORD

# ── Global Session ─────────────────────────────────────────────────────────────
_session = None


# ✅ Captcha সমাধান
def solve_captcha(soup):
    text = soup.get_text(" ", strip=True)
    match = re.search(r'(\d+)\s*([+\-])\s*(\d+)', text)
    if match:
        a, op, b = int(match.group(1)), match.group(2), int(match.group(3))
        return str(a + b if op == '+' else a - b)
    return "0"


# ✅ Lamix এ লগইন
def do_login():
    global _session
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    try:
        resp = session.get(f"{LAMIX_URL}/login", timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        captcha = solve_captcha(soup)

        resp = session.post(
            f"{LAMIX_URL}/signin",
            data={
                "username": LAMIX_USERNAME,
                "password": LAMIX_PASSWORD,
                "capt": captcha,
            },
            timeout=15,
            allow_redirects=True,
        )

        if "login" in resp.url.lower():
            print("❌ Lamix Login Failed!")
            _session = None
            return None

        print("✅ Lamix Login Successful!")
        session.headers.update({
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{LAMIX_URL}/ints/agent",
            "Origin": LAMIX_URL,
        })
        _session = session
        return session

    except Exception as e:
        print(f"Login Error: {e}")
        _session = None
        return None


# ✅ Session পাও
def get_session():
    global _session
    if _session is None:
        return do_login()
    return _session


# ✅ Session রিসেট
def reset_session():
    global _session
    _session = None
    return do_login()


# ✅ ইউজারের Lamix username ভেরিফাই
def verify_username(username: str):
    session = get_session()
    if not session:
        return None, False
    try:
        params = {
            "sEcho": "1",
            "iColumns": "8",
            "sColumns": ",,,,,,",
            "iDisplayStart": "0",
            "iDisplayLength": "1000",
            "mDataProp_0": "0", "mDataProp_1": "1", "mDataProp_2": "2",
            "mDataProp_3": "3", "mDataProp_4": "4", "mDataProp_5": "5",
            "mDataProp_6": "6", "mDataProp_7": "7",
            "sSearch": "", "bRegex": "false",
            "iSortCol_0": "0", "sSortDir_0": "asc", "iSortingCols": "1",
            "_": str(int(time.time() * 1000)),
        }
        resp = session.get(
            f"{LAMIX_URL}/ints/agent/res/data_clients.php",
            params=params, timeout=15,
        )
        if resp.status_code != 200:
            return None, False

        data = resp.json()
        rows = data.get("aaData", [])

        for row in rows:
            row_username = str(row[1]).strip()
            soup_td = BeautifulSoup(str(row[0]), "html.parser")
            inp = soup_td.find("input")
            client_id = inp["value"] if inp else ""
            if row_username.lower() == username.lower():
                return client_id, True

        return None, False

    except Exception as e:
        print(f"Verify Error: {e}")
        return None, False


# ✅ সব নম্বর আনো এবং Range অনুযায়ী গ্রুপ করো
def fetch_ranges():
    session = get_session()
    if not session:
        return []
    try:
        params = {
            "frange": "", "fclient": "", "totnum": "99999",
            "sEcho": "1", "iColumns": "8", "sColumns": ",,,,,,",
            "iDisplayStart": "0", "iDisplayLength": "10000",
            "mDataProp_0": "0", "mDataProp_1": "1", "mDataProp_2": "2",
            "mDataProp_3": "3", "mDataProp_4": "4", "mDataProp_5": "5",
            "mDataProp_6": "6", "mDataProp_7": "7",
            "sSearch": "", "bRegex": "false",
            "iSortCol_0": "0", "sSortDir_0": "asc", "iSortingCols": "1",
            "_": str(int(time.time() * 1000)),
        }
        resp = session.get(
            f"{LAMIX_URL}/ints/agent/res/data_smsnumbers.php",
            params=params, timeout=30,
        )
        if resp.status_code == 403:
            reset_session()
            return fetch_ranges()

        data = resp.json()
        rows = data.get("aaData", [])

        # Range অনুযায়ী গ্রুপ করো
        range_dict = {}
        for row in rows:
            range_name = str(row[0]).strip()
            number     = str(row[2]).strip()
            payterm    = str(row[3]).strip() if len(row) > 3 else "Weekly"
            payout     = str(row[4]).strip() if len(row) > 4 else "0.019"
            client     = str(row[5]).strip() if len(row) > 5 else ""

            # Client খালি = available নম্বর
            soup_client = BeautifulSoup(client, "html.parser")
            client_text = soup_client.get_text(strip=True)
            is_available = client_text in ("", "/", "✏")

            if range_name not in range_dict:
                range_dict[range_name] = {
                    "id": range_name,
                    "name": range_name,
                    "available": 0,
                    "total": 0,
                    "payterm": payterm,
                    "payout": payout,
                    "country_code": get_country_code(range_name),
                    "numbers": [],
                }

            range_dict[range_name]["total"] += 1
            if is_available:
                range_dict[range_name]["available"] += 1
                range_dict[range_name]["numbers"].append(number)

        # শুধু available নম্বর আছে এমন রেঞ্জ রিটার্ন করো
        return [r for r in range_dict.values() if r["available"] > 0]

    except Exception as e:
        print(f"Fetch Ranges Error: {e}")
        return []


# ✅ নম্বর Allocate করো
def allocate_numbers(client_id: str, range_name: str, quantity: int):
    session = get_session()
    if not session:
        return None
    try:
        # সব নম্বর আনো
        params = {
            "frange": range_name, "fclient": "", "totnum": "99999",
            "sEcho": "1", "iColumns": "8", "sColumns": ",,,,,,",
            "iDisplayStart": "0", "iDisplayLength": "10000",
            "mDataProp_0": "0", "mDataProp_1": "1", "mDataProp_2": "2",
            "mDataProp_3": "3", "mDataProp_4": "4", "mDataProp_5": "5",
            "mDataProp_6": "6", "mDataProp_7": "7",
            "sSearch": "", "bRegex": "false",
            "iSortCol_0": "0", "sSortDir_0": "asc", "iSortingCols": "1",
            "_": str(int(time.time() * 1000)),
        }
        resp = session.get(
            f"{LAMIX_URL}/ints/agent/res/data_smsnumbers.php",
            params=params, timeout=30,
        )
        data = resp.json()
        rows = data.get("aaData", [])

        # Available নম্বর বাছাই করো
        available_numbers = []
        number_ids = []

        for row in rows:
            client = str(row[5]).strip() if len(row) > 5 else ""
            soup_client = BeautifulSoup(client, "html.parser")
            client_text = soup_client.get_text(strip=True)
            is_available = client_text in ("", "/", "✏")

            if is_available:
                number = str(row[2]).strip()
                # Number ID বের করো row[0] থেকে
                soup_cb = BeautifulSoup(str(row[0]), "html.parser")
                inp = soup_cb.find("input")
                num_id = inp["value"] if inp else ""
                available_numbers.append(number)
                number_ids.append(num_id)

            if len(available_numbers) >= quantity:
                break

        if len(available_numbers) < quantity:
            return {"status": "failed", "numbers": []}

        # প্রতিটা নম্বর Client কে Assign করো
        assigned = []
        for num_id, number in zip(number_ids[:quantity], available_numbers[:quantity]):
            try:
                assign_resp = session.post(
                    f"{LAMIX_URL}/ints/agent/Numbers",
                    data={
                        "action": "assign",
                        "eid": num_id,
                        "client_id": client_id,
                    },
                    timeout=15,
                )
                if assign_resp.status_code == 200:
                    assigned.append(number)
            except Exception as e:
                print(f"Assign Error [{number}]: {e}")

        if not assigned:
            return {"status": "failed", "numbers": []}

        return {"status": "success", "numbers": assigned}

    except Exception as e:
        print(f"Allocate Error: {e}")
        return None


# ✅ Country Code বের করো
def get_country_code(range_name: str):
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
    name_lower = range_name.lower()
    for country, code in codes.items():
        if country in name_lower:
            return code
    return ""
          
