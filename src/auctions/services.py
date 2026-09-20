from decimal import Decimal

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .models import Bid, Lot


def place_bid(lot_id, user_id, amount: Decimal) -> dict:
    """Atomically validate and record a bid on a lot.

    Locks the lot row with SELECT ... FOR UPDATE so concurrent bids on the
    same lot are serialized by PostgreSQL. Both AuctionConsumer (WebSocket,
    lab 1) and the REST API (lab 3) call this same function, so there is
    exactly one implementation of the race-condition guard to keep correct.
    """
    with transaction.atomic():
        lot = Lot.objects.select_for_update().get(id=lot_id)

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
        "bid_id": bid.id,
    }
