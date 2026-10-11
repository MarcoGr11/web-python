"""Typical-user load scenario for the sandbox environment (lab 4).

Each virtual user logs in once as one of the seed users, then browses:
home page, lot list, lot details. HTTP only — Locust doesn't drive the
WebSocket bidding channel.

    locust -f locust/locustfile.py --host http://127.0.0.1:8000 \
        --users 50 --spawn-rate 5 --run-time 5m --headless --csv=locust/results/run1
"""

import random
import re

from locust import HttpUser, between, task

# Regular users created by `python manage.py seed` (sandbox only).
SEED_USERS = [
    ("pilot1", "pilot1pass123"),
    ("pilot2", "pilot2pass123"),
    ("starcommander", "starcommanderpass123"),
    ("voidtrader", "voidtraderpass123"),
]


class AuctionVisitor(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        username, password = random.choice(SEED_USERS)
        self.client.get("/accounts/login/", name="/accounts/login/ [GET]")
        with self.client.post(
            "/accounts/login/",
            data={
                "username": username,
                "password": password,
                "csrfmiddlewaretoken": self.client.cookies["csrftoken"],
            },
            name="/accounts/login/ [POST]",
            catch_response=True,
        ) as response:
            # Success redirects to the dashboard; otherwise every later
            # @login_required page would silently 302 back to the login form.
            if not response.url.endswith("/dashboard/user/"):
                response.failure(f"login as {username} failed")
        # Lot ids come from the real list page, so only existing lots are hit.
        lots_page = self.client.get("/lots/").text
        self.lot_ids = sorted(set(re.findall(r'href="/lots/(\d+)/"', lots_page)))

    @task(2)
    def home(self):
        self.client.get("/")

    @task(3)
    def lot_list(self):
        self.client.get("/lots/")

    @task(4)
    def lot_details(self):
        for lot_id in random.sample(self.lot_ids, min(3, len(self.lot_ids))):
            self.client.get(f"/lots/{lot_id}/", name="/lots/<id>/")

    @task(1)
    def dashboard(self):
        self.client.get("/dashboard/user/")
