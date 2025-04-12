from gc import get_objects

from django.shortcuts import get_object_or_404
from rest_framework import serializers
from .models import Category, Product, Order, OrderItem, Cart


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'



class ProductSerializer(serializers.ModelSerializer):
    category_id = serializers.CharField(write_only=True)
    category = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'stock', 'category_id', 'category']

    def create(self, validated_data):
        category_id = validated_data.pop('category_id', None)

        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            raise serializers.ValidationError({"category_id": "Invalid category ID."})

        return Product.objects.create(category=category, **validated_data)


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )
    quantity = serializers.IntegerField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_id', 'quantity', 'price']
        read_only_fields = ['price']

    def create(self, validated_data):
        product = validated_data['product']
        validated_data['price'] = product.price
        return super().create(validated_data)


class OrderSerializer(serializers.ModelSerializer):
    customer = serializers.StringRelatedField(read_only=True)  # Shows customer username
    items = OrderItemSerializer(many=True, read_only=True)  # Displays order items
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'customer', 'created_at', 'total_price', 'items']



class CartSerializer(serializers.ModelSerializer):
    product_id = serializers.CharField(write_only=True)
    product = serializers.StringRelatedField(read_only=True)
    quantity = serializers.IntegerField()

    class Meta:
        model = Cart
        fields = ['id', 'product_id', 'product', 'quantity', 'total_price']
        read_only_fields = ['id', 'product', 'total_price']

    def get_total_price(self, obj):
        return obj.total_price

    def create(self, validated_data):
        request = self.context['request']
        user = request.user

        product_id = validated_data.pop('product_id')
        quantity = validated_data.get('quantity', 1)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            raise serializers.ValidationError({"product_id": "Invalid product ID."})

        cart_item, created = Cart.objects.get_or_create(
            user=user,
            product=product,
            defaults={'quantity': quantity}
        )

        if not created:
            # Optional: Update quantity if already exists
            cart_item.quantity += quantity
            cart_item.save()

        return cart_item
