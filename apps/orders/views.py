"""apps/orders/views.py"""
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction

from .models import Cart, CartItem, Order, OrderItem
from apps.menu.models import Product, Coupon, ProductAttribute
from apps.loyalty.models import LoyaltyAccount


PLATFORM_FEE_RATE = Decimal('0.05')
PLATFORM_FEE_GST_RATE = Decimal('0.18')
DELIVERY_FEE = Decimal('40.00')


def _money(value):
    return Decimal(str(value)).quantize(Decimal('0.01'))


def _calculate_totals(subtotal, order_type='dine_in', discount=Decimal('0')):
    subtotal = _money(subtotal)
    discount = _money(discount)
    gst_amount = Decimal('0.00')
    platform_fee = _money(subtotal * PLATFORM_FEE_RATE) if subtotal > 0 else Decimal('0.00')
    platform_fee_tax = _money(platform_fee * PLATFORM_FEE_GST_RATE) if platform_fee > 0 else Decimal('0.00')
    delivery_fee = DELIVERY_FEE if order_type == 'delivery' else Decimal('0.00')
    total = _money(subtotal + platform_fee + platform_fee_tax + delivery_fee - discount)
    if total < 0:
        total = Decimal('0.00')

    return {
        'subtotal': subtotal,
        'gst_amount': gst_amount,
        'platform_fee': platform_fee,
        'platform_fee_tax': platform_fee_tax,
        'delivery_fee': delivery_fee,
        'discount': discount,
        'total': total,
    }


@login_required
def cart_view(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('product').all()
    summary = _calculate_totals(cart.total)
    context = {
        'cart': cart,
        'items': items,
        'summary': summary,
    }
    return render(request, 'orders/cart.html', context)


@login_required
@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_available=True)
    cart, _ = Cart.objects.get_or_create(user=request.user)
    quantity = int(request.POST.get('quantity', 1))
    special_instructions = request.POST.get('special_instructions', '')

    selected_ids = []
    for value in request.POST.getlist('selected_attribute_ids'):
        if value.isdigit():
            selected_ids.append(int(value))

    selected_attributes_payload = {}
    if selected_ids:
        selected_options = list(
            ProductAttribute.objects.filter(product=product, pk__in=selected_ids).order_by('name', 'value', 'id')
        )

        if len(selected_options) != len(set(selected_ids)):
            messages.error(request, 'Some selected customizations are invalid for this product.')
            return redirect('menu:product_detail', slug=product.slug)

        selected_attributes_payload = {
            'options': [
                {
                    'id': option.id,
                    'name': option.name,
                    'value': option.value,
                    'price_modifier': float(option.price_modifier),
                }
                for option in selected_options
            ],
            'price_modifiers': {
                str(option.id): float(option.price_modifier)
                for option in selected_options
                if option.price_modifier is not None and option.price_modifier != 0
            },
            'labels': [
                f"{option.name}: {option.value}"
                for option in selected_options
            ],
        }

    cart_item = cart.items.filter(
        product=product,
        special_instructions=special_instructions,
        selected_attributes=selected_attributes_payload,
    ).first()

    if cart_item:
        cart_item.quantity += quantity
        cart_item.save(update_fields=['quantity'])
    else:
        CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=quantity,
            special_instructions=special_instructions,
            selected_attributes=selected_attributes_payload,
        )

    messages.success(request, f'{product.name} added to cart!')
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'cart_count': cart.item_count})
    return redirect('orders:cart')


@login_required
@require_POST
def update_cart(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    quantity = int(request.POST.get('quantity', 1))
    if quantity <= 0:
        item.delete()
        messages.info(request, 'Item removed from cart.')
    else:
        item.quantity = quantity
        item.save()
    return redirect('orders:cart')


@login_required
@require_POST
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    item.delete()
    messages.info(request, 'Item removed from cart.')
    return redirect('orders:cart')


@login_required
def checkout(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('product').all()
    if not items.exists():
        messages.warning(request, 'Your cart is empty.')
        return redirect('orders:cart')

    try:
        loyalty = LoyaltyAccount.objects.get(user=request.user)
    except LoyaltyAccount.DoesNotExist:
        loyalty = LoyaltyAccount.objects.create(user=request.user)

    # Apply coupon if in session
    coupon = None
    discount = Decimal('0')
    coupon_code = request.session.get('coupon_code', '')
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code=coupon_code)
            if coupon.is_valid:
                discount = Decimal(str(coupon.calculate_discount(cart.total)))
        except Coupon.DoesNotExist:
            pass

    order_type = request.GET.get('order_type', 'dine_in')
    totals = _calculate_totals(cart.total, order_type=order_type, discount=discount)

    context = {
        'cart': cart,
        'items': items,
        'subtotal': totals['subtotal'],
        'tax': totals['gst_amount'],
        'platform_fee': totals['platform_fee'],
        'platform_fee_tax': totals['platform_fee_tax'],
        'delivery_fee': totals['delivery_fee'],
        'discount': totals['discount'],
        'total': totals['total'],
        'order_type': order_type,
        'delivery_fee_amount': DELIVERY_FEE,
        'loyalty': loyalty,
        'coupon': coupon,
    }
    return render(request, 'orders/checkout.html', context)


@login_required
@require_POST
def apply_coupon(request):
    code = request.POST.get('code', '').strip().upper()
    try:
        coupon = Coupon.objects.get(code=code)
        if coupon.is_valid:
            request.session['coupon_code'] = code
            messages.success(request, f'Coupon "{code}" applied successfully!')
        else:
            messages.error(request, 'This coupon is expired or invalid.')
    except Coupon.DoesNotExist:
        messages.error(request, 'Invalid coupon code.')
    return redirect('orders:checkout')


@login_required
@require_POST
def place_order(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('product').all()

    if not items.exists():
        messages.error(request, 'Your cart is empty.')
        return redirect('orders:cart')

    with transaction.atomic():
        order_type = request.POST.get('order_type', 'dine_in')
        payment_method = request.POST.get('payment_method', 'cash')
        delivery_address = request.POST.get('delivery_address', '')
        table_number = request.POST.get('table_number', None)
        special_instructions = request.POST.get('special_instructions', '')
        use_loyalty = request.POST.get('use_loyalty_points') == 'on'

        subtotal = _money(cart.total)

        # Apply coupon
        coupon = None
        discount = Decimal('0')
        coupon_code = request.session.get('coupon_code', '')
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code)
                if coupon.is_valid:
                    discount = Decimal(str(coupon.calculate_discount(subtotal)))
                    coupon.used_count += 1
                    coupon.save()
            except Coupon.DoesNotExist:
                pass

        # Loyalty points
        loyalty_points_used = 0
        loyalty = None
        try:
            loyalty = LoyaltyAccount.objects.get(user=request.user)
            if use_loyalty and loyalty.points >= 100:
                loyalty_points_used = min(loyalty.points, int(subtotal * 10))
                discount += Decimal(loyalty_points_used) / Decimal('10')
                loyalty.points -= loyalty_points_used
        except LoyaltyAccount.DoesNotExist:
            pass

        totals = _calculate_totals(subtotal, order_type=order_type, discount=discount)
        points_earned = int(totals['total'] / Decimal('10'))

        order = Order.objects.create(
            user=request.user,
            order_type=order_type,
            payment_method=payment_method,
            delivery_address=delivery_address,
            table_number=table_number if table_number else None,
            special_instructions=special_instructions,
            subtotal=totals['subtotal'],
            tax_amount=totals['gst_amount'],
            platform_fee=totals['platform_fee'],
            platform_fee_tax=totals['platform_fee_tax'],
            delivery_fee=totals['delivery_fee'],
            discount_amount=totals['discount'],
            total_amount=totals['total'],
            coupon=coupon,
            loyalty_points_used=loyalty_points_used,
            loyalty_points_earned=points_earned,
        )

        for item in items:
            addon_price = sum(
                (Decimal(str(value)) for value in item.selected_attributes.get('price_modifiers', {}).values()),
                Decimal('0'),
            )
            unit_price = item.product.effective_price + addon_price
            OrderItem.objects.create(
                order=order,
                product=item.product,
                product_name=item.product.name,
                product_price=unit_price,
                quantity=item.quantity,
                special_instructions=item.special_instructions,
                selected_attributes=item.selected_attributes,
            )

        # Award loyalty points
        if loyalty:
            loyalty.points += points_earned
            loyalty.total_points_earned += points_earned
            loyalty.save()

        # Clear cart
        cart.items.all().delete()
        request.session.pop('coupon_code', None)

    messages.success(request, f'Order #{order.order_number} placed successfully! ☕')
    return redirect('orders:order_confirmation', pk=order.pk)


@login_required
def order_confirmation(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(request, 'orders/order_confirmation.html', {'order': order})


@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('items').order_by('-created_at')
    return render(request, 'orders/order_history.html', {'orders': orders})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related('items__product'), pk=pk, user=request.user)
    return render(request, 'orders/order_detail.html', {'order': order})
