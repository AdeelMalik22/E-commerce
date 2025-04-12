from django.urls import path, re_path

from .views import GoogleLoginUrlView, GoogleCallbackView

urlpatterns = [
    path('google/login/', GoogleLoginUrlView.as_view(), name='google-login-url'),
    path('google/callback/', GoogleCallbackView.as_view(), name='google-callback'),


]
