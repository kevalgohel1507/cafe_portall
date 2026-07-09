"""apps/orders/models.py"""
from decimal import Decimal

from django.db import models
from django.conf import settings
from apps.menu.models import Product, Coupon


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total(self):
        return sum((item.subtotal for item in self.items.all()), Decimal('0'))

    @property
    def platform_fee(self):
        return (self.total * Decimal('0.05')).quantize(Decimal('0.01')) if self.item_count > 0 else Decimal('0.00')

    @property
    def platform_fee_gst(self):
        return (self.platform_fee * Decimal('0.18')).quantize(Decimal('0.01')) if self.platform_fee > 0 else Decimal('0.00')

    @property
    def payable_total(self):
        return (self.total + self.platform_fee + self.platform_fee_gst).quantize(Decimal('0.01'))

    @property
    def item_count(self):
        return self.items.aggregate(total=models.Sum('quantity'))['total'] or 0

    def __str__(self):
        return f"Cart of {self.user.username}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    special_instructions = models.CharField(max_length=300, blank=True)
    selected_attributes = models.JSONField(default=dict, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    @property
    def subtotal(self):
        base = self.product.effective_price
        addon_price = sum(
            (Decimal(str(value)) for value in self.selected_attributes.get('price_modifiers', {}).values()),
            Decimal('0'),
        ) if self.selected_attributes else Decimal('0')
        return (base + addon_price) * self.quantity

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready for Pickup'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    ORDER_TYPE_CHOICES = [
        ('dine_in', 'Dine In'),
        ('takeaway', 'Takeaway'),
        ('delivery', 'Delivery'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('upi', 'UPI'),
        ('wallet', 'Wallet'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='orders')
    order_number = models.CharField(max_length=20, unique=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, default='dine_in')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')

    # Pricing
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    platform_fee_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    loyalty_points_used = models.PositiveIntegerField(default=0)
    loyalty_points_earned = models.PositiveIntegerField(default=0)

    # Coupon
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)

    # Delivery details
    delivery_address = models.TextField(blank=True)
    table_number = models.PositiveIntegerField(null=True, blank=True)
    special_instructions = models.TextField(blank=True)
    estimated_delivery_time = models.PositiveIntegerField(null=True, blank=True, help_text='Minutes')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.order_number:
            import random, string
            self.order_number = 'BB' + ''.join(random.choices(string.digits, k=8))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.order_number} by {self.user}"

    class Meta:
        ordering = ['-created_at']


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=200)  # snapshot
    product_price = models.DecimalField(max_digits=10, decimal_places=2)  # snapshot
    quantity = models.PositiveIntegerField(default=1)
    special_instructions = models.CharField(max_length=300, blank=True)
    selected_attributes = models.JSONField(default=dict, blank=True)

    @property
    def subtotal(self):
        return self.product_price * self.quantity

    def __str__(self):
        return f"{self.quantity}x {self.product_name}"
