import socket

# No db fixture: pytest-django raises on any query, so passing proves the endpoint is DB-free.


def test_whoami_is_public_and_db_free(client):
    response = client.get("/api/whoami/")
    assert response.status_code == 200
    assert response.json() == {"hostname": socket.gethostname()}
    assert response["X-Served-By"] == socket.gethostname()


def test_every_response_has_served_by_header(client):
    response = client.get("/accounts/login/")
    assert response["X-Served-By"] == socket.gethostname()
