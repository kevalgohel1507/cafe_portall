"""apps/accounts/admin_views.py"""
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Avg, Q, Max
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
from functools import wraps

from .models import CustomUser
from .forms import AdminUserCreateForm, AdminUserEditForm
from apps.menu.models import Category, Attribute, CategoryAttribute, Product, ProductAttribute, Coupon
from apps.menu.forms import (
    CategoryForm,
    AttributeForm,
    CategoryAttributeForm,
    ProductForm,
    ProductAttributeForm,
    CouponForm,
)
from apps.orders.models import Order
from apps.reviews.models import Review
from apps.reservations.models import Reservation


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_admin_user():
            messages.error(request, 'Access denied. Admin privileges required.')
            return redirect('menu:menu_list')
        return view_func(request, *args, **kwargs)
    return wrapper


def _flatten_category_tree(categories):
    by_parent = {}
    for category in categories:
        by_parent.setdefault(category.parent_id, []).append(category)

    flattened = []

    def walk(parent_id, level):
        for node in by_parent.get(parent_id, []):
            node.tree_level = level
            flattened.append(node)
            walk(node.id, level + 1)

    walk(None, 0)
    return flattened


def _extract_mapped_attribute_values(post_data, category):
    mappings = list(
        CategoryAttribute.objects.filter(category=category, attribute__isnull=False)
        .select_related('attribute')
        .order_by('display_order', 'attribute__name')
    )

    values = {}
    missing_required = []
    mapping_by_attribute_id = {}

    for mapping in mappings:
        attribute_id = mapping.attribute_id
        option_key = f"mapped_attr_option_{attribute_id}[]"
        price_key = f"mapped_attr_price_{attribute_id}[]"
        combined_key = f"mapped_attr_{attribute_id}"

        option_list = post_data.getlist(option_key)
        price_list = post_data.getlist(price_key)

        tokens = []
        for index, raw_option in enumerate(option_list):
            option = (raw_option or '').strip()
            if not option:
                continue
            raw_price = (price_list[index] if index < len(price_list) else '').strip()
            tokens.append(f"{option}:{raw_price}" if raw_price else option)

        value = ', '.join(tokens)
        if not value:
            # Backward-compatible fallback for older single-input payloads.
            value = (post_data.get(combined_key) or '').strip()

        values[attribute_id] = value
        mapping_by_attribute_id[mapping.attribute_id] = mapping
        if mapping.is_required and not value:
            missing_required.append(mapping.attribute.name)

    return values, missing_required, mapping_by_attribute_id


def _parse_mapping_options(raw_value):
    """
    Parse comma-separated attribute options.
    Supports formats: "ginger", "ginger:20", "ginger=20".
    """
    options = []
    for chunk in (raw_value or '').split(','):
        piece = chunk.strip()
        if not piece:
            continue

        label = piece
        price_modifier = Decimal('0')
        if ':' in piece:
            label, price_part = piece.rsplit(':', 1)
            label = label.strip()
            price_part = price_part.strip()
        elif '=' in piece:
            label, price_part = piece.rsplit('=', 1)
            label = label.strip()
            price_part = price_part.strip()
        else:
            price_part = ''

        if price_part:
            try:
                price_modifier = Decimal(price_part)
            except (InvalidOperation, ValueError):
                price_modifier = Decimal('0')

        if label:
            options.append((label, price_modifier))

    return options


def _sync_product_mapped_attributes(product, values, mapping_by_attribute_id):
    managed_ids = set(mapping_by_attribute_id.keys())

    # Remove mapped values that no longer belong to this category.
    ProductAttribute.objects.filter(
        product=product,
        attribute__isnull=False,
    ).exclude(attribute_id__in=managed_ids).delete()

    # Rebuild mapped options from posted values to keep product options in sync.
    ProductAttribute.objects.filter(product=product, attribute_id__in=managed_ids).delete()

    to_create = []
    for attribute_id, mapping in mapping_by_attribute_id.items():
        options = _parse_mapping_options(values.get(attribute_id, ''))
        for index, (option_label, price_modifier) in enumerate(options):
            to_create.append(ProductAttribute(
                product=product,
                attribute_id=attribute_id,
                attribute_type='addon',
                name=mapping.attribute.name,
                value=option_label,
                price_modifier=price_modifier,
                is_default=(index == 0),
            ))

    if to_create:
        ProductAttribute.objects.bulk_create(to_create)


def _collect_posted_mapped_values(post_data):
    values = {}

    grouped = {}
    for key in post_data.keys():
        if not key.startswith('mapped_attr_option_') or not key.endswith('[]'):
            continue
        attribute_id = key[len('mapped_attr_option_'):-2]
        if not attribute_id.isdigit():
            continue

        option_list = post_data.getlist(key)
        price_list = post_data.getlist(f'mapped_attr_price_{attribute_id}[]')
        tokens = []
        for index, raw_option in enumerate(option_list):
            option = (raw_option or '').strip()
            if not option:
                continue
            raw_price = (price_list[index] if index < len(price_list) else '').strip()
            tokens.append(f"{option}:{raw_price}" if raw_price else option)
        grouped[int(attribute_id)] = ', '.join(tokens)

    values.update(grouped)

    for key, value in post_data.items():
        if not key.startswith('mapped_attr_'):
            continue
        attribute_id = key.replace('mapped_attr_', '', 1)
        if attribute_id.endswith('[]'):
            continue
        if attribute_id.isdigit() and int(attribute_id) not in values:
            values[int(attribute_id)] = value
    return values


def _extract_customization_rows(post_data):
    names = post_data.getlist('customization_name[]')
    prices = post_data.getlist('customization_price[]')

    rows = []
    for index, raw_name in enumerate(names):
        name = (raw_name or '').strip()
        if not name:
            continue

        raw_price = (prices[index] if index < len(prices) else '').strip()
        if raw_price:
            try:
                price = Decimal(raw_price)
            except (InvalidOperation, ValueError):
                price = Decimal('0')
        else:
            price = Decimal('0')

        if price < 0:
            price = Decimal('0')

        rows.append({
            'label': name,
            'price_modifier': price,
        })

    return rows


def _sync_product_customizations(product, customization_rows):
    ProductAttribute.objects.filter(
        product=product,
        attribute__isnull=True,
        attribute_type='addon',
        name='Customization',
    ).delete()

    if not customization_rows:
        return

    ProductAttribute.objects.bulk_create([
        ProductAttribute(
            product=product,
            attribute_type='addon',
            name='Customization',
            value=row['label'],
            price_modifier=row['price_modifier'],
            is_default=(index == 0),
        )
        for index, row in enumerate(customization_rows)
    ])


def _effective_base_price(cleaned_data):
    discounted_price = cleaned_data.get('discounted_price')
    price = cleaned_data.get('price') or Decimal('0')
    return discounted_price if discounted_price is not None else price


def _extract_variant_rows(post_data, base_price):
    labels = post_data.getlist('variant_name[]')
    prices = post_data.getlist('variant_price[]')

    rows = []
    for index, raw_label in enumerate(labels):
        label = (raw_label or '').strip()
        if not label:
            continue

        raw_price = (prices[index] if index < len(prices) else '').strip()
        try:
            final_price = Decimal(raw_price) if raw_price else base_price
        except (InvalidOperation, ValueError):
            final_price = base_price

        if final_price < 0:
            final_price = Decimal('0')

        rows.append({
            'label': label,
            'final_price': final_price,
            'price_modifier': final_price - base_price,
        })

    return rows


def _sync_product_variants(product, variant_rows):
    ProductAttribute.objects.filter(
        product=product,
        attribute__isnull=True,
        attribute_type='size',
        name='Size',
    ).delete()

    if not variant_rows:
        return

    ProductAttribute.objects.bulk_create([
        ProductAttribute(
            product=product,
            attribute_type='size',
            name='Size',
            value=row['label'],
            price_modifier=row['price_modifier'],
            is_default=(index == 0),
        )
        for index, row in enumerate(variant_rows)
    ])


@admin_required
def dashboard(request):
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    stats = {
        'total_users': CustomUser.objects.filter(role=CustomUser.ROLE_USER).count(),
        'total_products': Product.objects.filter(is_available=True).count(),
        'total_orders': Order.objects.count(),
        'pending_orders': Order.objects.filter(status='pending').count(),
        'today_orders': Order.objects.filter(created_at__date=today).count(),
        'today_revenue': Order.objects.filter(
            created_at__date=today, status__in=['delivered', 'completed']
        ).aggregate(total=Sum('total_amount'))['total'] or 0,
        'monthly_revenue': Order.objects.filter(
            created_at__date__gte=month_ago, status__in=['delivered', 'completed']
        ).aggregate(total=Sum('total_amount'))['total'] or 0,
        'weekly_revenue': Order.objects.filter(
            created_at__date__gte=week_ago, status__in=['delivered', 'completed']
        ).aggregate(total=Sum('total_amount'))['total'] or 0,
        'pending_reservations': Reservation.objects.filter(status='pending').count(),
        'low_stock_products': Product.objects.filter(stock__lt=10, track_stock=True).count(),
        'total_reviews': Review.objects.filter(is_approved=False).count(),
    }

    recent_orders = Order.objects.select_related('user').order_by('-created_at')[:8]
    top_products = Product.objects.annotate(
        order_count=Count('orderitem')
    ).order_by('-order_count')[:5]

    # Revenue chart data (last 7 days)
    chart_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        revenue = Order.objects.filter(
            created_at__date=day, status__in=['delivered', 'completed']
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        chart_data.append({'date': day.strftime('%b %d'), 'revenue': float(revenue)})

    context = {
        'stats': stats,
        'recent_orders': recent_orders,
        'top_products': top_products,
        'chart_data': chart_data,
    }
    return render(request, 'admin_panel/dashboard.html', context)


# ─── USER MANAGEMENT ───────────────────────────────────────────────────────────

@admin_required
def user_list(request):
    query = request.GET.get('q', '')
    role = request.GET.get('role', '')
    users = CustomUser.objects.all()
    if query:
        users = users.filter(Q(username__icontains=query) | Q(email__icontains=query))
    if role:
        users = users.filter(role=role)
    return render(request, 'admin_panel/users/list.html', {'users': users, 'query': query, 'role': role})


@admin_required
def user_create(request):
    if request.method == 'POST':
        form = AdminUserCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'User created successfully!')
            return redirect('admin_panel:user_list')
    else:
        form = AdminUserCreateForm()
    return render(request, 'admin_panel/users/form.html', {'form': form, 'title': 'Create User'})


@admin_required
def user_edit(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        form = AdminUserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'User updated successfully!')
            return redirect('admin_panel:user_list')
    else:
        form = AdminUserEditForm(instance=user)
    return render(request, 'admin_panel/users/form.html', {'form': form, 'title': 'Edit User', 'object': user})


@admin_required
def user_delete(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        user.delete()
        messages.success(request, 'User deleted.')
        return redirect('admin_panel:user_list')
    return render(request, 'admin_panel/confirm_delete.html', {'object': user, 'type': 'User'})


@admin_required
def user_toggle_active(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    user.is_active = not user.is_active
    user.save()
    messages.success(request, f"User {'activated' if user.is_active else 'deactivated'}.")
    return redirect('admin_panel:user_list')


# ─── CATEGORY MANAGEMENT ───────────────────────────────────────────────────────

@admin_required
def category_list(request):
    categories_qs = Category.objects.select_related('parent').annotate(
        product_count=Count('products'),
        child_count=Count('children', distinct=True),
        category_attribute_count=Count('category_attributes', distinct=True),
    ).order_by('order', 'name')
    categories = _flatten_category_tree(list(categories_qs))
    return render(request, 'admin_panel/categories/list.html', {
        'categories': categories,
        'category_total': len(categories),
    })


@admin_required
def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created!')
            return redirect('admin_panel:category_list')
    else:
        form = CategoryForm()
    return render(request, 'admin_panel/categories/form.html', {'form': form, 'title': 'Create Category'})


@admin_required
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated!')
            return redirect('admin_panel:category_list')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'admin_panel/categories/form.html', {'form': form, 'title': 'Edit Category', 'object': category})


@admin_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Category deleted.')
        return redirect('admin_panel:category_list')
    return render(request, 'admin_panel/confirm_delete.html', {'object': category, 'type': 'Category'})


# ─── CATEGORY ATTRIBUTE MANAGEMENT ────────────────────────────────────────────

@admin_required
def category_attribute_list(request):
    categories = _flatten_category_tree(list(Category.objects.select_related('parent').order_by('order', 'name')))
    attributes = Attribute.objects.order_by('name')

    selected_category_id = request.GET.get('category') or request.POST.get('category_id')
    selected_category = Category.objects.filter(pk=selected_category_id).first() if selected_category_id else None

    if request.method == 'POST':
        if not selected_category:
            messages.error(request, 'Please select a valid category.')
            return redirect('admin_panel:category_attribute_list')

        selected_ids = {
            int(attribute_id)
            for attribute_id in request.POST.getlist('attributes')
            if attribute_id.isdigit()
        }
        valid_ids = set(attributes.filter(id__in=selected_ids).values_list('id', flat=True))

        existing_qs = CategoryAttribute.objects.filter(category=selected_category)
        existing_ids = set(existing_qs.values_list('attribute_id', flat=True))

        remove_ids = existing_ids - valid_ids
        add_ids = valid_ids - existing_ids

        if remove_ids:
            existing_qs.filter(attribute_id__in=remove_ids).delete()

        if add_ids:
            max_order = existing_qs.aggregate(max_order=Max('display_order'))['max_order'] or 0
            CategoryAttribute.objects.bulk_create([
                CategoryAttribute(
                    category=selected_category,
                    attribute_id=attribute_id,
                    display_order=max_order + index,
                )
                for index, attribute_id in enumerate(sorted(add_ids), start=1)
            ])

        messages.success(request, 'Category attribute mapping saved successfully.')
        return redirect(f"{reverse('admin_panel:category_attribute_list')}?category={selected_category.pk}")

    selected_attribute_ids = set()
    category_mappings = CategoryAttribute.objects.none()
    if selected_category:
        category_mappings = CategoryAttribute.objects.filter(
            category=selected_category
        ).select_related('attribute').order_by('display_order', 'attribute__name')
        selected_attribute_ids = set(category_mappings.values_list('attribute_id', flat=True))

    return render(request, 'admin_panel/category_attributes/list.html', {
        'categories': categories,
        'attributes': attributes,
        'selected_category': selected_category,
        'selected_attribute_ids': selected_attribute_ids,
        'category_mappings': category_mappings,
    })


@admin_required
def category_attribute_create(request):
    if not Category.objects.exists():
        messages.warning(request, 'Create at least one category before assigning category attributes.')
        return redirect('admin_panel:category_create')
    if not Attribute.objects.exists():
        messages.warning(request, 'Create at least one attribute first.')
        return redirect('admin_panel:attribute_create')

    if request.method == 'POST':
        form = CategoryAttributeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category attribute created!')
            return redirect('admin_panel:category_attribute_list')
    else:
        form = CategoryAttributeForm()
    return render(request, 'admin_panel/category_attributes/form.html', {'form': form, 'title': 'Add Category Attribute'})


@admin_required
def category_attribute_edit(request, pk):
    attribute = get_object_or_404(CategoryAttribute, pk=pk)
    if request.method == 'POST':
        form = CategoryAttributeForm(request.POST, instance=attribute)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category attribute updated!')
            return redirect('admin_panel:category_attribute_list')
    else:
        form = CategoryAttributeForm(instance=attribute)
    return render(request, 'admin_panel/category_attributes/form.html', {
        'form': form,
        'title': 'Edit Category Attribute',
        'object': attribute,
    })


@admin_required
def category_attribute_delete(request, pk):
    attribute = get_object_or_404(CategoryAttribute, pk=pk)
    if request.method == 'POST':
        attribute.delete()
        messages.success(request, 'Category attribute deleted.')
        return redirect('admin_panel:category_attribute_list')
    return render(request, 'admin_panel/confirm_delete.html', {'object': attribute, 'type': 'Category Attribute'})


# ─── PRODUCT MANAGEMENT ────────────────────────────────────────────────────────

@admin_required
def product_list(request):
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    products = Product.objects.select_related('category').all()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if category_id:
        products = products.filter(category_id=category_id)
    categories = _flatten_category_tree(list(Category.objects.select_related('parent').order_by('order', 'name')))
    return render(request, 'admin_panel/products/list.html', {
        'products': products, 'categories': categories,
        'query': query, 'category_id': category_id
    })


@admin_required
def product_create(request):
    mapped_attribute_values = {}
    customizations = []
    variants = []
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        mapped_attribute_values = _collect_posted_mapped_values(request.POST)
        customizations = _extract_customization_rows(request.POST)
        if form.is_valid():
            base_price = _effective_base_price(form.cleaned_data)
            variants = _extract_variant_rows(request.POST, base_price)
            selected_category = form.cleaned_data.get('category')
            mapped_values, missing_required, mapping_by_attribute_id = _extract_mapped_attribute_values(
                request.POST,
                selected_category,
            )

            if missing_required:
                form.add_error(None, f"Please fill required mapped attributes: {', '.join(missing_required)}.")
            else:
                product = form.save()
                _sync_product_mapped_attributes(product, mapped_values, mapping_by_attribute_id)
                _sync_product_customizations(product, customizations)
                _sync_product_variants(product, variants)
                messages.success(request, 'Product added to menu!')
                return redirect('admin_panel:product_list')
    else:
        form = ProductForm()
    return render(request, 'admin_panel/products/form.html', {
        'form': form,
        'title': 'Add Product',
        'mapped_attribute_values': mapped_attribute_values,
        'customizations': customizations,
        'variants': variants,
    })


@admin_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    mapped_attribute_values = {
        item.attribute_id: item.value
        for item in ProductAttribute.objects.filter(product=product, attribute__isnull=False)
    }
    customizations = [
        {
            'label': item.value,
            'price_modifier': float(item.price_modifier or 0),
        }
        for item in ProductAttribute.objects.filter(
            product=product,
            attribute__isnull=True,
            attribute_type='addon',
            name='Customization',
        ).order_by('id')
    ]
    variants = [
        {
            'label': item.value,
            'final_price': float(product.effective_price + item.price_modifier),
        }
        for item in ProductAttribute.objects.filter(
            product=product,
            attribute__isnull=True,
            attribute_type='size',
            name='Size',
        ).order_by('id')
    ]

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        mapped_attribute_values = _collect_posted_mapped_values(request.POST)
        customizations = _extract_customization_rows(request.POST)
        if form.is_valid():
            base_price = _effective_base_price(form.cleaned_data)
            variants = _extract_variant_rows(request.POST, base_price)
            selected_category = form.cleaned_data.get('category')
            mapped_values, missing_required, mapping_by_attribute_id = _extract_mapped_attribute_values(
                request.POST,
                selected_category,
            )

            if missing_required:
                form.add_error(None, f"Please fill required mapped attributes: {', '.join(missing_required)}.")
            else:
                product = form.save()
                _sync_product_mapped_attributes(product, mapped_values, mapping_by_attribute_id)
                _sync_product_customizations(product, customizations)
                _sync_product_variants(product, variants)
                messages.success(request, 'Product updated!')
                return redirect('admin_panel:product_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'admin_panel/products/form.html', {
        'form': form,
        'title': 'Edit Product',
        'object': product,
        'mapped_attribute_values': mapped_attribute_values,
        'customizations': customizations,
        'variants': variants,
    })


@admin_required
def category_attributes_json(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    mappings = CategoryAttribute.objects.filter(category=category).select_related('attribute').order_by(
        'display_order', 'attribute__name'
    )

    product_id = request.GET.get('product_id', '')
    existing_options = {}
    if product_id.isdigit():
        rows = ProductAttribute.objects.filter(
            product_id=int(product_id),
            attribute__isnull=False,
        ).order_by('attribute_id', 'id')
        for row in rows:
            existing_options.setdefault(row.attribute_id, []).append({
                'label': row.value,
                'price_modifier': float(row.price_modifier or 0),
            })

    return JsonResponse({
        'attributes': [
            {
                'id': mapping.attribute_id,
                'name': mapping.attribute.name,
                'is_required': mapping.is_required,
                'options': existing_options.get(mapping.attribute_id, []),
            }
            for mapping in mappings
        ]
    })


@admin_required
def product_price_preview(request):
    base_raw = (request.GET.get('base_price') or '0').strip()
    addon_raw_values = request.GET.getlist('addon_prices')

    try:
        base_price = Decimal(base_raw) if base_raw else Decimal('0')
    except (InvalidOperation, ValueError):
        base_price = Decimal('0')

    addon_total = Decimal('0')
    for raw in addon_raw_values:
        candidate = (raw or '').strip()
        if not candidate:
            continue
        try:
            addon_total += Decimal(candidate)
        except (InvalidOperation, ValueError):
            continue

    total_price = base_price + addon_total
    return JsonResponse({
        'base_price': str(base_price),
        'addon_total': str(addon_total),
        'total_price': str(total_price),
    })


@admin_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product removed from menu.')
        return redirect('admin_panel:product_list')
    return render(request, 'admin_panel/confirm_delete.html', {'object': product, 'type': 'Product'})


@admin_required
def product_toggle(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.is_available = not product.is_available
    product.save()
    messages.success(request, f"Product {'enabled' if product.is_available else 'disabled'}.")
    return redirect('admin_panel:product_list')


# ─── ATTRIBUTE MANAGEMENT ──────────────────────────────────────────────────────

@admin_required
def attribute_list(request):
    attributes = Attribute.objects.annotate(category_count=Count('category_links', distinct=True)).order_by('name')
    return render(request, 'admin_panel/attributes/list.html', {'attributes': attributes})


@admin_required
def attribute_create(request):
    if request.method == 'POST':
        form = AttributeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Attribute added!')
            return redirect('admin_panel:attribute_list')
    else:
        form = AttributeForm()
    return render(request, 'admin_panel/attributes/form.html', {'form': form, 'title': 'Add Attribute'})


@admin_required
def attribute_edit(request, pk):
    attr = get_object_or_404(Attribute, pk=pk)
    if request.method == 'POST':
        form = AttributeForm(request.POST, instance=attr)
        if form.is_valid():
            form.save()
            messages.success(request, 'Attribute updated!')
            return redirect('admin_panel:attribute_list')
    else:
        form = AttributeForm(instance=attr)
    return render(request, 'admin_panel/attributes/form.html', {'form': form, 'title': 'Edit Attribute', 'object': attr})


@admin_required
def attribute_delete(request, pk):
    attr = get_object_or_404(Attribute, pk=pk)
    if request.method == 'POST':
        attr.delete()
        messages.success(request, 'Attribute deleted.')
        return redirect('admin_panel:attribute_list')
    return render(request, 'admin_panel/confirm_delete.html', {'object': attr, 'type': 'Attribute'})


# ─── ORDER MANAGEMENT ──────────────────────────────────────────────────────────

@admin_required
def order_list(request):
    status_filter = request.GET.get('status', '')
    orders = Order.objects.select_related('user').order_by('-created_at')
    if status_filter:
        orders = orders.filter(status=status_filter)
    return render(request, 'admin_panel/orders/list.html', {'orders': orders, 'status_filter': status_filter})


@admin_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related('items__product'), pk=pk)
    return render(request, 'admin_panel/orders/detail.html', {'order': order})


@admin_required
def order_update_status(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Order.STATUS_CHOICES):
            order.status = new_status
            order.save()
            messages.success(request, f'Order #{order.id} status updated to {new_status}.')
    return redirect('admin_panel:order_detail', pk=pk)


# ─── COUPON MANAGEMENT ─────────────────────────────────────────────────────────

@admin_required
def coupon_list(request):
    coupons = Coupon.objects.all().order_by('-created_at')
    return render(request, 'admin_panel/coupons/list.html', {'coupons': coupons})


@admin_required
def coupon_create(request):
    if request.method == 'POST':
        form = CouponForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Coupon created!')
            return redirect('admin_panel:coupon_list')
    else:
        form = CouponForm()
    return render(request, 'admin_panel/coupons/form.html', {'form': form, 'title': 'Create Coupon'})


@admin_required
def coupon_edit(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    if request.method == 'POST':
        form = CouponForm(request.POST, instance=coupon)
        if form.is_valid():
            form.save()
            messages.success(request, 'Coupon updated!')
            return redirect('admin_panel:coupon_list')
    else:
        form = CouponForm(instance=coupon)
    return render(request, 'admin_panel/coupons/form.html', {'form': form, 'title': 'Edit Coupon', 'object': coupon})


@admin_required
def coupon_delete(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    if request.method == 'POST':
        coupon.delete()
        messages.success(request, 'Coupon deleted.')
        return redirect('admin_panel:coupon_list')
    return render(request, 'admin_panel/confirm_delete.html', {'object': coupon, 'type': 'Coupon'})


# ─── RESERVATION MANAGEMENT ────────────────────────────────────────────────────

@admin_required
def reservation_list(request):
    from apps.reservations.views import _build_time_slots, SLOT_CAPACITY

    selected_date = request.GET.get('date', '')
    selected_location = request.GET.get('location', '')

    reservations = Reservation.objects.select_related('user').order_by('date', 'time')
    if selected_date:
        reservations = reservations.filter(date=selected_date)
    if selected_location:
        reservations = reservations.filter(cafe_location=selected_location)

    grid_date = selected_date or timezone.localdate().isoformat()
    grid_location = selected_location or 'ahmedabad'

    slot_counts = {}
    day_rows = Reservation.objects.filter(
        date=grid_date,
        cafe_location=grid_location,
        status__in=['pending', 'confirmed', 'completed'],
    )
    for row in day_rows.values('time_slot'):
        slot_counts[row['time_slot']] = slot_counts.get(row['time_slot'], 0) + 1

    slot_grid = [
        {
            'slot': slot,
            'booked': slot_counts.get(slot, 0),
            'capacity': SLOT_CAPACITY,
        }
        for slot in _build_time_slots(grid_location)
    ]

    return render(request, 'admin_panel/reservations/list.html', {
        'reservations': reservations,
        'selected_date': selected_date,
        'selected_location': selected_location,
        'slot_grid': slot_grid,
        'grid_date': grid_date,
        'grid_location': grid_location,
        'location_choices': Reservation.CAFE_LOCATION_CHOICES,
    })


@admin_required
def reservation_status(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = {choice[0] for choice in Reservation.STATUS_CHOICES}
        if new_status in valid_statuses:
            reservation.status = new_status
            reservation.save(update_fields=['status'])
            messages.success(request, 'Reservation status updated.')
        else:
            messages.error(request, 'Invalid reservation status.')
    return redirect('admin_panel:reservation_list')


# ─── REVIEW MANAGEMENT ─────────────────────────────────────────────────────────

@admin_required
def review_list(request):
    reviews = Review.objects.select_related('user', 'product').order_by('-created_at')
    return render(request, 'admin_panel/reviews/list.html', {'reviews': reviews})


@admin_required
def review_approve(request, pk):
    review = get_object_or_404(Review, pk=pk)
    review.is_approved = not review.is_approved
    review.save()
    messages.success(request, f"Review {'approved' if review.is_approved else 'unapproved'}.")
    return redirect('admin_panel:review_list')


@admin_required
def review_delete(request, pk):
    review = get_object_or_404(Review, pk=pk)
    if request.method == 'POST':
        review.delete()
        messages.success(request, 'Review deleted.')
        return redirect('admin_panel:review_list')
    return render(request, 'admin_panel/confirm_delete.html', {'object': review, 'type': 'Review'})


# ─── ANALYTICS ─────────────────────────────────────────────────────────────────

@admin_required
def analytics(request):
    today = timezone.now().date()
    # Monthly revenue (last 12 months)
    monthly_data = []
    for i in range(11, -1, -1):
        month_start = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        revenue = Order.objects.filter(
            created_at__year=month_start.year,
            created_at__month=month_start.month,
            status__in=['delivered', 'completed']
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        monthly_data.append({'month': month_start.strftime('%b %Y'), 'revenue': float(revenue)})

    top_categories = Category.objects.annotate(
        total_orders=Count('products__orderitem')
    ).order_by('-total_orders')[:5]

    context = {
        'monthly_data': monthly_data,
        'top_categories': top_categories,
        'total_revenue': Order.objects.filter(
            status__in=['delivered', 'completed']
        ).aggregate(total=Sum('total_amount'))['total'] or 0,
        'avg_order_value': Order.objects.aggregate(avg=Avg('total_amount'))['avg'] or 0,
    }
    return render(request, 'admin_panel/analytics.html', context)
