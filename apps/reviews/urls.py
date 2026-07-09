"""apps/reviews/urls.py"""
from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    path('add/<int:product_id>/', views.add_review, name='add_review'),
    path('my-reviews/', views.my_reviews, name='my_reviews'),
]
