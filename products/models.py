from django.db import models
from django.db.models import Avg
from shortuuid.django_fields import ShortUUIDField

from login.models import CustomUser


class SoftDeleteModel(models.Model):
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class Category(models.Model):
    id = ShortUUIDField(primary_key=True)  # Use short UUIDs
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Product(SoftDeleteModel):
    id = ShortUUIDField(primary_key=True)  # Use short UUIDs
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="products/", null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products', null=True, blank =True)

    def __str__(self):
        return self.name

    def average_rating(self):
        return self.reviews.aggregate(Avg("rating"))["rating__avg"] or 0

    def review_count(self):
        return self.reviews.count()



class Order(models.Model):
    id = ShortUUIDField(primary_key=True)  # Use short UUIDs
    customer = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="orders")
    created_at = models.DateTimeField(auto_now_add=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Order {self.id} by {self.customer.username}"

class OrderItem(models.Model):
    id = ShortUUIDField(primary_key=True)  # Use short UUIDs
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


class Cart(models.Model):
    id = ShortUUIDField(primary_key=True, max_length=22)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="cart")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    @property
    def total_price(self):
        return self.quantity * self.product.price

    def __str__(self):
        return f"{self.user.username} - {self.product.name} ({self.quantity})"

    class Meta:
        unique_together = ('user', 'product')


class Review(models.Model):
    id = ShortUUIDField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="reviews")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField()  # Typically 1-5 stars
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')  # One review per user per product

    def __str__(self):
        return f"{self.user.username} rated {self.product.name} ({self.rating}⭐)"



