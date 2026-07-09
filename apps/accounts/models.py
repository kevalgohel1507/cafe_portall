"""apps/accounts/models.py"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_USER = 1
    ROLE_ADMIN = 2
    ROLE_CHOICES = [
        (ROLE_USER, 'User'),
        (ROLE_ADMIN, 'Admin'),
    ]

    role = models.IntegerField(choices=ROLE_CHOICES, default=ROLE_USER)
    phone = models.CharField(max_length=15, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    address = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_admin_user(self):
        return self.role == self.ROLE_ADMIN or self.is_staff or self.is_superuser

    def is_regular_user(self):
        return self.role == self.ROLE_USER

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username

    def __str__(self):
        return f"{self.username} ({'Admin' if self.is_admin_user() else 'User'})"

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
