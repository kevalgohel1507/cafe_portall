from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


def _backfill_booking_refs(apps, schema_editor):
    Reservation = apps.get_model('reservations', 'Reservation')
    used = set(Reservation.objects.exclude(booking_reference='').values_list('booking_reference', flat=True))

    for row in Reservation.objects.all():
        changed = False
        if not row.booking_reference:
            while True:
                ref = f"BBS{uuid.uuid4().hex[:7].upper()}"
                if ref not in used:
                    used.add(ref)
                    row.booking_reference = ref
                    changed = True
                    break

        if not row.time_slot and row.time:
            hour = row.time.hour
            row.time_slot = f"{hour:02d}:00-{(hour + 1):02d}:00"
            changed = True

        if changed:
            row.save(update_fields=['booking_reference', 'time_slot'])


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='reservation',
            name='booking_reference',
            field=models.CharField(blank=True, default='', max_length=16),
        ),
        migrations.AddField(
            model_name='reservation',
            name='cafe_location',
            field=models.CharField(
                choices=[
                    ('ahmedabad', 'Ahmedabad'),
                    ('mumbai', 'Mumbai'),
                    ('jaipur', 'Jaipur'),
                    ('delhi', 'Delhi'),
                    ('bengaluru', 'Bengaluru'),
                ],
                default='ahmedabad',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='reservation',
            name='is_large_group_inquiry',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='reservation',
            name='time_slot',
            field=models.CharField(default='08:00-09:00', max_length=20),
        ),
        migrations.AlterField(
            model_name='reservation',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('confirmed', 'Confirmed'),
                    ('cancelled', 'Cancelled'),
                    ('completed', 'Completed'),
                    ('no_show', 'No Show'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='reservation',
            name='user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reservations',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(_backfill_booking_refs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='reservation',
            name='booking_reference',
            field=models.CharField(blank=True, max_length=16, unique=True),
        ),
    ]
