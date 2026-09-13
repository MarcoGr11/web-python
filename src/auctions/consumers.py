import json
from decimal import Decimal, InvalidOperation

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .models import Bid, Lot


class AuctionConsumer(AsyncWebsocketConsumer):
    """
    Handles real-time bidding for a single lot.

    Every bid is validated and persisted inside a database transaction that
    locks the lot row with SELECT ... FOR UPDATE, so concurrent bids on the
    same lot are serialized by PostgreSQL and only a genuinely higher bid can
    ever win, regardless of how many WebSocket workers process requests in
    parallel.
    """

    async def connect(self):
        self.lot_id = self.scope["url_route"]["kwargs"]["lot_id"]
        self.group_name = f"lot_{self.lot_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            payload = json.loads(text_data)
            amount = Decimal(str(payload["amount"]))
        except (json.JSONDecodeError, KeyError, InvalidOperation):
            await self.send(text_data=json.dumps({"type": "error", "reason": "invalid_payload"}))
            return

        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.send(text_data=json.dumps({"type": "error", "reason": "not_authenticated"}))
            return

        result = await self.place_bid(user_id=user.id, amount=amount)

        if result["accepted"]:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "bid_accepted",
                    "amount": str(result["amount"]),
                    "user": result["username"],
                },
            )
        else:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "bid_rejected",
                        "reason": result["reason"],
                        "current_highest_bid": str(result["current_highest_bid"]),
                    }
                )
            )

    @database_sync_to_async
    def place_bid(self, user_id, amount):
        with transaction.atomic():
            lot = Lot.objects.select_for_update().get(id=self.lot_id)

            if timezone.now() >= lot.ends_at:
                return {
                    "accepted": False,
                    "reason": "auction_closed",
                    "current_highest_bid": lot.current_highest_bid,
                }

            if amount <= lot.current_highest_bid:
                return {
                    "accepted": False,
                    "reason": "outbid",
                    "current_highest_bid": lot.current_highest_bid,
                }

            bid = Bid.objects.create(lot=lot, user_id=user_id, amount=amount)
            lot.current_highest_bid = amount
            lot.current_winner_id = user_id
            lot.save(update_fields=["current_highest_bid", "current_winner"])

        cache.set(f"lot:{lot.id}:highest_bid", str(amount), timeout=None)

        return {
            "accepted": True,
            "amount": amount,
            "username": bid.user.username,
        }

    async def bid_accepted(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "bid_accepted",
                    "amount": event["amount"],
                    "user": event["user"],
                }
            )
        )
