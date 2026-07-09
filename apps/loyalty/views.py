"""apps/loyalty/views.py"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import LoyaltyAccount


@login_required
def loyalty_dashboard(request):
    loyalty, _ = LoyaltyAccount.objects.get_or_create(user=request.user)
    tier_benefits = {
        'bronze': ['5% discount on every order', 'Birthday special offer'],
        'silver': ['10% discount', 'Free drink on 5th order', 'Priority seating'],
        'gold': ['15% discount', 'Monthly free dessert', 'Early access to new items'],
        'platinum': ['20% discount', 'Free delivery always', 'Exclusive events access', 'Personal barista service'],
    }
    return render(request, 'loyalty/dashboard.html', {
        'loyalty': loyalty,
        'benefits': tier_benefits.get(loyalty.tier, []),
        'all_benefits': tier_benefits,
    })
