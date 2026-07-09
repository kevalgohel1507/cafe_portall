from datetime import datetime, timedelta
from urllib.parse import urlencode

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Reservation


SLOT_CAPACITY = 4
CAFE_HOURS = {
    'ahmedabad': (8, 22),
    'mumbai': (8, 23),
    'jaipur': (8, 22),
    'delhi': (8, 23),
    'bengaluru': (8, 22),
}


class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = [
            'cafe_location',
            'date',
            'time_slot',
            'guests',
            'name',
            'email',
            'phone',
            'occasion',
            'special_requests',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'special_requests': forms.Textarea(attrs={'rows': 3}),
            'guests': forms.NumberInput(attrs={'min': 1, 'max': 20}),
            'occasion': forms.Select(
                choices=[
                    ('', 'Select occasion (optional)'),
                    ('Regular visit', 'Regular visit'),
                    ('Birthday', 'Birthday'),
                    ('Anniversary', 'Anniversary'),
                    ('Business', 'Business'),
                    ('Date Night', 'Date Night'),
                ]
            ),
            'time_slot': forms.Select(choices=[]),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cafe_location'].widget = forms.Select(choices=Reservation.CAFE_LOCATION_CHOICES)
        self.fields['time_slot'].required = True


def _build_time_slots(location_code):
    open_hour, close_hour = CAFE_HOURS.get(location_code, (8, 22))
    slots = []
    for hour in range(open_hour, close_hour):
        start = f"{hour:02d}:00"
        end = f"{(hour + 1):02d}:00"
        slots.append(f"{start}-{end}")
    return slots


def _active_reservations_qs(location_code, selected_date):
    return Reservation.objects.filter(
        cafe_location=location_code,
        date=selected_date,
        status__in=['pending', 'confirmed'],
    )


def _slot_availability(location_code, selected_date):
    slots = _build_time_slots(location_code)
    counts = {}
    for row in _active_reservations_qs(location_code, selected_date).values('time_slot'):
        counts[row['time_slot']] = counts.get(row['time_slot'], 0) + 1

    result = []
    for slot in slots:
        booked = counts.get(slot, 0)
        remaining = max(SLOT_CAPACITY - booked, 0)
        result.append({
            'value': slot,
            'label': slot,
            'remaining_tables': remaining,
            'is_available': remaining > 0,
        })
    return result


def _fully_booked_dates(location_code, days_ahead=45):
    today = timezone.localdate()
    blocked = []
    for day_offset in range(days_ahead + 1):
        candidate = today + timedelta(days=day_offset)
        slots = _slot_availability(location_code, candidate)
        if slots and all(not slot['is_available'] for slot in slots):
            blocked.append(candidate.isoformat())
    return blocked


def _reservation_email_message(reservation):
    return (
        f"Hi {reservation.name},\n\n"
        f"Your Brew & Bliss reservation is received.\n"
        f"Booking Reference: {reservation.booking_reference}\n"
        f"Cafe: {reservation.get_cafe_location_display()}\n"
        f"Date: {reservation.date.strftime('%d %b %Y')}\n"
        f"Time Slot: {reservation.time_slot}\n"
        f"Guests: {reservation.guests}\n"
        f"Status: {reservation.get_status_display()}\n\n"
        f"We'll keep your table ready."
    )


def make_reservation(request):
    initial_data = {}
    if request.user.is_authenticated:
        initial_data.update({
            'name': request.user.get_full_name(),
            'email': request.user.email,
            'phone': getattr(request.user, 'phone', ''),
        })

    # Rebook support via query params.
    initial_data.update({
        'cafe_location': request.GET.get('cafe_location', ''),
        'date': request.GET.get('date', ''),
        'time_slot': request.GET.get('time_slot', ''),
        'guests': request.GET.get('guests', ''),
    })

    if request.method == 'POST':
        form = ReservationForm(request.POST)
        posted_location = request.POST.get('cafe_location', 'ahmedabad')
        form.fields['time_slot'].choices = [(slot, slot) for slot in _build_time_slots(posted_location)]
        if form.is_valid():
            selected_date = form.cleaned_data['date']
            selected_location = form.cleaned_data['cafe_location']
            selected_slot = form.cleaned_data['time_slot']
            guests = form.cleaned_data['guests']

            if selected_date < timezone.localdate():
                form.add_error('date', 'Past dates are not allowed.')
            else:
                slot_options = _slot_availability(selected_location, selected_date)
                slot_map = {slot['value']: slot for slot in slot_options}

                is_large_group = guests > 10
                if not is_large_group:
                    slot_data = slot_map.get(selected_slot)
                    if not slot_data or not slot_data['is_available']:
                        form.add_error('time_slot', 'Selected slot is fully booked. Please choose another slot.')

                if not form.errors:
                    reservation = form.save(commit=False)
                    reservation.user = request.user if request.user.is_authenticated else None
                    reservation.is_large_group_inquiry = is_large_group

                    start_text = selected_slot.split('-', 1)[0]
                    reservation.time = datetime.strptime(start_text, '%H:%M').time()

                    if is_large_group:
                        note = 'Large group inquiry: team will contact for custom arrangement.'
                        reservation.special_requests = (
                            f"{reservation.special_requests}\n{note}".strip()
                            if reservation.special_requests else note
                        )

                    reservation.save()

                    send_mail(
                        subject=f"Brew & Bliss Reservation {reservation.booking_reference}",
                        message=_reservation_email_message(reservation),
                        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@brewbliss.local'),
                        recipient_list=[reservation.email],
                        fail_silently=True,
                    )

                    messages.success(request, 'Reservation submitted successfully!')
                    return redirect('reservations:reservation_confirmation', reference=reservation.booking_reference)
    else:
        form = ReservationForm(initial=initial_data)
        initial_location = initial_data.get('cafe_location') or 'ahmedabad'
        form.fields['time_slot'].choices = [(slot, slot) for slot in _build_time_slots(initial_location)]

    default_location = (request.POST.get('cafe_location') if request.method == 'POST' else form.initial.get('cafe_location')) or 'ahmedabad'
    blocked_dates = _fully_booked_dates(default_location)
    return render(request, 'reservations/make_reservation.html', {
        'form': form,
        'blocked_dates': blocked_dates,
        'slot_capacity': SLOT_CAPACITY,
    })


def reservation_availability(request):
    location_code = request.GET.get('cafe_location', 'ahmedabad')
    raw_date = request.GET.get('date', '')

    if location_code not in dict(Reservation.CAFE_LOCATION_CHOICES):
        return JsonResponse({'error': 'Invalid cafe location.'}, status=400)

    blocked_dates = _fully_booked_dates(location_code)

    if not raw_date:
        return JsonResponse({'slots': [], 'blocked_dates': blocked_dates})

    try:
        selected_date = datetime.strptime(raw_date, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format.'}, status=400)

    if selected_date < timezone.localdate():
        return JsonResponse({'slots': [], 'blocked_dates': blocked_dates})

    slots = _slot_availability(location_code, selected_date)
    return JsonResponse({'slots': slots, 'blocked_dates': blocked_dates})


def reservation_confirmation(request, reference):
    reservation = get_object_or_404(Reservation, booking_reference=reference)

    start_dt = datetime.combine(reservation.date, reservation.time)
    end_dt = start_dt + timedelta(hours=1)
    details = f"Guests: {reservation.guests}\\nReference: {reservation.booking_reference}"

    query = urlencode({
        'action': 'TEMPLATE',
        'text': f"Brew & Bliss - {reservation.get_cafe_location_display()} Reservation",
        'dates': f"{start_dt.strftime('%Y%m%dT%H%M%S')}/{end_dt.strftime('%Y%m%dT%H%M%S')}",
        'details': details,
        'location': reservation.get_cafe_location_display(),
    })
    calendar_url = f"https://calendar.google.com/calendar/render?{query}"

    return render(request, 'reservations/confirmation.html', {
        'reservation': reservation,
        'calendar_url': calendar_url,
    })


@login_required
def my_reservations(request):
    all_reservations = Reservation.objects.filter(user=request.user).order_by('date', 'time')

    now = timezone.now()
    upcoming = []
    past = []
    for reservation in all_reservations:
        reservation_dt = timezone.make_aware(
            datetime.combine(reservation.date, reservation.time),
            timezone.get_current_timezone(),
        )
        if reservation_dt >= now and reservation.status in ['pending', 'confirmed']:
            upcoming.append(reservation)
        else:
            past.append(reservation)

    return render(request, 'reservations/my_reservations.html', {
        'upcoming_reservations': upcoming,
        'past_reservations': list(reversed(past)),
    })


@login_required
def cancel_reservation(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk, user=request.user)
    if reservation.can_cancel:
        reservation.status = 'cancelled'
        reservation.save(update_fields=['status'])
        messages.info(request, 'Reservation cancelled successfully.')
    else:
        messages.error(request, 'Cancellation allowed only up to 2 hours before the slot.')
    return redirect('reservations:my_reservations')


@login_required
def rebook_reservation(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk, user=request.user)
    query = urlencode({
        'cafe_location': reservation.cafe_location,
        'date': reservation.date.isoformat(),
        'time_slot': reservation.time_slot,
        'guests': reservation.guests,
    })
    return redirect(f"{redirect('reservations:make_reservation').url}?{query}")
