from django.contrib import admin
from .models import Product, Category, Order, OrderItem, Cart


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id",'name', 'price', 'stock', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at', 'updated_at')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description')
    search_fields = ('name', 'description')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["customer","total_price"]
    search_fields = ["total_price","created_at","customer"]

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ["order", "product", "quantity"]
    search_fields = ['price']

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ["product", "user", "quantity","total_price"]