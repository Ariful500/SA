"""
debug_allocate.py — Allocate API টেস্ট করার স্ক্রিপ্ট
চালানো: python debug_allocate.py
"""
import re
import os
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

LAMIX_URL      = os.getenv("LAMIX_URL", "http://51.210.208.26")
LAMIX_USERNAME = os.getenv("LAMIX_USERNAME", "")
LAMIX_PASSWORD = os.getenv("LAMIX_PASSWORD", "")
TEST_RANGE     = "Sri Lanka LX 04May"  # টেস্ট করার range

print("=" * 60)
print("🔍 ALLOCATE DEBUG TOOL")
print("=" * 60)

# ── Login ──────────────────────────────────────────────────
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
})

print("\n📌 STEP 1: Login")
resp = session.get(f"{LAMIX_URL}/ints/login", timeout=15)
soup = BeautifulSoup(resp.text, "html.parser")
text = soup.get_text(" ", strip=True)
m = re.search(r'(\d+)\s*([+\-])\s*(\d+)', text)
captcha = str(int(m.group(1)) + int(m.group(3))) if m and m.group(2) == '+' else str(int(m.group(1)) - int(m.group(3))) if m else "0"
print(f"  Captcha: {captcha}")

resp = session.post(f"{LAMIX_URL}/ints/signin",
    data={"username": LAMIX_USERNAME, "password": LAMIX_PASSWORD, "capt": captcha},
    timeout=15, allow_redirects=True)

if "login" in resp.url.lower():
    print("  ❌ Login Failed!")
    exit(1)
print(f"  ✅ Login OK → {resp.url}")

session.headers.update({
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": f"{LAMIX_URL}/ints/agent/MySMSNumbers",
})

# ── Fetch Numbers ──────────────────────────────────────────
print(f"\n📌 STEP 2: '{TEST_RANGE}' এর numbers fetch")
params = {
    "frange": TEST_RANGE, "fclient": "", "totnum": "220",
    "sEcho": "1", "iColumns": "8", "sColumns": "%2C%2C%2C%2C%2C%2C%2C",
    "iDisplayStart": "0", "iDisplayLength": "10000",
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

resp = session.get(f"{LAMIX_URL}/ints/agent/res/data_smsnumbers.php", params=params, timeout=30)
print(f"  Status: {resp.status_code}")
rows = resp.json().get("aaData", [])
print(f"  Total rows: {len(rows)}")

# ── Find first available ───────────────────────────────────
print(f"\n📌 STEP 3: Available number খোঁজা")
first_available = None
for i, row in enumerate(rows[:10]):  # প্রথম ১০টা দেখি
    if len(row) < 6:
        continue
    inp = BeautifulSoup(str(row[0]), "html.parser").find("input")
    num_id = inp["value"] if inp else ""
    number = str(row[3]).strip()
    client_cell = str(row[5])
    client_soup = BeautifulSoup(client_cell, "html.parser")
    has_allocate   = bool(client_soup.find("a", id="allocate"))
    has_unallocate = bool(client_soup.find("a", id="unallocate"))
    client_text = client_soup.get_text(strip=True)
    
    print(f"  Row {i}: number={number}, id={num_id}")
    print(f"    has_allocate={has_allocate}, has_unallocate={has_unallocate}, text='{client_text[:50]}'")
    
    if has_allocate and not has_unallocate and not first_available:
        first_available = (num_id, number)
        print(f"    ✅ AVAILABLE!")
    elif has_unallocate:
        print(f"    ❌ Already assigned")

if not first_available:
    print("\n❌ কোনো available number পাওয়া যায়নি!")
    exit(1)

num_id, number = first_available
print(f"\n✅ Test করব: number={number}, id={num_id}")

# ── Fetch Clients ──────────────────────────────────────────
print(f"\n📌 STEP 4: Client list fetch")
c_params = {
    "sEcho": "1", "iColumns": "8", "sColumns": "%2C%2C%2C%2C%2C%2C%2C",
    "iDisplayStart": "0", "iDisplayLength": "100",
    "sSearch": "", "bRegex": "false",
    "iSortCol_0": "0", "sSortDir_0": "asc", "iSortingCols": "1",
    "_": str(int(time.time() * 1000)),
}
for i in range(8):
    c_params[f"mDataProp_{i}"] = str(i)
    c_params[f"sSearch_{i}"] = ""
    c_params[f"bRegex_{i}"] = "false"
    c_params[f"bSearchable_{i}"] = "true"
    c_params[f"bSortable_{i}"] = "false" if i in (0, 7) else "true"

cr = session.get(f"{LAMIX_URL}/ints/agent/res/data_clients.php",
    params=c_params, headers={"Referer": f"{LAMIX_URL}/ints/agent/Clients"}, timeout=15)
client_rows = cr.json().get("aaData", [])
print(f"  Clients found: {len(client_rows)}")
for row in client_rows:
    inp = BeautifulSoup(str(row[0]), "html.parser").find("input")
    cid = inp["value"] if inp else "?"
    print(f"  → username={row[1]}, client_id={cid}")

# ── Modal GET ──────────────────────────────────────────────
print(f"\n📌 STEP 5: Modal GET (form load)")
modal = session.post(
    f"{LAMIX_URL}/ints/agent/res/allocatesmsnumber.php",
    data={"id": num_id, "frange": "", "fclient": ""},
    headers={
        "Referer": f"{LAMIX_URL}/ints/agent/MySMSNumbers?fclient=&frange=",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    },
    timeout=15,
)
print(f"  Status: {modal.status_code}")
print(f"  Response:\n{modal.text[:800]}")

# ── Allocate POST ──────────────────────────────────────────
# প্রথম client দিয়ে test করব
if client_rows:
    inp = BeautifulSoup(str(client_rows[0][0]), "html.parser").find("input")
    test_client_id = inp["value"] if inp else ""
    test_client_name = str(client_rows[0][1])
    print(f"\n📌 STEP 6: Allocate POST (client: {test_client_name}, id: {test_client_id})")
    
    alloc = session.post(
        f"{LAMIX_URL}/ints/agent/res/allocatesmsnumber.php",
        data={
            "action":  "allocate",
            "id":      num_id,
            "client":  test_client_id,
            "payterm": "2",
            "payout":  "0",
            "frange":  "",
            "fclient": "",
        },
        headers={
            "Referer": f"{LAMIX_URL}/ints/agent/MySMSNumbers?fclient=&frange=",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
        timeout=15,
    )
    print(f"  Status: {alloc.status_code}")
    print(f"  Response:\n{alloc.text[:500]}")
else:
    print("\n❌ কোনো client নেই!")

print("\n" + "=" * 60)
print("✅ Debug complete!")
print("=" * 60)
