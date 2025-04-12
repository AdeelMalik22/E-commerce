from django.shortcuts import get_object_or_404
from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Category, Product, Order, OrderItem, Cart
from .serializers import CategorySerializer, ProductSerializer, OrderSerializer, CartSerializer, OrderItemSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    """Manage product categories"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]  # Only authenticated users can manage categories

    def retrieve(self, request, *args, **kwargs):
        category = get_object_or_404(Category, pk=kwargs['pk'])
        serializer = CategorySerializer(category)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        category = get_object_or_404(Category, pk=kwargs['pk'])
        category.delete()
        return Response("Category deleted successfully",status=status.HTTP_204_NO_CONTENT)


from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Product
from .serializers import ProductSerializer

class ProductViewSet(viewsets.ModelViewSet):
    """Manage products"""
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['price', 'stock']
    ordering_fields = ['price', 'created_at'] #Sort the product


    def retrieve(self, request, pk=None, *args, **kwargs):
        product = get_object_or_404(Product, pk=pk)
        serializer = ProductSerializer(product)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        product = get_object_or_404(Product, pk=kwargs['pk'])
        product.delete()
        return Response("Product deleted successfully",status=status.HTTP_204_NO_CONTENT)



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