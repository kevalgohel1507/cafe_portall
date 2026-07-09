"""apps/loyalty/models.py"""
from django.db import models
from django.conf import settings


class LoyaltyAccount(models.Model):
    TIER_CHOICES = [
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
        ('platinum', 'Platinum'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='loyalty')
    points = models.PositiveIntegerField(default=0)
    total_points_earned = models.PositiveIntegerField(default=0)
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='bronze')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def update_tier(self):
        if self.total_points_earned >= 5000:
            self.tier = 'platinum'
        elif self.total_points_earned >= 2000:
            self.tier = 'gold'
        elif self.total_points_earned >= 500:
            self.tier = 'silver'
        else:
            self.tier = 'bronze'

    def save(self, *args, **kwargs):
        self.update_tier()
        super().save(*args, **kwargs)

    @property
    def points_to_next_tier(self):
        thresholds = {'bronze': 500, 'silver': 2000, 'gold': 5000, 'platinum': None}
        next_threshold = thresholds.get(self.tier)
        if next_threshold:
            return max(0, next_threshold - self.total_points_earned)
        return 0

    def __str__(self):
        return f"{self.user.username} - {self.tier.title()} ({self.points} pts)"
