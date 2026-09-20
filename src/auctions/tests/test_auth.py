import pytest
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.mark.django_db
def test_register_creates_user_and_logs_them_in(client):
    resp = client.post(
        reverse("register"),
        {
            "username": "newuser",
            "email": "newuser@example.com",
            "password1": "S3curePass!23",
            "password2": "S3curePass!23",
        },
    )
    assert resp.status_code == 302
    assert User.objects.filter(username="newuser").exists()


@pytest.mark.django_db
def test_register_duplicate_username_is_rejected(client):
    User.objects.create_user("dupe", "dupe@example.com", "S3curePass!23")
    resp = client.post(
        reverse("register"),
        {
            "username": "dupe",
            "email": "other@example.com",
            "password1": "S3curePass!23",
            "password2": "S3curePass!23",
        },
    )
    assert resp.status_code == 200
    assert User.objects.filter(username="dupe").count() == 1


@pytest.mark.django_db
def test_login_with_correct_credentials_succeeds(client):
    User.objects.create_user("bob", "bob@example.com", "S3curePass!23")
    resp = client.post(reverse("login"), {"username": "bob", "password": "S3curePass!23"})
    assert resp.status_code == 302
    resp2 = client.get(reverse("dashboard_user"))
    assert resp2.status_code == 200


@pytest.mark.django_db
def test_login_with_wrong_password_is_rejected(client):
    User.objects.create_user("bob", "bob@example.com", "S3curePass!23")
    resp = client.post(reverse("login"), {"username": "bob", "password": "wrong-password"})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_logout_ends_the_session(client):
    user = User.objects.create_user("bob", "bob@example.com", "S3curePass!23")
    client.force_login(user)
    resp = client.post(reverse("logout"))
    assert resp.status_code == 302
    resp2 = client.get(reverse("dashboard_user"))
    assert resp2.status_code == 302
