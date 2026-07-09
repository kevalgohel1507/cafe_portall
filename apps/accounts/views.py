"""apps/accounts/views.py"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count
from .forms import UserRegistrationForm, CustomLoginForm, UserProfileForm
from .models import CustomUser
from apps.orders.models import Order
from apps.loyalty.models import LoyaltyAccount


def register_view(request):
    if request.user.is_authenticated:
        if request.user.is_admin_user():
            return redirect('admin_panel:dashboard')
        return redirect('menu:menu_list')
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Auto-create loyalty account
            LoyaltyAccount.objects.create(user=user)
            messages.success(request, 'Registration successful. Please login to continue.')
            return redirect('accounts:login')
    else:
        form = UserRegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_admin_user():
            return redirect('admin_panel:dashboard')
        return redirect('menu:menu_list')
    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            # Keep custom role aligned when user is promoted via Django flags.
            if (user.is_staff or user.is_superuser) and user.role != CustomUser.ROLE_ADMIN:
                user.role = CustomUser.ROLE_ADMIN
                user.save(update_fields=['role'])
            login(request, user)
            messages.success(request, f'Welcome back, {user.get_full_name()}! ☕')
            if user.is_admin_user():
                return redirect('admin_panel:dashboard')
            return redirect(request.GET.get('next', 'menu:menu_list'))
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = CustomLoginForm()
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out. See you soon!')
    return redirect('home')


@login_required
def profile_view(request):
    user = request.user
    orders = Order.objects.filter(user=user).order_by('-created_at')[:5]
    try:
        loyalty = LoyaltyAccount.objects.get(user=user)
    except LoyaltyAccount.DoesNotExist:
        loyalty = LoyaltyAccount.objects.create(user=user)

    total_spent = Order.objects.filter(
        user=user, status__in=['delivered', 'completed']
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    context = {
        'orders': orders,
        'loyalty': loyalty,
        'total_spent': total_spent,
        'total_orders': Order.objects.filter(user=user).count(),
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def edit_profile_view(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:profile')
    else:
        form = UserProfileForm(instance=request.user)
    return render(request, 'accounts/edit_profile.html', {'form': form})
