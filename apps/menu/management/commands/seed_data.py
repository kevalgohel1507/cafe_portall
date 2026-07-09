"""apps/menu/management/commands/seed_data.py"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.menu.models import Category, Product, Coupon


class Command(BaseCommand):
    help = 'Seeds the database with sample cafe data'

    def handle(self, *args, **kwargs):
        # Categories
        categories_data = [
            {'name': 'Hot Coffee', 'icon': 'fa-coffee', 'order': 1, 'description': 'Freshly brewed hot coffees'},
            {'name': 'Cold Coffee', 'icon': 'fa-glass-martini', 'order': 2, 'description': 'Chilled coffee beverages'},
            {'name': 'Teas', 'icon': 'fa-leaf', 'order': 3, 'description': 'Premium teas and infusions'},
            {'name': 'Smoothies', 'icon': 'fa-blender', 'order': 4, 'description': 'Fresh fruit smoothies'},
            {'name': 'Pastries', 'icon': 'fa-birthday-cake', 'order': 5, 'description': 'Freshly baked pastries'},
            {'name': 'Sandwiches', 'icon': 'fa-hamburger', 'order': 6, 'description': 'Artisan sandwiches'},
            {'name': 'Desserts', 'icon': 'fa-ice-cream', 'order': 7, 'description': 'Decadent desserts'},
        ]
        categories = {}
        for cat_data in categories_data:
            cat, created = Category.objects.get_or_create(name=cat_data['name'], defaults=cat_data)
            categories[cat_data['name']] = cat
            if created:
                self.stdout.write(f"  ✅ Category: {cat.name}")

        # Products
        products_data = [
            # Hot Coffee
            {'category': 'Hot Coffee', 'name': 'Classic Espresso', 'price': 120, 'description': 'Rich, bold shot of premium espresso', 'is_featured': True, 'is_bestseller': True, 'calories': 5, 'prep_time': 3, 'is_vegetarian': True, 'temperature': 'hot'},
            {'category': 'Hot Coffee', 'name': 'Cappuccino', 'price': 180, 'description': 'Espresso with steamed milk and velvety foam', 'is_featured': True, 'calories': 120, 'prep_time': 5, 'is_vegetarian': True, 'temperature': 'hot'},
            {'category': 'Hot Coffee', 'name': 'Flat White', 'price': 200, 'description': 'Double ristretto with silky microfoam milk', 'calories': 130, 'prep_time': 5, 'is_vegetarian': True, 'temperature': 'hot'},
            {'category': 'Hot Coffee', 'name': 'Caramel Latte', 'price': 220, 'description': 'Espresso with caramel and steamed milk', 'is_featured': True, 'discounted_price': 199, 'calories': 250, 'prep_time': 6, 'is_vegetarian': True, 'temperature': 'hot'},
            {'category': 'Hot Coffee', 'name': 'Mocha', 'price': 230, 'description': 'Rich espresso with chocolate and steamed milk', 'calories': 280, 'prep_time': 6, 'is_vegetarian': True, 'temperature': 'hot'},
            # Cold Coffee
            {'category': 'Cold Coffee', 'name': 'Cold Brew', 'price': 220, 'description': '18-hour slow-steeped cold brew concentrate', 'is_featured': True, 'is_bestseller': True, 'calories': 15, 'prep_time': 2, 'is_vegetarian': True, 'temperature': 'cold'},
            {'category': 'Cold Coffee', 'name': 'Iced Caramel Macchiato', 'price': 260, 'description': 'Vanilla, milk, ice, espresso, caramel drizzle', 'calories': 300, 'prep_time': 4, 'is_vegetarian': True, 'temperature': 'cold'},
            {'category': 'Cold Coffee', 'name': 'Frappuccino', 'price': 280, 'discounted_price': 249, 'description': 'Blended coffee with cream and ice', 'is_new': True, 'calories': 380, 'prep_time': 5, 'is_vegetarian': True, 'temperature': 'cold'},
            # Teas
            {'category': 'Teas', 'name': 'Masala Chai', 'price': 80, 'description': 'Traditional Indian spiced tea', 'is_bestseller': True, 'calories': 90, 'prep_time': 5, 'is_vegetarian': True, 'temperature': 'hot'},
            {'category': 'Teas', 'name': 'Matcha Latte', 'price': 240, 'description': 'Premium ceremonial grade matcha with oat milk', 'is_featured': True, 'is_new': True, 'calories': 150, 'prep_time': 4, 'is_vegan': True, 'is_vegetarian': True, 'temperature': 'both'},
            {'category': 'Teas', 'name': 'Earl Grey', 'price': 120, 'description': 'Classic bergamot-infused black tea', 'calories': 5, 'prep_time': 4, 'is_vegetarian': True, 'temperature': 'hot'},
            # Pastries
            {'category': 'Pastries', 'name': 'Butter Croissant', 'price': 120, 'description': 'Flaky, buttery French croissant', 'is_bestseller': True, 'calories': 320, 'prep_time': 2, 'is_vegetarian': True},
            {'category': 'Pastries', 'name': 'Blueberry Muffin', 'price': 130, 'description': 'Bursting with fresh blueberries', 'is_featured': True, 'calories': 380, 'prep_time': 2, 'is_vegetarian': True},
            {'category': 'Pastries', 'name': 'Cinnamon Roll', 'price': 160, 'description': 'Warm, gooey cinnamon swirl with cream cheese icing', 'is_new': True, 'calories': 420, 'prep_time': 3, 'is_vegetarian': True},
            # Sandwiches
            {'category': 'Sandwiches', 'name': 'Club Sandwich', 'price': 280, 'description': 'Triple-decker with chicken, bacon, egg and veggies', 'is_featured': True, 'calories': 580, 'prep_time': 10},
            {'category': 'Sandwiches', 'name': 'Avocado Toast', 'price': 240, 'description': 'Smashed avocado on sourdough with poached egg', 'is_new': True, 'calories': 420, 'prep_time': 8, 'is_vegetarian': True},
            # Desserts
            {'category': 'Desserts', 'name': 'Tiramisu', 'price': 220, 'description': 'Classic Italian coffee dessert', 'is_featured': True, 'is_bestseller': True, 'calories': 450, 'prep_time': 5, 'is_vegetarian': True},
            {'category': 'Desserts', 'name': 'Cheesecake', 'price': 240, 'discounted_price': 210, 'description': 'New York-style baked cheesecake', 'calories': 480, 'prep_time': 3, 'is_vegetarian': True},
        ]

        for p_data in products_data:
            cat_name = p_data.pop('category')
            p_data['category'] = categories[cat_name]
            p_data.setdefault('is_vegetarian', False)
            p_data.setdefault('is_vegan', False)
            p_data.setdefault('is_featured', False)
            p_data.setdefault('is_bestseller', False)
            p_data.setdefault('is_new', False)
            p_data.setdefault('temperature', 'both')
            discounted_price = p_data.pop('discounted_price', None)

            prod, created = Product.objects.get_or_create(
                name=p_data['name'],
                defaults={**p_data, 'discounted_price': discounted_price, 'short_description': p_data['description'][:100]}
            )
            if created:
                self.stdout.write(f"  ✅ Product: {prod.name}")

        # Coupons
        now = timezone.now()
        coupons = [
            {
                'code': 'WELCOME10', 'description': '10% off for new customers',
                'discount_type': 'percentage', 'discount_value': 10,
                'minimum_order_amount': 200, 'usage_limit': 500,
                'valid_from': now, 'valid_until': now + timedelta(days=365),
            },
            {
                'code': 'FLAT50', 'description': 'Flat ₹50 off on orders above ₹300',
                'discount_type': 'fixed', 'discount_value': 50,
                'minimum_order_amount': 300, 'usage_limit': 200,
                'valid_from': now, 'valid_until': now + timedelta(days=90),
            },
        ]
        for c_data in coupons:
            coupon, created = Coupon.objects.get_or_create(code=c_data['code'], defaults=c_data)
            if created:
                self.stdout.write(f"  ✅ Coupon: {coupon.code}")

        self.stdout.write(self.style.SUCCESS('\n🎉 Sample data seeded successfully!'))
