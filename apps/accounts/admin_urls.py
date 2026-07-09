"""apps/accounts/admin_urls.py"""
from django.urls import path
from . import admin_views

app_name = 'admin_panel'

urlpatterns = [
    path('', admin_views.dashboard, name='dashboard'),
    # Users
    path('users/', admin_views.user_list, name='user_list'),
    path('users/create/', admin_views.user_create, name='user_create'),
    path('users/<int:pk>/edit/', admin_views.user_edit, name='user_edit'),
    path('users/<int:pk>/delete/', admin_views.user_delete, name='user_delete'),
    path('users/<int:pk>/toggle/', admin_views.user_toggle_active, name='user_toggle'),
    # Categories
    path('categories/', admin_views.category_list, name='category_list'),
    path('categories/create/', admin_views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', admin_views.category_edit, name='category_edit'),
    path('categories/<int:pk>/delete/', admin_views.category_delete, name='category_delete'),
    path('categories/<int:category_id>/attributes-json/', admin_views.category_attributes_json, name='category_attributes_json'),
    path('category-attributes/', admin_views.category_attribute_list, name='category_attribute_list'),
    path('category-attributes/create/', admin_views.category_attribute_create, name='category_attribute_create'),
    path('category-attributes/<int:pk>/edit/', admin_views.category_attribute_edit, name='category_attribute_edit'),
    path('category-attributes/<int:pk>/delete/', admin_views.category_attribute_delete, name='category_attribute_delete'),
    # Products
    path('products/', admin_views.product_list, name='product_list'),
    path('products/create/', admin_views.product_create, name='product_create'),
    path('products/price-preview/', admin_views.product_price_preview, name='product_price_preview'),
    path('products/<int:pk>/edit/', admin_views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', admin_views.product_delete, name='product_delete'),
    path('products/<int:pk>/toggle/', admin_views.product_toggle, name='product_toggle'),
    # Attributes
    path('attributes/', admin_views.attribute_list, name='attribute_list'),
    path('attributes/create/', admin_views.attribute_create, name='attribute_create'),
    path('attributes/<int:pk>/edit/', admin_views.attribute_edit, name='attribute_edit'),
    path('attributes/<int:pk>/delete/', admin_views.attribute_delete, name='attribute_delete'),
    # Orders
    path('orders/', admin_views.order_list, name='order_list'),
    path('orders/<int:pk>/', admin_views.order_detail, name='order_detail'),
    path('orders/<int:pk>/status/', admin_views.order_update_status, name='order_status'),
    # Coupons
    path('coupons/', admin_views.coupon_list, name='coupon_list'),
    path('coupons/create/', admin_views.coupon_create, name='coupon_create'),
    path('coupons/<int:pk>/edit/', admin_views.coupon_edit, name='coupon_edit'),
    path('coupons/<int:pk>/delete/', admin_views.coupon_delete, name='coupon_delete'),
    # Reservations
    path('reservations/', admin_views.reservation_list, name='reservation_list'),
    path('reservations/<int:pk>/status/', admin_views.reservation_status, name='reservation_status'),
    # Reviews
    path('reviews/', admin_views.review_list, name='review_list'),
    path('reviews/<int:pk>/approve/', admin_views.review_approve, name='review_approve'),
    path('reviews/<int:pk>/delete/', admin_views.review_delete, name='review_delete'),
    # Analytics
    path('analytics/', admin_views.analytics, name='analytics'),
]
