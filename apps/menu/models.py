"""apps/menu/models.py"""
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text='Font Awesome icon class e.g. fa-coffee')
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.parent_id is None:
            return
        if self.parent_id == self.pk:
            raise ValidationError({'parent': 'A category cannot be its own parent.'})

        ancestor = self.parent
        while ancestor is not None:
            if ancestor.pk == self.pk:
                raise ValidationError({'parent': 'Circular category hierarchy is not allowed.'})
            ancestor = ancestor.parent

    def get_descendant_ids(self):
        descendant_ids = set()
        queue = list(self.children.all())
        while queue:
            node = queue.pop(0)
            if node.pk in descendant_ids:
                continue
            descendant_ids.add(node.pk)
            queue.extend(node.children.all())
        return descendant_ids

    @property
    def level(self):
        level = 0
        parent = self.parent
        while parent is not None:
            level += 1
            parent = parent.parent
        return level

    @property
    def full_path(self):
        nodes = [self.name]
        parent = self.parent
        while parent is not None:
            nodes.append(parent.name)
            parent = parent.parent
        return ' > '.join(reversed(nodes))

    @property
    def indented_name(self):
        return f"{'-- ' * self.level}{self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['order', 'name']


class Attribute(models.Model):
    """Reusable attribute definition, e.g. Size, Tea Base, Sugar Level."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or 'attribute'
            slug = base_slug
            counter = 1
            while Attribute.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class CategoryAttribute(models.Model):
    """Assign an existing attribute to a category."""
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='category_attributes')
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE, related_name='category_links', null=True, blank=True)
    is_required = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        attribute_name = self.attribute.name if self.attribute else 'Unassigned Attribute'
        return f"{self.category.full_path} - {attribute_name}"

    class Meta:
        ordering = ['display_order', 'attribute__name']
        unique_together = ['category', 'attribute']


class Product(models.Model):
    SIZE_CHOICES = [
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
        ('XL', 'Extra Large'),
    ]
    TEMPERATURE_CHOICES = [
        ('hot', 'Hot'),
        ('cold', 'Cold'),
        ('both', 'Hot & Cold'),
    ]

    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField()
    short_description = models.CharField(max_length=200, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    discounted_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    is_available = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_vegetarian = models.BooleanField(default=False)
    is_vegan = models.BooleanField(default=False)
    is_bestseller = models.BooleanField(default=False)
    is_new = models.BooleanField(default=False)
    calories = models.PositiveIntegerField(null=True, blank=True)
    prep_time = models.PositiveIntegerField(null=True, blank=True, help_text='Preparation time in minutes')
    temperature = models.CharField(max_length=10, choices=TEMPERATURE_CHOICES, default='both')
    allergens = models.TextField(blank=True, help_text='Comma-separated allergens')
    ingredients = models.TextField(blank=True)
    stock = models.PositiveIntegerField(default=100)
    track_stock = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            # Keep incrementing until we find a unique slug
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def effective_price(self):
        return self.discounted_price if self.discounted_price else self.price

    @property
    def discount_percentage(self):
        if self.discounted_price and self.price > 0:
            return int(((self.price - self.discounted_price) / self.price) * 100)
        return 0

    @property
    def average_rating(self):
        reviews = self.reviews.filter(is_approved=True)
        if reviews.exists():
            return round(reviews.aggregate(models.Avg('rating'))['rating__avg'], 1)
        return 0

    @property
    def review_count(self):
        return self.reviews.filter(is_approved=True).count()

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-is_featured', '-created_at']


class ProductAttribute(models.Model):
    """Extra attributes like size variants, add-ons etc."""
    ATTRIBUTE_TYPES = [
        ('size', 'Size'),
        ('addon', 'Add-on'),
        ('variant', 'Variant'),
        ('extra', 'Extra'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='attributes')
    attribute = models.ForeignKey(
        Attribute,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_values'
    )
    attribute_type = models.CharField(max_length=20, choices=ATTRIBUTE_TYPES, default='variant')
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=200)
    price_modifier = models.DecimalField(max_digits=6, decimal_places=2, default=0,
                                          help_text='Additional price for this option')
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.product.name} - {self.name}: {self.value}"

    class Meta:
        ordering = ['attribute_type', 'name']


class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]

    code = models.CharField(max_length=20, unique=True)
    description = models.CharField(max_length=200, blank=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default='percentage')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    maximum_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    usage_limit = models.PositiveIntegerField(default=100)
    used_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code

    @property
    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        return self.is_active and self.valid_from <= now <= self.valid_until and self.used_count < self.usage_limit

    def calculate_discount(self, order_amount):
        if order_amount < self.minimum_order_amount:
            return 0
        if self.discount_type == 'percentage':
            discount = (order_amount * self.discount_value) / 100
            if self.maximum_discount:
                discount = min(discount, self.maximum_discount)
        else:
            discount = self.discount_value
        return min(discount, order_amount)

    class Meta:
        ordering = ['-created_at']