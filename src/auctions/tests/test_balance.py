from datetime import timedelta
from decimal import Decimal

import pytest
from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from auctions import services
from auctions.models import STARTING_BALANCE, Lot
from auctions.routing import websocket_urlpatterns


def make_user(username, balance=STARTING_BALANCE):
    user = User.objects.create_user(username, f"{username}@example.com", "S3curePass!23")
    user.profile.balance = balance
    user.profile.save()
    return user


def balance(user):
    user.profile.refresh_from_db()
    return user.profile.balance


@pytest.fixture
def lot(db):
    return Lot.objects.create(
        title="Relic",
        starting_price=100,
        current_highest_bid=100,
        owner=make_user("seller"),
        ends_at=timezone.now() + timedelta(days=1),
    )


def test_new_user_gets_starting_balance(db):
    assert balance(make_user("newbie")) == STARTING_BALANCE


def test_bid_above_balance_is_rejected(lot):
    poor = make_user("poor", balance=Decimal("150"))
    result = services.place_bid(lot.id, poor.id, Decimal("200"))
    assert result["accepted"] is False
    assert result["reason"] == "insufficient_balance"
    lot.refresh_from_db()
    assert lot.current_highest_bid == 100
    assert lot.current_winner is None
    assert balance(poor) == 150


def test_accepted_bid_freezes_amount(lot):
    bidder = make_user("bidder", balance=Decimal("1000"))
    assert services.place_bid(lot.id, bidder.id, Decimal("300"))["accepted"]
    assert balance(bidder) == 700


def test_outbid_leader_gets_refund(lot):
    first = make_user("first", balance=Decimal("1000"))
    second = make_user("second", balance=Decimal("1000"))
    services.place_bid(lot.id, first.id, Decimal("300"))
    assert services.place_bid(lot.id, second.id, Decimal("400"))["accepted"]
    assert balance(first) == 1000
    assert balance(second) == 600


def test_leader_raising_own_bid_only_pays_the_difference(lot):
    leader = make_user("leader", balance=Decimal("500"))
    services.place_bid(lot.id, leader.id, Decimal("300"))  # 200 left
    # 450 > 200 spendable, but 300 of it is already frozen on this lot.
    assert services.place_bid(lot.id, leader.id, Decimal("450"))["accepted"]
    assert balance(leader) == 50


def test_api_returns_insufficient_balance_reason(lot):
    poor = make_user("poor", balance=Decimal("150"))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=poor).key}")
    resp = client.post(f"/api/lots/{lot.pk}/bid/", {"amount": "200"}, format="json")
    assert resp.status_code == 400
    assert resp.data["reason"] == "insufficient_balance"


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}})
async def test_websocket_returns_insufficient_balance_reason():
    @database_sync_to_async
    def setup():
        poor = make_user("poor", balance=Decimal("150"))
        return poor, Lot.objects.create(
            title="Relic",
            starting_price=100,
            current_highest_bid=100,
            owner=poor,
            ends_at=timezone.now() + timedelta(days=1),
        )

    poor, lot = await setup()
    communicator = WebsocketCommunicator(URLRouter(websocket_urlpatterns), f"/ws/auction/{lot.id}/")
    communicator.scope["user"] = poor
    await communicator.connect()
    await communicator.send_json_to({"amount": "200"})
    response = await communicator.receive_json_from()
    assert response == {
        "type": "bid_rejected",
        "reason": "insufficient_balance",
        "current_highest_bid": "100.00",
    }
    await communicator.disconnect()


def test_balance_shown_in_header_and_dashboard(client, lot):
    bidder = make_user("bidder", balance=Decimal("1000"))
    services.place_bid(lot.id, bidder.id, Decimal("300"))
    client.force_login(bidder)
    html = client.get("/dashboard/user/").content.decode()
    assert "💰 700.00" in html  # header
    assert "Balance: <strong>700.00</strong>" in html
    assert "frozen in leading bids: 300.00" in html
