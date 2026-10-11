from django.core.management.base import BaseCommand

from auctions.services import close_expired_lots


class Command(BaseCommand):
    help = "Close every lot whose ends_at has passed (run manually or from cron)."

    def handle(self, *args, **options):
        self.stdout.write(f"Closed {close_expired_lots()} expired lot(s).")
