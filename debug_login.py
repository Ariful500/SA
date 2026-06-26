"""
debug_allocate.py — Allocate API টেস্ট
চালানো: python debug_login.py (replace করে)
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
TEST_RANGE     = "Sri Lanka LX 04May"

print("=" * 60)
print("🔍 ALLOCATE DEBUG TOOL")
print("=" * 60)

# ── Login ──────────────────────────────────────────────────
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
})

print("\n📌 STEP 1: Login")
resp = session.get(f"{LAMIX_URL}/ints/login", timeout=15)
soup = BeautifulSoup(resp.text, "html.parser")
m = re.search(r'(\d+)\s*([+\-])\s*(\d+)', soup.get_text(" ", strip=True))
captcha = str(int(m.group(1)) + int(m.group(3))) if m and m.group(2) == '+' else str(int(m.group(1)) - int(m.group(3))) if m else "0"
resp = session.post(f"{LAMIX_URL}/ints/signin",
    data={"username": LAMIX_USERNAME, "password": LAMIX_PASSWORD, "capt": captcha},
    timeout=15, allow_redirects=True)
if "login" in resp.url.lower():
    print("  ❌ Login Failed!")
    exit(1)
print(f"  ✅ Login OK")

session.headers.update({
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": f"{LAMIX_URL}/ints/agent/MySMSNumbers",
})

# ── Fetch ALL numbers (frange="" দিয়ে) ─────────────────────
print(f"\n📌 STEP 2: সব numbers fetch (frange='')")
params = {
    "frange": "", "fclient": "", "totnum": "220",
    "sEcho": "2", "iColumns": "8", "sColumns": "%2C%2C%2C%2C%2C%2C%2C",
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
all_rows = resp.json().get("aaData", [])
print(f"  Total rows: {len(all_rows)}")

# TEST_RANGE এর rows filter
rows = [r for r in all_rows if len(r) > 1 and str(r[1]).strip() == TEST_RANGE]
print(f"  '{TEST_RANGE}' rows: {len(rows)}")

# ── Available খোঁজা ────────────────────────────────────────
print(f"\n📌 STEP 3: Available number খোঁজা")
first_available = None
for i, row in enumerate(rows[:10]):
    if len(row) < 6:
        continue
    inp = BeautifulSoup(str(row[0]), "html.parser").find("input")
    num_id = inp["value"] if inp else ""
    number = str(row[3]).strip()
    client_cell = str(row[5])
    csoup = BeautifulSoup(client_cell, "html.parser")
    has_allocate   = bool(csoup.find("a", id="allocate"))
    has_unallocate = bool(csoup.find("a", id="unallocate"))
    ctext = csoup.get_text(strip=True)

    status = "✅ AVAILABLE" if (has_allocate and not has_unallocate) else "❌ assigned"
    print(f"  [{i}] {number} | id={num_id} | {status} | text='{ctext[:40]}'")

    if has_allocate and not has_unallocate and not first_available:
        first_available = (num_id, number)

if not first_available:
    print("\n❌ কোনো available number নেই!")
    exit(1)

num_id, number = first_available
print(f"\n✅ Test: number={number}, id={num_id}")

# ── Client fetch ────────────────────────────────────────────
print(f"\n📌 STEP 4: Client list")
cp = {"sEcho":"1","iColumns":"8","sColumns":"%2C%2C%2C%2C%2C%2C%2C",
      "iDisplayStart":"0","iDisplayLength":"100","sSearch":"","bRegex":"false",
      "iSortCol_0":"0","sSortDir_0":"asc","iSortingCols":"1","_":str(int(time.time()*1000))}
for i in range(8):
    cp[f"mDataProp_{i}"]=str(i); cp[f"sSearch_{i}"]=""; cp[f"bRegex_{i}"]="false"
    cp[f"bSearchable_{i}"]="true"; cp[f"bSortable_{i}"]="false" if i in(0,7) else "true"
cr = session.get(f"{LAMIX_URL}/ints/agent/res/data_clients.php",
    params=cp, headers={"Referer":f"{LAMIX_URL}/ints/agent/Clients"}, timeout=15)
client_rows = cr.json().get("aaData",[])
test_client_id = ""
for row in client_rows:
    inp = BeautifulSoup(str(row[0]),"html.parser").find("input")
    cid = inp["value"] if inp else "?"
    print(f"  → {row[1]} | id={cid}")
    if not test_client_id:
        test_client_id = cid

# ── Modal GET ───────────────────────────────────────────────
print(f"\n📌 STEP 5: Modal GET")
modal = session.post(f"{LAMIX_URL}/ints/agent/res/allocatesmsnumber.php",
    data={"id": num_id, "frange": "", "fclient": ""},
    headers={"Referer":f"{LAMIX_URL}/ints/agent/MySMSNumbers?fclient=&frange=",
             "X-Requested-With":"XMLHttpRequest","Accept":"*/*",
             "Content-Type":"application/x-www-form-urlencoded; charset=UTF-8"},
    timeout=15)
print(f"  Status: {modal.status_code}")
print(f"  Response (first 300):\n{modal.text[:300]}")

# ── Allocate POST ───────────────────────────────────────────
print(f"\n📌 STEP 6: Allocate POST (client_id={test_client_id})")
alloc = session.post(f"{LAMIX_URL}/ints/agent/res/allocatesmsnumber.php",
    data={"action":"allocate","id":num_id,"client":test_client_id,
          "payterm":"2","payout":"0","frange":"","fclient":""},
    headers={"Referer":f"{LAMIX_URL}/ints/agent/MySMSNumbers?fclient=&frange=",
             "X-Requested-With":"XMLHttpRequest","Accept":"*/*",
             "Content-Type":"application/x-www-form-urlencoded; charset=UTF-8"},
    timeout=15)
print(f"  Status: {alloc.status_code}")
print(f"  Response:\n{alloc.text[:500]}")

print("\n" + "="*60)
print("✅ Debug complete!")
print("="*60)
