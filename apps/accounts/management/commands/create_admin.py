"""apps/accounts/management/commands/create_admin.py"""
from django.core.management.base import BaseCommand
from apps.accounts.models import CustomUser
from apps.loyalty.models import LoyaltyAccount


class Command(BaseCommand):
    help = 'Creates default admin and sample user accounts'

    def handle(self, *args, **kwargs):
        # Create Admin (role=2)
        if not CustomUser.objects.filter(username='admin').exists():
            admin = CustomUser.objects.create_superuser(
                username='admin',
                email='admin@brewandbliss.com',
                password='Admin@1234',
                first_name='Admin',
                last_name='User',
                role=CustomUser.ROLE_ADMIN,
            )
            self.stdout.write(self.style.SUCCESS('✅ Admin created: username=admin, password=Admin@1234'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Admin already exists'))

        # Create Sample User (role=1)
        if not CustomUser.objects.filter(username='testuser').exists():
            user = CustomUser.objects.create_user(
                username='testuser',
                email='user@brewandbliss.com',
                password='User@1234',
                first_name='Test',
                last_name='User',
                role=CustomUser.ROLE_USER,
                phone='9876543210',
            )
            LoyaltyAccount.objects.create(user=user)
            self.stdout.write(self.style.SUCCESS('✅ User created: username=testuser, password=User@1234'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  testuser already exists'))
