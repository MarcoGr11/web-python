from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone


@pytest.fixture
def user(db):
    return User.objects.create_user("alice", "alice@example.com", "S3curePass!23")


def test_lot_create_requires_login(client):
    resp = client.get(reverse("lot_create"))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_lot_create_sets_owner_and_initial_bid(client, user):
    client.force_login(user)
    ends_at = (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    resp = client.post(
        reverse("lot_create"),
        {
            "title": "Star Fragment",
            "description": "A shard of a dying star.",
            "starting_price": "42.50",
            "ends_at": ends_at,
        },
    )
    assert resp.status_code == 302
    from auctions.models import Lot

    lot = Lot.objects.get(title="Star Fragment")
    assert lot.owner_id == user.id
    assert lot.current_highest_bid == 42.5
