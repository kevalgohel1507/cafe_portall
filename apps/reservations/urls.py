"""apps/reservations/urls.py"""
from django.urls import path
from . import views

app_name = 'reservations'

urlpatterns = [
    path('', views.make_reservation, name='make_reservation'),
    path('availability/', views.reservation_availability, name='reservation_availability'),
    path('confirmation/<str:reference>/', views.reservation_confirmation, name='reservation_confirmation'),
    path('my/', views.my_reservations, name='my_reservations'),
    path('cancel/<int:pk>/', views.cancel_reservation, name='cancel_reservation'),
    path('rebook/<int:pk>/', views.rebook_reservation, name='rebook_reservation'),
]
