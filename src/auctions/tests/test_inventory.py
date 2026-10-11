from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from auctions import services
from auctions.models import Lot


def make_user(username):
    return User.objects.create_user(username, f"{username}@example.com", "S3curePass!23")


@pytest.fixture
def won_lot(db):
    """A lot `winner` leads on, whose ends_at has just passed (not closed yet)."""
    winner, loser = make_user("winner"), make_user("loser")
    lot = Lot.objects.create(
        title="Kyber Crystal",
        starting_price=100,
        current_highest_bid=100,
        owner=make_user("seller"),
        ends_at=timezone.now() + timedelta(days=1),
    )
    services.place_bid(lot.id, loser.id, Decimal("200"))
    services.place_bid(lot.id, winner.id, Decimal("300"))
    Lot.objects.filter(pk=lot.pk).update(ends_at=timezone.now() - timedelta(minutes=1))
    return lot, winner, loser


def test_viewing_expired_lot_closes_it_and_shows_winner(client, won_lot):
    lot, winner, loser = won_lot
    client.force_login(loser)
    html = client.get(f"/lots/{lot.pk}/").content.decode()
    lot.refresh_from_db()
    assert lot.is_closed
    assert lot.current_winner == winner
    assert "Переможець: <strong>winner</strong>" in html
    assert 'id="bid-form"' not in html


def test_winner_sees_you_won(client, won_lot):
    lot, winner, _ = won_lot
    client.force_login(winner)
    assert "Ви виграли!" in client.get(f"/lots/{lot.pk}/").content.decode()


def test_won_lot_appears_only_in_winners_inventory(client, won_lot):
    lot, winner, loser = won_lot
    client.force_login(winner)
    resp = client.get("/inventory/")
    assert list(resp.context["lots"]) == [lot]
    assert "Kyber Crystal" in resp.content.decode()
    client.force_login(loser)
    assert list(client.get("/inventory/").context["lots"]) == []


def test_api_inventory(won_lot):
    lot, winner, _ = won_lot
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=winner).key}")
    resp = client.get("/api/inventory/")
    assert resp.status_code == 200
    assert [item["id"] for item in resp.data] == [lot.pk]
    assert resp.data[0]["is_closed"] is True


def test_closing_does_not_charge_the_winner_twice(won_lot):
    _, winner, loser = won_lot
    call_command("close_expired_auctions")
    call_command("close_expired_auctions")
    winner.profile.refresh_from_db()
    loser.profile.refresh_from_db()
    assert winner.profile.balance == Decimal("9700.00")  # charged once, at bid time
    assert loser.profile.balance == Decimal("10000.00")  # refunded when outbid


def test_closed_lot_rejects_bids(won_lot):
    lot, _, loser = won_lot
    services.close_expired_lots()
    result = services.place_bid(lot.id, loser.id, Decimal("500"))
    assert result["reason"] == "auction_closed"


def test_lot_list_marks_closed_lots(client, won_lot):
    lot, winner, _ = won_lot
    client.force_login(winner)
    html = client.get("/lots/").content.decode()
    assert "<s>Kyber Crystal</s>" in html
    assert "Closed" in html


def test_seed_creates_closed_won_lots_idempotently(db):
    call_command("seed")
    call_command("seed")
    pilot1 = User.objects.get(username="pilot1")
    won = Lot.objects.filter(current_winner=pilot1, is_closed=True)
    assert [lot.title for lot in won] == ["Флакон зоряного пилу"]
    pilot1.profile.refresh_from_db()
    assert pilot1.profile.balance == Decimal("10000.00") - won[0].current_highest_bid
    assert User.objects.get(username="admin").profile.balance == Decimal("10000.00")
