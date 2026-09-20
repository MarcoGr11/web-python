from datetime import timedelta

import pytest
from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone

from auctions.models import Lot
from auctions.routing import websocket_urlpatterns

application = URLRouter(websocket_urlpatterns)

IN_MEMORY_CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


@database_sync_to_async
def make_lot(username):
    owner = User.objects.create_user(username, f"{username}@example.com", "S3curePass!23")
    return owner, Lot.objects.create(
        title="Relic",
        starting_price=10,
        current_highest_bid=10,
        owner=owner,
        ends_at=timezone.now() + timedelta(days=1),
    )


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=IN_MEMORY_CHANNEL_LAYERS)
async def test_authenticated_user_bid_is_accepted():
    owner, lot = await make_lot("owner1")

    communicator = WebsocketCommunicator(application, f"/ws/auction/{lot.id}/")
    communicator.scope["user"] = owner
    connected, _ = await communicator.connect()
    assert connected

    await communicator.send_json_to({"amount": "50"})
    response = await communicator.receive_json_from()
    assert response == {"type": "bid_accepted", "amount": "50", "user": "owner1"}

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=IN_MEMORY_CHANNEL_LAYERS)
async def test_anonymous_bid_is_rejected():
    _, lot = await make_lot("owner2")

    communicator = WebsocketCommunicator(application, f"/ws/auction/{lot.id}/")
    connected, _ = await communicator.connect()
    assert connected

    await communicator.send_json_to({"amount": "50"})
    response = await communicator.receive_json_from()
    assert response == {"type": "error", "reason": "not_authenticated"}

    await communicator.disconnect()
