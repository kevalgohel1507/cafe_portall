"""apps/orders/context_processors.py"""
from .models import Cart


def cart_count(request):
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
            return {'cart_count': cart.item_count}
        except Cart.DoesNotExist:
            pass
    return {'cart_count': 0}
