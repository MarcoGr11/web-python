from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from auctions.models import Lot

ADMIN = {"username": "admin", "password": "adminpass123"}

REGULAR_USERS = [
    {"username": "pilot1", "password": "pilot1pass123"},
    {"username": "pilot2", "password": "pilot2pass123"},
    {"username": "starcommander", "password": "starcommanderpass123"},
    {"username": "voidtrader", "password": "voidtraderpass123"},
]

LOTS = [
    {
        "title": "Кристал Кайбер",
        "description": "Рідкісний кристал, що резонує з енергією Сили. Джерело живлення для клинків.",
        "starting_price": 500,
        "current_highest_bid": 750,
        "owner": "pilot1",
        "ends_in_days": 3,
    },
    {
        "title": "Уламок мертвої зорі",
        "description": "Фрагмент ядра зорі, що згасла тисячоліття тому. Випромінює слабке тепло.",
        "starting_price": 1200,
        "current_highest_bid": 1200,
        "owner": "pilot2",
        "ends_in_days": 5,
    },
    {
        "title": "Голографічна карта Зовнішнього рукава",
        "description": "Застаріла, але надзвичайно детальна голокарта маловідомих торгових шляхів.",
        "starting_price": 300,
        "current_highest_bid": 420,
        "owner": "starcommander",
        "ends_in_days": 1,
    },
    {
        "title": "Двигун викривлення класу III",
        "description": "Списаний, але робочий гіпердвигун з крейсера довгої дії. Потребує калібрування.",
        "starting_price": 2000,
        "current_highest_bid": 2500,
        "owner": "voidtrader",
        "ends_in_days": 7,
    },
    {
        "title": "Броня давнього вартового",
        "description": "Церемоніальна броня невідомого ордену. Метал не піддається сучасному аналізу.",
        "starting_price": 800,
        "current_highest_bid": 800,
        "owner": "pilot1",
        "ends_in_days": 2,
    },
    {
        "title": "Флакон зоряного пилу",
        "description": "Пил, зібраний із хвоста комети на межі відомого космосу. Світиться у темряві.",
        "starting_price": 150,
        "current_highest_bid": 310,
        "owner": "pilot2",
        "ends_in_days": -1,
    },
    {
        "title": "Дроїд-архіваріус (несправний)",
        "description": "Старовинний дроїд з пошкодженою пам'яттю. Може містити втрачені записи Республіки.",
        "starting_price": 600,
        "current_highest_bid": 950,
        "owner": "starcommander",
        "ends_in_days": -3,
    },
    {
        "title": "Осколок астероїда-привида",
        "description": "Уламок астероїда, що періодично зникає з радарів. Науковці не можуть пояснити ефект.",
        "starting_price": 400,
        "current_highest_bid": 400,
        "owner": "voidtrader",
        "ends_in_days": 4,
    },
]


class Command(BaseCommand):
    help = "Seed the database with a demo admin, regular users, and themed auction lots."

    def handle(self, *args, **options):
        created_credentials = []

        admin_user, created = User.objects.get_or_create(
            username=ADMIN["username"],
            defaults={"is_staff": True, "is_superuser": True},
        )
        if created:
            admin_user.set_password(ADMIN["password"])
            admin_user.save()
        created_credentials.append((ADMIN["username"], ADMIN["password"], "admin"))

        users_by_username = {}
        for spec in REGULAR_USERS:
            user, created = User.objects.get_or_create(username=spec["username"])
            if created:
                user.set_password(spec["password"])
                user.save()
            users_by_username[spec["username"]] = user
            created_credentials.append((spec["username"], spec["password"], "user"))

        for spec in LOTS:
            Lot.objects.get_or_create(
                title=spec["title"],
                defaults={
                    "description": spec["description"],
                    "starting_price": spec["starting_price"],
                    "current_highest_bid": spec["current_highest_bid"],
                    "owner": users_by_username[spec["owner"]],
                    "ends_at": timezone.now() + timedelta(days=spec["ends_in_days"]),
                },
            )

        self.stdout.write(self.style.SUCCESS("Seed complete. Login credentials:"))
        for username, password, role in created_credentials:
            self.stdout.write(f"  {username} / {password}  ({role})")
        self.stdout.write(f"Lots in database: {Lot.objects.count()}")
