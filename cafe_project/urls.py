"""cafe_project/urls.py"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.menu import views as menu_views

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('', menu_views.home, name='home'),
    path('cafe-locator/', menu_views.cafe_locator, name='cafe_locator'),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('menu/', include('apps.menu.urls', namespace='menu')),
    path('orders/', include('apps.orders.urls', namespace='orders')),
    path('reviews/', include('apps.reviews.urls', namespace='reviews')),
    path('reservations/', include('apps.reservations.urls', namespace='reservations')),
    path('loyalty/', include('apps.loyalty.urls', namespace='loyalty')),
    path('admin-panel/', include('apps.accounts.admin_urls', namespace='admin_panel')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
