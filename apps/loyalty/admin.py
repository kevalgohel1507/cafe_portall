from django.contrib import admin
from .models import LoyaltyAccount

@admin.register(LoyaltyAccount)
class LoyaltyAccountAdmin(admin.ModelAdmin):
    list_display = ['user', 'tier', 'points', 'total_points_earned']
    list_filter = ['tier']
