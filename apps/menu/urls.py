"""apps/menu/urls.py"""
from django.urls import path
from . import views

app_name = 'menu'

urlpatterns = [
    path('', views.menu_list, name='menu_list'),
    path('category/<slug:slug>/', views.category_products, name='category_products'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
]
