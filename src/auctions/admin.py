from django.contrib import admin

from .models import Bid, Lot, UserProfile

admin.site.register(Lot)
admin.site.register(Bid)
admin.site.register(UserProfile)
