"""apps/menu/views.py"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Category, Product


def home(request):
    featured = Product.objects.filter(is_featured=True, is_available=True)[:6]
    bestsellers = Product.objects.filter(is_bestseller=True, is_available=True)[:4]
    categories = Category.objects.filter(is_active=True, parent__isnull=True)[:6]
    context = {
        'featured_products': featured,
        'bestsellers': bestsellers,
        'categories': categories,
    }
    return render(request, 'base/home.html', context)


def cafe_locator(request):
    return render(request, 'base/cafe_locator.html')


@login_required
def menu_list(request):
    return _render_menu(request)


def _render_menu(request, category_slug_override=''):
    parent_categories = Category.objects.filter(
        is_active=True,
        parent__isnull=True,
    ).prefetch_related(
        'children__children'
    ).order_by('order', 'name')
    products = Product.objects.filter(is_available=True).select_related('category')

    # Filtering
    category_slug = category_slug_override or request.GET.get('category', '')
    selected_category_obj = None
    query = request.GET.get('q', '')
    veg_only = request.GET.get('veg', '')
    veg_only_active = bool(veg_only)
    sort = request.GET.get('sort', '')

    if category_slug:
        selected_category_obj = Category.objects.filter(slug=category_slug, is_active=True).first()
        if selected_category_obj:
            category_ids = selected_category_obj.get_descendant_ids()
            category_ids.add(selected_category_obj.id)
            products = products.filter(category_id__in=category_ids)
        else:
            category_slug = ''
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if veg_only_active:
        products = products.filter(is_vegetarian=True)
    if sort == 'price_asc':
        products = products.order_by('price')
    elif sort == 'price_desc':
        products = products.order_by('-price')
    elif sort == 'newest':
        products = products.order_by('-created_at')
    elif sort == 'popular':
        from django.db.models import Count
        products = products.annotate(order_count=Count('orderitem')).order_by('-order_count')

    category_breadcrumb = []
    if selected_category_obj:
        current = selected_category_obj
        while current is not None:
            category_breadcrumb.append(current)
            current = current.parent
        category_breadcrumb.reverse()

    child_categories = []
    if selected_category_obj:
        child_categories = selected_category_obj.children.filter(is_active=True).order_by('order', 'name')

    parent_nav = []
    for parent in parent_categories:
        active_children = [child for child in parent.children.all() if child.is_active]
        parent_nav.append({
            'category': parent,
            'children': active_children,
        })

    context = {
        'parent_nav': parent_nav,
        'selected_category_obj': selected_category_obj,
        'child_categories': child_categories,
        'category_breadcrumb': category_breadcrumb,
        'products': products,
        'selected_category': category_slug,
        'query': query,
        'sort': sort,
        'veg_only': veg_only_active,
    }
    return render(request, 'menu/menu_list.html', context)


@login_required
def category_products(request, slug):
    return _render_menu(request, category_slug_override=slug)


@login_required
def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_available=True)
    related = Product.objects.filter(
        category=product.category, is_available=True
    ).exclude(pk=product.pk)[:4]
    reviews = product.reviews.filter(is_approved=True).select_related('user')
    attributes = list(product.attributes.order_by('attribute_type', 'name', 'value', 'id'))

    variant_map = {}
    addon_map = {}
    for option in attributes:
        key = option.name or ('Variant' if option.attribute_type in ('size', 'variant') else 'Add-on')
        target = variant_map if option.attribute_type in ('size', 'variant') else addon_map
        target.setdefault(key, []).append(option)

    variant_groups = [
        {'name': name, 'options': options}
        for name, options in variant_map.items()
    ]
    addon_groups = [
        {'name': name, 'options': options}
        for name, options in addon_map.items()
    ]

    context = {
        'product': product,
        'related_products': related,
        'reviews': reviews,
        'variant_groups': variant_groups,
        'addon_groups': addon_groups,
    }
    return render(request, 'menu/product_detail.html', context)
