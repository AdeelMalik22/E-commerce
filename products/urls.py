from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .views import CategoryViewSet, ProductViewSet, OrderViewSet, CartViewSet, OrderItemViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet,basename='categories')
router.register(r'products', ProductViewSet,basename='products')
router.register(r'orders', OrderViewSet,basename='orders')
router.register(r'carts', CartViewSet, basename='carts')

router.register(r'order-items', OrderItemViewSet ,basename='order-items')

urlpatterns = [
    path('api/', include(router.urls)),


]
