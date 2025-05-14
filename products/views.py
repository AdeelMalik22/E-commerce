import hashlib

import stripe
from django.db import transaction
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters, status, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import serializers
from .models import Category, Product, Order,Cart
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


    def list(self, request, *args, **kwargs):
        # Create a safe cache key
        params = request.query_params.urlencode()
        params_hash = hashlib.md5(params.encode('utf-8')).hexdigest()
        cache_key = f'products_{params_hash}'

        cached_data = cache.get(cache_key)
        if cached_data is not None:  # Explicit None check
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=60 * 15)  # Cache for 15 minutes
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

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def checkout(self, request):
        """Initiate checkout and create Stripe session"""
        user = request.user
        cart_items = Cart.objects.filter(user=user)

        if not cart_items.exists():
            return Response({"error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

        line_items = []
        for item in cart_items:
            product = item.product
            quantity = item.quantity

            if product.stock < quantity:
                return Response({"error": f"Insufficient stock for {product.name}"}, status=400)

            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': product.name,
                    },
                    'unit_amount': int(product.price * 100),  # Stripe uses cents
                },
                'quantity': quantity,
            })

        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url=f"{settings.DOMAIN}/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.DOMAIN}/cancel/",
                metadata={'user_id': user.id}
            )
        except Exception as e:
            return Response({'error': str(e)}, status=400)

        return Response({'checkout_url': checkout_session.url}, status=200)

# views.py
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.conf import settings
import stripe
import json
from .models import Product, Order, OrderItem, Cart, CustomUser  # Import your models

stripe.api_key = settings.STRIPE_SECRET_KEY

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = 'your_webhook_secret_here'  # Get this from Stripe dashboard
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)

    # 💳 Event: Successful payment via Checkout
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session['metadata'].get('user_id')

        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return JsonResponse({"error": "User not found"}, status=404)

        # Get cart items
        cart_items = Cart.objects.filter(user=user)
        if not cart_items.exists():
            return JsonResponse({"error": "No items in cart"}, status=400)

        # Create Order
        order = Order.objects.create(customer=user, total_price=0)
        total_price = 0

        for item in cart_items:
            product = item.product
            quantity = item.quantity

            if product.stock < quantity:
                return JsonResponse({"error": f"Not enough stock for {product.name}"}, status=400)

            item_price = product.price * quantity

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=item_price
            )

            # Deduct stock
            product.stock -= quantity
            product.save()

            total_price += item_price

        # Finalize order price
        order.total_price = total_price
        order.save()

        # Clear cart
        cart_items.delete()

        # Optionally log or email confirmation
        print(f" Order created for user {user.email} - Order ID: {order.id}")

    return HttpResponse(status=200)

