"""apps/orders/urls.py"""
from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:item_id>/', views.update_cart, name='update_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/apply-coupon/', views.apply_coupon, name='apply_coupon'),
    path('place-order/', views.place_order, name='place_order'),
    path('confirmation/<int:pk>/', views.order_confirmation, name='order_confirmation'),
    path('history/', views.order_history, name='order_history'),
    path('<int:pk>/', views.order_detail, name='order_detail'),
]
