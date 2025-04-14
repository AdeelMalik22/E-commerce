from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import serializers
from .models import Category, Product, Order, OrderItem, Cart
from .serializers import CategorySerializer, ProductSerializer, OrderSerializer, CartSerializer, OrderItemSerializer

from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.decorators import action
from django.core.cache import cache

from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser  # Add this

class CategoryViewSet(viewsets.ModelViewSet):
    """Manage product categories"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUser]  # Only admin users should manage categories
    pagination_class = PageNumberPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    # Override list to add caching headers
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
        return response

    # Add validation before deletion
    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        if category.products.exists():
            return Response(
                {"error": "Cannot delete category with associated products"},
                status=status.HTTP_400_BAD_REQUEST
            )
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)



class ProductViewSet(viewsets.ModelViewSet):
    """Manage products"""
    queryset = Product.objects.select_related('category').all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'category__name']
    filterset_fields = ['price', 'stock', 'category']
    ordering_fields = ['price', 'created_at', 'name']
    pagination_class = PageNumberPagination

    # Cache product listings
    def list(self, request, *args, **kwargs):
        cache_key = f'products_{request.query_params}'
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)
        # Set cache for 15 minutes
        cache.set(cache_key, response.data, timeout=60 * 15)
        return response

    # Add featured products endpoint
    @action(detail=False, methods=['get'])
    def featured(self, request):
        featured_products = self.queryset.filter(is_featured=True)[:10]
        serializer = self.get_serializer(featured_products, many=True)
        return Response(serializer.data)

    # Add validation for product creation
    def perform_create(self, serializer):
        if serializer.validated_data['stock'] < 0:
            raise serializers.ValidationError("Stock cannot be negative")
        serializer.save()



class OrderViewSet(viewsets.ModelViewSet):
    """Manage orders for authenticated users"""
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user)

    def perform_create(self, serializer):
        """Create an order with the logged-in user"""
        serializer.save(customer=self.request.user)



class OrderItemViewSet(viewsets.ModelViewSet):
    serializer_class = OrderItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return OrderItem.objects.filter(order__customer=self.request.user)

    def retrieve(self, request, pk=None, *args, **kwargs):
        order = get_object_or_404(Order, pk=pk, customer=request.user)
        serializer = OrderSerializer(order)
        return Response(serializer.data)

    def destroy(self, request,pk=None, *args, **kwargs):
        order = get_object_or_404(Order, pk=pk, customer=request.user)
        order.delete()
        return Response("Order deleted successfully",status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        order_id = self.request.data.get('order_id')
        product_id = self.request.data.get('product_id')
        quantity = int(self.request.data.get('quantity', 1))  # ensure it's an int

        # Get order and product
        order = get_object_or_404(Order, id=order_id, customer=self.request.user)
        product = get_object_or_404(Product, id=product_id)

        # Check if item already exists in this order
        existing_item = OrderItem.objects.filter(order=order, product=product).first()

        if existing_item:
            # Update quantity and price
            existing_item.quantity += quantity
            existing_item.price += product.price * quantity
            existing_item.save()

            # Also update order total
            order.total_price += product.price * quantity
            order.save()
        else:
            # New order item
            item_price = product.price * quantity
            serializer.save(order=order, product=product, quantity=quantity, price=item_price)

            # Update order total
            order.total_price += item_price
            order.save()


class CartViewSet(viewsets.ModelViewSet):
    """Manage shopping cart"""
    queryset = Cart.objects.all()
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Ensure the cart belongs to the authenticated user"""
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        cart = get_object_or_404(Cart, user=self.request.user,pk=kwargs['pk'])
        cart.delete()
        return Response("Cart deleted successfully",status=status.HTTP_204_NO_CONTENT)