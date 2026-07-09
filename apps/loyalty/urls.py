"""apps/loyalty/urls.py"""
from django.urls import path
from . import views

app_name = 'loyalty'

urlpatterns = [
    path('', views.loyalty_dashboard, name='dashboard'),
]
