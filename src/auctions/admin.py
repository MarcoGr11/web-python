from django.contrib import admin

from .models import Bid, Lot

admin.site.register(Lot)
admin.site.register(Bid)
