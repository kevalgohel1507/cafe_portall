"""apps/menu/forms.py"""
from django import forms
from .models import Category, Attribute, Product, ProductAttribute, Coupon, CategoryAttribute


class HierarchicalCategoryChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.indented_name


class CategoryForm(forms.ModelForm):
    parent = HierarchicalCategoryChoiceField(
        queryset=Category.objects.none(),
        required=False,
        empty_label='Root Category (No Parent)'
    )

    class Meta:
        model = Category
        fields = ['name', 'parent', 'description', 'icon', 'image', 'is_active', 'order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'icon': forms.TextInput(attrs={
                'placeholder': 'fa-mug-hot',
                'list': 'category-icons',
            }),
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Category.objects.select_related('parent').order_by('order', 'name')

        if self.instance and self.instance.pk:
            blocked_ids = self.instance.get_descendant_ids()
            blocked_ids.add(self.instance.pk)
            queryset = queryset.exclude(pk__in=blocked_ids)

        self.fields['parent'].queryset = queryset

    def clean_parent(self):
        parent = self.cleaned_data.get('parent')

        if not parent or not (self.instance and self.instance.pk):
            return parent

        if parent.pk == self.instance.pk:
            raise forms.ValidationError('A category cannot be its own parent.')

        if parent.pk in self.instance.get_descendant_ids():
            raise forms.ValidationError('A category cannot be moved under its own descendant.')

        return parent


class ProductForm(forms.ModelForm):
    category = HierarchicalCategoryChoiceField(queryset=Category.objects.none(), required=True)

    class Meta:
        model = Product
        fields = [
            'category', 'name', 'description', 'short_description', 'price',
            'discounted_price', 'image', 'is_available', 'is_featured', 'is_vegetarian',
            'is_vegan', 'is_bestseller', 'is_new', 'calories', 'prep_time',
            'temperature', 'allergens', 'ingredients', 'stock', 'track_stock'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'short_description': forms.Textarea(attrs={'rows': 2}),
            'allergens': forms.Textarea(attrs={'rows': 2}),
            'ingredients': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.select_related('parent').order_by('order', 'name')


class ProductAttributeForm(forms.ModelForm):
    product = forms.ModelChoiceField(queryset=Product.objects.none(), empty_label='Select Product')

    class Meta:
        model = ProductAttribute
        fields = ['product', 'attribute_type', 'name', 'value', 'price_modifier', 'is_default']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Product.objects.select_related('category').order_by('name')
        self.fields['product'].queryset = queryset
        if not queryset.exists():
            self.fields['product'].help_text = 'No products found. Please create a product first.'


class AttributeForm(forms.ModelForm):
    class Meta:
        model = Attribute
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = [
            'code', 'description', 'discount_type', 'discount_value',
            'minimum_order_amount', 'maximum_discount', 'usage_limit',
            'is_active', 'valid_from', 'valid_until'
        ]
        widgets = {
            'valid_from': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'valid_until': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class CategoryAttributeForm(forms.ModelForm):
    category = HierarchicalCategoryChoiceField(queryset=Category.objects.none(), required=True)
    attribute = forms.ModelChoiceField(queryset=Attribute.objects.none(), required=True, empty_label='Select Attribute')

    class Meta:
        model = CategoryAttribute
        fields = ['category', 'attribute', 'is_required', 'display_order']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.select_related('parent').order_by('order', 'name')
        self.fields['attribute'].queryset = Attribute.objects.order_by('name')
