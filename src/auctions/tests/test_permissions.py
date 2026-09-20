from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from auctions.models import Lot


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


def test_anonymous_access_to_dashboard_redirects_to_login(client):
    resp = client.get(reverse("dashboard_user"))
    assert resp.status_code == 302
    assert reverse("login") in resp.url


def test_home_page_returns_200(client, db):
    """The landing page is a public showcase — no login required."""
    resp = client.get(reverse("home"))
    assert resp.status_code == 200


def test_regular_user_cannot_access_admin_dashboard(client, user):
    client.force_login(user)
    resp = client.get(reverse("dashboard_admin"))
    assert resp.status_code == 403


def test_admin_can_access_admin_dashboard(client, admin_user):
    client.force_login(admin_user)
    resp = client.get(reverse("dashboard_admin"))
    assert resp.status_code == 200


def test_user_cannot_edit_someone_elses_lot(client, other_user, lot):
    """IDOR check: user B must not be able to open user A's lot edit form."""
    client.force_login(other_user)
    resp = client.get(reverse("lot_edit", args=[lot.pk]))
    assert resp.status_code == 403


def test_owner_can_edit_their_own_lot(client, user, lot):
    client.force_login(user)
    resp = client.get(reverse("lot_edit", args=[lot.pk]))
    assert resp.status_code == 200


def test_admin_can_edit_any_lot(client, admin_user, lot):
    client.force_login(admin_user)
    resp = client.get(reverse("lot_edit", args=[lot.pk]))
    assert resp.status_code == 200
