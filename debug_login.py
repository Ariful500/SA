"""
debug_login.py — Lamix Login ধাপে ধাপে চেক করার স্ক্রিপ্ট
চালানো: python debug_login.py
"""
import re
import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

LAMIX_URL      = os.getenv("LAMIX_URL", "http://51.210.208.26")
LAMIX_USERNAME = os.getenv("LAMIX_USERNAME", "")
LAMIX_PASSWORD = os.getenv("LAMIX_PASSWORD", "")

print("=" * 50)
print("🔍 LAMIX LOGIN DEBUG TOOL")
print("=" * 50)


# ══════════════════════════════════════════════
#  STEP 1: Config চেক
# ══════════════════════════════════════════════
print("\n📌 STEP 1: Config চেক")
print(f"  LAMIX_URL      = {LAMIX_URL}")
print(f"  LAMIX_USERNAME = {LAMIX_USERNAME if LAMIX_USERNAME else '❌ খালি!'}")
print(f"  LAMIX_PASSWORD = {'*' * len(LAMIX_PASSWORD) if LAMIX_PASSWORD else '❌ খালি!'}")

if not LAMIX_URL:
    print("  ❌ LAMIX_URL সেট নেই! .env চেক করুন।")
    exit(1)
if not LAMIX_USERNAME:
    print("  ❌ LAMIX_USERNAME সেট নেই!")
    exit(1)
if not LAMIX_PASSWORD:
    print("  ❌ LAMIX_PASSWORD সেট নেই!")
    exit(1)
print("  ✅ Config OK")


# ══════════════════════════════════════════════
#  STEP 2: Server Reachable চেক
# ══════════════════════════════════════════════
print("\n📌 STEP 2: Server চেক")
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

try:
    r = session.get(LAMIX_URL, timeout=10)
    print(f"  ✅ Server alive! Status: {r.status_code}, URL: {r.url}")
except Exception as e:
    print(f"  ❌ Server reach করা যাচ্ছে না: {e}")
    exit(1)


# ══════════════════════════════════════════════
#  STEP 3: Login Page GET
# ══════════════════════════════════════════════
print("\n📌 STEP 3: Login Page GET")
login_url = f"{LAMIX_URL}/ints/login"
try:
    resp = session.get(login_url, timeout=15)
    print(f"  Status  : {resp.status_code}")
    print(f"  Final URL: {resp.url}")
    if resp.status_code != 200:
        print(f"  ❌ Login page load হয়নি!")
        exit(1)
    print("  ✅ Login page OK")
except Exception as e:
    print(f"  ❌ Exception: {e}")
    exit(1)


# ══════════════════════════════════════════════
#  STEP 4: Captcha Solve
# ══════════════════════════════════════════════
print("\n📌 STEP 4: Captcha Solve")
soup = BeautifulSoup(resp.text, "html.parser")
page_text = soup.get_text(" ", strip=True)

# Math captcha খোঁজা
m = re.search(r'(\d+)\s*([+\-])\s*(\d+)', page_text)
if m:
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    captcha = str(a + b if op == '+' else a - b)
    print(f"  ✅ Captcha found: {a} {op} {b} = {captcha}")
else:
    captcha = "0"
    print(f"  ⚠️ Captcha পাওয়া যায়নি! '0' দিয়ে চেষ্টা করব।")
    print(f"  Page text (first 200 chars): {page_text[:200]}")

# Form fields চেক
print(f"\n  Form inputs found:")
for inp in soup.find_all("input"):
    name = inp.get("name", "")
    itype = inp.get("type", "text")
    val = inp.get("value", "")
    if name:
        print(f"    name='{name}' type='{itype}' value='{val}'")


# ══════════════════════════════════════════════
#  STEP 5: POST Login
# ══════════════════════════════════════════════
print("\n📌 STEP 5: POST Login")
post_data = {
    "username": LAMIX_USERNAME,
    "password": LAMIX_PASSWORD,
    "capt": captcha,
}
print(f"  POST URL : {LAMIX_URL}/ints/signin")
print(f"  POST data: username={LAMIX_USERNAME}, capt={captcha}, password=***")

try:
    resp2 = session.post(
        f"{LAMIX_URL}/ints/signin",
        data=post_data,
        timeout=15,
        allow_redirects=True,
    )
    print(f"  Status   : {resp2.status_code}")
    print(f"  Final URL: {resp2.url}")

    if "login" in resp2.url.lower():
        print("  ❌ Login FAILED! এখনো login page এ আছে।")
        print(f"\n  Response HTML (first 500 chars):\n{resp2.text[:500]}")

        # Error message খোঁজা
        err_soup = BeautifulSoup(resp2.text, "html.parser")
        for tag in err_soup.find_all(["div", "p", "span"], class_=re.compile(r"error|alert|danger|warning", re.I)):
            print(f"  🔴 Error message: {tag.get_text(strip=True)}")
    else:
        print("  ✅ Login SUCCESS!")
        print(f"\n  🎉 Landed on: {resp2.url}")

except Exception as e:
    print(f"  ❌ Exception: {e}")
    exit(1)


# ══════════════════════════════════════════════
#  STEP 6: Session / API চেক (login সফল হলে)
# ══════════════════════════════════════════════
if "login" not in resp2.url.lower():
    print("\n📌 STEP 6: API Session চেক")
    session.headers.update({
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{LAMIX_URL}/ints/agent/SMSDashboard",
        "Origin": LAMIX_URL,
        "Accept": "application/json, text/javascript, */*; q=0.01",
    })
    try:
        import time
        params = {"sEcho": "1", "iDisplayStart": "0", "iDisplayLength": "10", "_": str(int(time.time() * 1000))}
        r3 = session.get(
            f"{LAMIX_URL}/ints/agent/res/data_clients.php",
            params=params,
            headers={"Referer": f"{LAMIX_URL}/ints/agent/Clients"},
            timeout=15,
        )
        print(f"  Clients API status: {r3.status_code}")
        if r3.status_code == 200:
            try:
                data = r3.json()
                count = len(data.get("aaData", []))
                print(f"  ✅ API OK! Clients found: {count}")
            except:
                print(f"  ⚠️ JSON parse error. Response: {r3.text[:200]}")
        else:
            print(f"  ❌ API failed. Response: {r3.text[:200]}")
    except Exception as e:
        print(f"  ❌ API Exception: {e}")

print("\n" + "=" * 50)
print("✅ Debug complete!")
print("=" * 50)
  
