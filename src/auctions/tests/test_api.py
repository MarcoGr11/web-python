from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from auctions.models import Lot


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user("alice", "alice@example.com", "S3curePass!23")


@pytest.fixture
def other_user(db):
    return User.objects.create_user("mallory", "mallory@example.com", "S3curePass!23")


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser("root", "root@example.com", "S3curePass!23")


@pytest.fixture
def lot(user):
    return Lot.objects.create(
        title="Ancient Relic",
        starting_price=10,
        current_highest_bid=10,
        owner=user,
        ends_at=timezone.now() + timedelta(days=1),
    )


def authenticate(api_client, user):
    token, _ = Token.objects.get_or_create(user=user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")


def test_anonymous_get_lots_returns_401(api_client, db):
    resp = api_client.get("/api/lots/")
    assert resp.status_code == 401


def test_login_with_correct_credentials_returns_token(api_client, user):
    resp = api_client.post("/api/auth/login/", {"username": "alice", "password": "S3curePass!23"})
    assert resp.status_code == 200
    assert "token" in resp.data


def test_login_with_wrong_password_is_rejected(api_client, user):
    resp = api_client.post("/api/auth/login/", {"username": "alice", "password": "wrong-password"})
    assert resp.status_code == 400


def test_regular_user_cannot_access_admin_dashboard(api_client, user):
    authenticate(api_client, user)
    resp = api_client.get("/api/dashboard/admin/")
    assert resp.status_code == 403


def test_admin_can_access_admin_dashboard(api_client, admin_user):
    authenticate(api_client, admin_user)
    resp = api_client.get("/api/dashboard/admin/")
    assert resp.status_code == 200


def test_user_cannot_patch_someone_elses_lot(api_client, other_user, lot):
    """IDOR check: user B must not be able to PATCH user A's lot."""
    authenticate(api_client, other_user)
    resp = api_client.patch(f"/api/lots/{lot.pk}/", {"title": "Hijacked"}, format="json")
    assert resp.status_code == 403


def test_owner_can_patch_their_own_lot(api_client, user, lot):
    authenticate(api_client, user)
    resp = api_client.patch(f"/api/lots/{lot.pk}/", {"title": "Updated title"}, format="json")
    assert resp.status_code == 200


def test_register_creates_user_and_returns_token(api_client, db):
    resp = api_client.post(
        "/api/auth/register/",
        {"username": "newuser", "email": "newuser@example.com", "password": "S3curePass!23"},
    )
    assert resp.status_code == 201
    assert "token" in resp.data
    assert User.objects.filter(username="newuser").exists()


def test_lot_create_sets_owner_via_api(api_client, user):
    authenticate(api_client, user)
    resp = api_client.post(
        "/api/lots/",
        {
            "title": "Star Fragment",
            "description": "A shard of a dying star.",
            "starting_price": "42.50",
            "ends_at": (timezone.now() + timedelta(days=1)).isoformat(),
        },
        format="json",
    )
    assert resp.status_code == 201
    created = Lot.objects.get(title="Star Fragment")
    assert created.owner_id == user.id
    assert created.current_highest_bid == created.starting_price


def test_bid_action_uses_shared_service(api_client, other_user, lot):
    """The API's bid action must go through services.place_bid(), same as the WebSocket consumer."""
    authenticate(api_client, other_user)
    resp = api_client.post(f"/api/lots/{lot.pk}/bid/", {"amount": "999"}, format="json")
    assert resp.status_code == 201
    assert resp.data == {
        "accepted": True,
        "amount": "999",
        "user": "mallory",
        "new_balance": "9001.00",
    }
    lot.refresh_from_db()
    assert lot.current_highest_bid == 999
