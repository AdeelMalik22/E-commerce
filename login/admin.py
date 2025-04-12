from django.contrib import admin

# Register your models here.

from django.contrib import admin
from .models import CustomUser

@admin.register(CustomUser)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id",'first_name', 'email')
