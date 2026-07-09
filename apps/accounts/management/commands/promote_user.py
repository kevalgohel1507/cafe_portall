"""apps/accounts/management/commands/promote_user.py"""
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import CustomUser


class Command(BaseCommand):
    help = "Promote a registered user to admin role."

    def add_arguments(self, parser):
        parser.add_argument("username", type=str, help="Username to promote")

    def handle(self, *args, **options):
        username = options["username"]

        try:
            user = CustomUser.objects.get(username=username)
        except CustomUser.DoesNotExist as exc:
            raise CommandError(f"User '{username}' does not exist.") from exc

        user.role = CustomUser.ROLE_ADMIN
        user.is_staff = True
        user.save(update_fields=["role", "is_staff"])

        self.stdout.write(self.style.SUCCESS(f"User '{username}' promoted to Admin successfully."))
