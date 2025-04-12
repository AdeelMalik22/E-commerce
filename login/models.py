import uuid

from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models



class CustomUser(AbstractUser):
    groups = models.ManyToManyField(
        Group,
        related_name='customuser_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups'
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='customuser_permissions_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions'
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    google_id = models.CharField(max_length=255, blank=True, null=True)
    picture = models.URLField(blank=True, null=True)
    locale = models.CharField(max_length=10, blank=True, null=True)

    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address_line_1 = models.CharField(max_length=255, blank=True, null=True)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)

    USER_TYPE_CHOICES = [('buyer', 'Buyer'), ('seller', 'Seller'), ('admin', 'Admin')]
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='buyer')

    is_email_verified = models.BooleanField(default=False)
    has_accepted_terms = models.BooleanField(default=False)
    is_suspended = models.BooleanField(default=False)

    def __str__(self):
        return self.username

