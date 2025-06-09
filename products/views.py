import hashlib
import uuid

from django.shortcuts import get_object_or_404
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters, status, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import serializers
from .models import Category, Product, Order, OrderItem, Cart, Review
from .serializers import CategorySerializer, ProductSerializer, OrderSerializer, CartSerializer, OrderItemSerializer, \
    ReviewSerializer

from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.decorators import action
from django.core.cache import cache

from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser  # Add this

PRODUCT_CACHE_VERSION_KEY = 'products_cache_version'


def invalidate_product_cache():
    """Move product list requests to a fresh cache namespace."""
    cache.set(PRODUCT_CACHE_VERSION_KEY, uuid.uuid4().hex, timeout=None)


class IsReviewOwnerOrReadOnly(permissions.BasePermission):
    """Allow review changes only to the user who created the review."""

    def has_object_permission(self, request, view, obj):
        return request.method in permissions.SAFE_METHODS or obj.user == request.user


class IsAdminOrReadOnly(permissions.BasePermission):
    """Allow public catalog reads and restrict catalog changes to staff."""

    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS or bool(
            request.user and request.user.is_staff
        )


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
        response['Cache-Control'] = 'public, max-age=3600'  #
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
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'category__name']
    filterset_fields = ['price', 'stock', 'category']
    ordering_fields = ['price', 'created_at', 'name']
    pagination_class = PageNumberPagination

    def get_queryset(self):
        """Show active products publicly and all products to staff users."""
        queryset = Product.objects.select_related('category').all()
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return queryset
        return queryset.filter(is_active=True)

    def list(self, request, *args, **kwargs):
        # Create a safe cache key
        params = request.query_params.urlencode()
        params_hash = hashlib.md5(params.encode('utf-8')).hexdigest()
        version = cache.get(PRODUCT_CACHE_VERSION_KEY, 'initial')
        visibility = 'staff' if request.user.is_authenticated and request.user.is_staff else 'public'
        cache_key = f'products_{visibility}_{version}_{params_hash}'

        cached_data = cache.get(cache_key)
        if cached_data is not None:  # Explicit None check
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=60 * 15)  # Cache for 15 minutes
        return response


    # Add validation for product creation
    def perform_create(self, serializer):
        if serializer.validated_data['stock'] < 0:
            raise serializers.ValidationError("Stock cannot be negative")
        serializer.save()
        invalidate_product_cache()

    def perform_update(self, serializer):
        serializer.save()
        invalidate_product_cache()

    def perform_destroy(self, instance):
        instance.delete()
        invalidate_product_cache()


class ReviewViewSet(viewsets.ModelViewSet):
    """Manage product reviews"""
    queryset = Review.objects.select_related('user', 'product').all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsReviewOwnerOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


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

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def cancel(self, request, *args, **kwargs):
        """Cancel a pending order and return its reserved products to stock."""
        order = self.get_queryset().select_for_update().get(pk=kwargs['pk'])
        if order.status != 'pending':
            return Response(
                {'error': 'Only pending orders can be cancelled.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for item in order.items.all():
            product = Product.objects.select_for_update().get(pk=item.product_id)
            product.stock += item.quantity
            product.save(update_fields=['stock'])

        order.status = 'cancelled'
        order.save(update_fields=['status'])
        return Response(OrderSerializer(order).data)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """Delete an order and return its reserved products to stock."""
        order = self.get_object()
        for item in order.items.all():
            product = Product.objects.select_for_update().get(pk=item.product_id)
            product.stock += item.quantity
            product.save(update_fields=['stock'])
        order.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)



class OrderItemViewSet(viewsets.ModelViewSet):
    serializer_class = OrderItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return OrderItem.objects.filter(order__customer=self.request.user)

    def retrieve(self, request, pk=None, *args, **kwargs):
        item = get_object_or_404(
            self.get_queryset().select_related('product'),
            pk=pk,
        )
        serializer = self.get_serializer(item)
        return Response(serializer.data)

    @transaction.atomic
    def destroy(self, request, pk=None, *args, **kwargs):
        item = get_object_or_404(
            OrderItem.objects.select_related('product').select_for_update(),
            pk=pk,
            order__customer=request.user,
        )
        product = Product.objects.select_for_update().get(pk=item.product_id)
        product.stock += item.quantity
        product.save(update_fields=['stock'])
        order = item.order
        order.total_price -= item.price
        order.save(update_fields=['total_price'])
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @transaction.atomic
    def perform_create(self, serializer):
        order_id = self.request.data.get('order_id')
        product_id = self.request.data.get('product_id')
        quantity = int(self.request.data.get('quantity', 1))  # ensure it's an int

        # Get order and product
        order = get_object_or_404(
            Order.objects.select_for_update(), id=order_id, customer=self.request.user
        )
        product = get_object_or_404(Product.objects.select_for_update(), id=product_id)

        if quantity > product.stock:
            raise serializers.ValidationError(
                {'quantity': 'Requested quantity exceeds available stock.'}
            )
        product.stock -= quantity
        product.save(update_fields=['stock'])

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

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def checkout(self, request):
        """Create a pending order from the user's cart and reserve its stock."""
        cart_items = list(
            Cart.objects.select_for_update()
            .filter(user=request.user)
            .order_by('product_id')
        )
        if not cart_items:
            return Response(
                {'error': 'Cannot checkout with an empty cart.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order = Order.objects.create(customer=request.user)
        total_price = 0

        for cart_item in cart_items:
            product = Product.objects.select_for_update().get(pk=cart_item.product_id)
            if not product.is_active:
                raise serializers.ValidationError(
                    {'product': f'{product.name} is no longer available.'}
                )
            if cart_item.quantity > product.stock:
                raise serializers.ValidationError(
                    {'quantity': f'Insufficient stock for {product.name}.'}
                )

            item_price = product.price * cart_item.quantity
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=cart_item.quantity,
                price=item_price,
            )
            product.stock -= cart_item.quantity
            product.save(update_fields=['stock'])
            total_price += item_price

        order.total_price = total_price
        order.save(update_fields=['total_price'])
        Cart.objects.filter(user=request.user).delete()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        cart = get_object_or_404(Cart, user=self.request.user,pk=kwargs['pk'])
        cart.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
