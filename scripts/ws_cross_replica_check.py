"""Lab 6: end-to-end check through nginx (http://localhost, sandbox seed users).

Form login, lot pages, a REST bid, then a WebSocket bid by pilot1 that pilot2 must
receive while connected to another replica (see WSCONNECT in `docker compose logs web`).

    pip install requests websocket-client && python scripts/ws_cross_replica_check.py
"""

import json
import re
from decimal import Decimal

import requests
import websocket

BASE = "http://localhost"


def browser_login(username):
    s = requests.Session()
    s.get(f"{BASE}/accounts/login/")
    r = s.post(
        f"{BASE}/accounts/login/",
        data={
            "username": username,
            "password": f"{username}pass123",
            "csrfmiddlewaretoken": s.cookies["csrftoken"],
        },
        headers={"Origin": BASE, "Referer": f"{BASE}/accounts/login/"},
    )
    print(f"login {username}: {r.status_code} -> {r.url}  X-Served-By={r.headers['X-Served-By']}")
    assert r.url.endswith("/dashboard/user/")
    return s


a, b = browser_login("pilot1"), browser_login("pilot2")
r = a.get(f"{BASE}/lots/")
ids = re.findall(r'href="/lots/(\d+)/"', r.text)
print(f"GET /lots/: {r.status_code}, {len(set(ids))} lots, X-Served-By={r.headers['X-Served-By']}")

token = requests.post(
    f"{BASE}/api/auth/login/", json={"username": "pilot1", "password": "pilot1pass123"}
).json()["token"]
api = {"Authorization": f"Token {token}"}
lots = requests.get(f"{BASE}/api/lots/", headers=api).json()
lot = next(
    x for x in lots if not x["is_closed"] and x["owner"]["username"] not in ("pilot1", "pilot2")
)
d = a.get(f"{BASE}/lots/{lot['id']}/")
print(f"GET /lots/{lot['id']}/: {d.status_code}, X-Served-By={d.headers['X-Served-By']}")
amount = Decimal(lot["current_highest_bid"]) + 1
r = requests.post(f"{BASE}/api/lots/{lot['id']}/bid/", json={"amount": str(amount)}, headers=api)
print(
    f"REST bid {amount} on lot {lot['id']}: {r.status_code}, X-Served-By={r.headers['X-Served-By']}"
)


def ws(session):
    cookie = "; ".join(f"{k}={v}" for k, v in session.cookies.items())
    return websocket.create_connection(
        f"ws://localhost/ws/auction/{lot['id']}/",
        cookie=cookie,
        header=[f"Origin: {BASE}"],
        timeout=5,
    )


wa, wb = ws(a), ws(b)
print("WebSocket A (pilot1) and B (pilot2) connected")
amount += 1
wa.send(json.dumps({"amount": str(amount)}))
print("A received:", wa.recv())
print("B received:", wb.recv())
wa.close()
wb.close()
