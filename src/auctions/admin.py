from django.contrib import admin

from . import services
from .models import Bid, Lot, UserProfile


@admin.register(Lot)
class LotAdmin(admin.ModelAdmin):
    # Route admin deletes through the service so frozen bids get refunded.
    def delete_model(self, request, obj):
        services.delete_lot(obj.id)

    def delete_queryset(self, request, queryset):
        for lot_id in queryset.values_list("id", flat=True):
            services.delete_lot(lot_id)


admin.site.register(Bid)
admin.site.register(UserProfile)
