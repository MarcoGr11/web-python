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
    assert '<span id="header-balance">700.00</span>' in html  # header
    assert "Balance: <strong>700.00</strong>" in html
    assert "frozen in leading bids: 300.00" in html


def expire(lot):
    Lot.objects.filter(pk=lot.pk).update(ends_at=timezone.now() - timedelta(minutes=1))


def test_closing_pays_the_seller_exactly_once(lot):
    winner = make_user("winner", balance=Decimal("1000"))
    services.place_bid(lot.id, winner.id, Decimal("300"))
    expire(lot)
    assert services.close_expired_lots() == 1
    assert services.close_expired_lots() == 0
    assert balance(lot.owner) == STARTING_BALANCE + 300
    assert balance(winner) == 700  # charged once, at bid time


def test_closing_lot_without_bids_pays_nobody(lot):
    expire(lot)
    services.close_expired_lots()
    assert balance(lot.owner) == STARTING_BALANCE


def test_owner_winning_own_lot_nets_to_zero(lot):
    services.place_bid(lot.id, lot.owner_id, Decimal("300"))
    assert balance(lot.owner) == STARTING_BALANCE - 300
    expire(lot)
    services.close_expired_lots()
    assert balance(lot.owner) == STARTING_BALANCE


def test_one_seller_paid_for_several_lots(lot):
    second = Lot.objects.create(
        title="Second",
        starting_price=50,
        current_highest_bid=50,
        owner=lot.owner,
        ends_at=lot.ends_at,
    )
    buyer = make_user("buyer")
    services.place_bid(lot.id, buyer.id, Decimal("300"))
    services.place_bid(second.id, buyer.id, Decimal("200"))
    expire(lot)
    expire(second)
    assert services.close_expired_lots() == 2
    assert balance(lot.owner) == STARTING_BALANCE + 500


def api_client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}")
    return client


def test_deleting_lot_with_leading_bid_refunds_leader(lot):
    leader = make_user("leader", balance=Decimal("1000"))
    services.place_bid(lot.id, leader.id, Decimal("300"))
    resp = api_client_for(lot.owner).delete(f"/api/lots/{lot.pk}/")
    assert resp.status_code == 204
    assert not Lot.objects.filter(pk=lot.pk).exists()
    assert balance(leader) == 1000


def test_deleting_lot_without_bids_changes_no_balances(lot):
    bystander = make_user("bystander")
    resp = api_client_for(lot.owner).delete(f"/api/lots/{lot.pk}/")
    assert resp.status_code == 204
    assert balance(lot.owner) == STARTING_BALANCE
    assert balance(bystander) == STARTING_BALANCE


def test_non_owner_cannot_delete_lot(lot):
    leader = make_user("leader", balance=Decimal("1000"))
    services.place_bid(lot.id, leader.id, Decimal("300"))
    resp = api_client_for(make_user("mallory")).delete(f"/api/lots/{lot.pk}/")
    assert resp.status_code == 403
    assert Lot.objects.filter(pk=lot.pk).exists()
    assert balance(leader) == 700  # still frozen on the lot


def test_closed_lot_cannot_be_deleted_by_owner(lot):
    winner = make_user("winner")
    services.place_bid(lot.id, winner.id, Decimal("300"))
    expire(lot)
    services.close_expired_lots()
    resp = api_client_for(lot.owner).delete(f"/api/lots/{lot.pk}/")
    assert resp.status_code == 400
    assert Lot.objects.filter(pk=lot.pk, current_winner=winner).exists()


def test_admin_site_delete_refunds_leader(client, lot):
    leader = make_user("leader", balance=Decimal("1000"))
    services.place_bid(lot.id, leader.id, Decimal("300"))
    client.force_login(User.objects.create_superuser("root", "root@example.com", "x"))
    resp = client.post(f"/admin/auctions/lot/{lot.pk}/delete/", {"post": "yes"})
    assert resp.status_code == 302
    assert not Lot.objects.filter(pk=lot.pk).exists()
    assert balance(leader) == 1000


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}})
async def test_websocket_sends_each_user_only_their_own_new_balance():
    @database_sync_to_async
    def setup():
        seller = make_user("seller")
        first = make_user("first", balance=Decimal("1000"))
        second = make_user("second", balance=Decimal("1000"))
        lot = Lot.objects.create(
            title="Relic",
            starting_price=100,
            current_highest_bid=100,
            owner=seller,
            ends_at=timezone.now() + timedelta(days=1),
        )
        services.place_bid(lot.id, first.id, Decimal("300"))  # first: 700 left
        return seller, first, second, lot

    seller, first, second, lot = await setup()
    sockets = {}
    for user in (seller, first, second):
        communicator = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns), f"/ws/auction/{lot.id}/"
        )
        communicator.scope["user"] = user
        await communicator.connect()
        sockets[user.username] = communicator

    await sockets["second"].send_json_to({"amount": "400"})
    received = {name: await ws.receive_json_from() for name, ws in sockets.items()}
    for ws in sockets.values():
        await ws.disconnect()

    assert received["second"]["new_balance"] == "600.00"  # bidder: charged
    assert received["first"]["new_balance"] == "1000.00"  # outbid: refunded
    assert "new_balance" not in received["seller"]  # bystander: nothing leaked
    assert received["seller"]["user"] == "second"
