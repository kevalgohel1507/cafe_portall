"""apps/reviews/views.py"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import Review
from apps.menu.models import Product
from apps.orders.models import Order


@login_required
@require_POST
def add_review(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    rating = int(request.POST.get('rating', 5))
    title = request.POST.get('title', '')
    comment = request.POST.get('comment', '')

    # Check if user purchased the product
    verified = Order.objects.filter(
        user=request.user,
        items__product=product,
        status__in=['delivered', 'completed']
    ).exists()

    review, created = Review.objects.get_or_create(
        user=request.user, product=product,
        defaults={
            'rating': rating, 'title': title,
            'comment': comment, 'is_verified_purchase': verified
        }
    )
    if not created:
        review.rating = rating
        review.title = title
        review.comment = comment
        review.save()
        messages.success(request, 'Review updated!')
    else:
        messages.success(request, 'Review submitted! It will appear after approval.')

    return redirect('menu:product_detail', slug=product.slug)


@login_required
def my_reviews(request):
    reviews = Review.objects.filter(user=request.user).select_related('product')
    return render(request, 'reviews/my_reviews.html', {'reviews': reviews})
