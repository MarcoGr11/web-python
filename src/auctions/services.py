from decimal import Decimal

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .models import Bid, Lot, UserProfile


def place_bid(lot_id, user_id, amount: Decimal) -> dict:
    """Atomically validate and record a bid on a lot.

    Locks the lot row with SELECT ... FOR UPDATE so concurrent bids on the
    same lot are serialized by PostgreSQL. Both AuctionConsumer (WebSocket,
    lab 1) and the REST API (lab 3) call this same function, so there is
    exactly one implementation of the race-condition guard to keep correct.

    Money: the leading bid's amount is "frozen" — deducted from the leader's
    balance. When someone outbids them, it is refunded in the same
    transaction. Profiles are locked after the lot row, so balance checks
    can't race either.
    """
    with transaction.atomic():
        lot = Lot.objects.select_for_update().get(id=lot_id)

        if lot.is_closed or timezone.now() >= lot.ends_at:
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

        previous_leader_id = lot.current_winner_id
        # Lock bidder + previous leader in user_id order: two bids on
        # different lots can lock the same pair of profiles, and a fixed
        # order rules out deadlocks.
        profiles = {
            p.user_id: p
            for p in UserProfile.objects.select_for_update()
            .filter(user_id__in={user_id, previous_leader_id} - {None})
            .order_by("user_id")
        }
        bidder = profiles[user_id]

        # Raising your own leading bid: your frozen amount counts toward it.
        available = bidder.balance
        if previous_leader_id == user_id:
            available += lot.current_highest_bid
        if amount > available:
            return {
                "accepted": False,
                "reason": "insufficient_balance",
                "current_highest_bid": lot.current_highest_bid,
            }

        if previous_leader_id is not None:
            profiles[previous_leader_id].balance += lot.current_highest_bid
        bidder.balance -= amount
        for profile in profiles.values():
            profile.save(update_fields=["balance"])

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


def close_expired_lots() -> int:
    """Close every lot whose ends_at has passed and pay its seller; returns
    how many lots were closed.

    The winner's final bid was already deducted when it became the leading
    bid (place_bid), so closing doesn't charge them again — it only credits
    the same amount to the lot owner. Owners may bid on their own lots; if
    the owner is the winner, they paid X at bid time and get X back here, so
    no money is created or lost.

    Locks the lots first, then all owners' profiles in one user_id-ordered
    query — the same lot-then-profiles order place_bid() uses, so the two
    can't deadlock. A concurrent closer blocks on the lot rows and, once
    they're committed as closed, no longer matches is_closed=False, so a
    seller is never paid twice.
    """
    with transaction.atomic():
        lots = list(
            Lot.objects.select_for_update()
            .filter(is_closed=False, ends_at__lte=timezone.now())
            .order_by("id")
        )
        sold = [lot for lot in lots if lot.current_winner_id is not None]
        sellers = {
            p.user_id: p
            for p in UserProfile.objects.select_for_update()
            .filter(user_id__in={lot.owner_id for lot in sold})
            .order_by("user_id")
        }
        for lot in sold:
            sellers[lot.owner_id].balance += lot.current_highest_bid
        for profile in sellers.values():
            profile.save(update_fields=["balance"])
        Lot.objects.filter(id__in=[lot.id for lot in lots]).update(is_closed=True)
    return len(lots)
