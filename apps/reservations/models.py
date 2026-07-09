"""apps/reservations/models.py"""
from django.db import models
from django.conf import settings
from django.utils import timezone

from datetime import datetime, timedelta
import uuid


class Reservation(models.Model):
    CAFE_LOCATION_CHOICES = [
        ('ahmedabad', 'Ahmedabad'),
        ('mumbai', 'Mumbai'),
        ('jaipur', 'Jaipur'),
        ('delhi', 'Delhi'),
        ('bengaluru', 'Bengaluru'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('no_show', 'No Show'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='reservations',
        null=True,
        blank=True,
    )
    cafe_location = models.CharField(max_length=20, choices=CAFE_LOCATION_CHOICES, default='ahmedabad')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    date = models.DateField()
    time_slot = models.CharField(max_length=20, default='08:00-09:00')
    time = models.TimeField()
    guests = models.PositiveIntegerField(default=2)
    table_preference = models.CharField(max_length=100, blank=True, help_text='e.g. Window seat, Outdoor')
    special_requests = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    occasion = models.CharField(max_length=100, blank=True, help_text='e.g. Birthday, Anniversary')
    booking_reference = models.CharField(max_length=16, unique=True, blank=True)
    is_large_group_inquiry = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.time_slot and (not self.time or self.time == datetime.min.time()):
            try:
                start_time = self.time_slot.split('-', 1)[0]
                self.time = datetime.strptime(start_time, '%H:%M').time()
            except (ValueError, IndexError):
                pass

        if not self.booking_reference:
            while True:
                ref = f"BBS{uuid.uuid4().hex[:7].upper()}"
                if not Reservation.objects.filter(booking_reference=ref).exists():
                    self.booking_reference = ref
                    break

        super().save(*args, **kwargs)

    @property
    def can_cancel(self):
        if self.status not in ['pending', 'confirmed']:
            return False
        reservation_dt = datetime.combine(self.date, self.time)
        reservation_dt = timezone.make_aware(reservation_dt, timezone.get_current_timezone())
        return timezone.now() <= reservation_dt - timedelta(hours=2)

    def __str__(self):
        return f"{self.booking_reference} - {self.name} - {self.date} at {self.time}"

    class Meta:
        ordering = ['-date', '-time']
