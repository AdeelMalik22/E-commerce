from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect

import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from allauth.socialaccount.models import SocialApp
from rest_framework_simplejwt.tokens import RefreshToken

from login.models import CustomUser
from login.serializers import AuthSerializer


class GoogleLoginUrlView(APIView):
    """Redirect users to Google's OAuth authorization page."""

    def get(self, request):
        """Build and return the Google OAuth authorization URL."""
        client_id = SocialApp.objects.get(provider='google').client_id
        redirect_uri = settings.GOOGLE_REDIRECT_URI
        scope = 'openid email profile'

        params = urlencode({
            'response_type': 'code',
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': scope,
            'access_type': 'offline',
            'prompt': 'consent',
        })
        return redirect(f'https://accounts.google.com/o/oauth2/v2/auth?{params}')



class GoogleCallbackView(APIView):
    """Complete Google OAuth and return access and refresh tokens."""

    def get(self, request):
        """Exchange the authorization code for user details and JWT tokens."""
        if request.GET.get('error'):
            return Response({'error': 'Google sign-in was cancelled'}, status=400)

        code = request.GET.get('code', '').strip()
        if not code:
            return Response({'error': 'Authorization code is required'}, status=400)

        app = SocialApp.objects.get(provider='google')
        token_url = 'https://oauth2.googleapis.com/token'
        redirect_uri = settings.GOOGLE_REDIRECT_URI

        data = {
            "code": code,
            'client_id': app.client_id,
            'client_secret': app.secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }

        try:
            token_response = requests.post(token_url, data=data, timeout=10)
            if not token_response.ok:
                return Response({'error': 'Google authorization code was rejected'}, status=400)
            token_json = token_response.json()
        except (requests.RequestException, ValueError):
            return Response({'error': 'Unable to contact Google token service'}, status=502)

        if "access_token" not in token_json:
            return Response({'error': 'Failed to get access token'}, status=400)


        access_token = token_json['access_token']

        try:
            userinfo_response = requests.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=10,
            )
            if not userinfo_response.ok:
                return Response({'error': 'Google profile request was rejected'}, status=502)
            user_info = userinfo_response.json()
        except (requests.RequestException, ValueError):
            return Response({'error': 'Unable to retrieve Google profile'}, status=502)
        email = user_info.get('email', '').strip().lower()
        if not email:
            return Response({'error': 'Google account email is required'}, status=400)

        user, _ = CustomUser.objects.get_or_create(
            email=email,
            defaults={
                'username': email.split("@")[0],
                'google_id': user_info.get('id'),
                'picture': user_info.get('picture'),
                'locale': user_info.get('locale'),
            }
        )

        refresh = RefreshToken.for_user(user)

        serializer = AuthSerializer({
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'user': user
        })

        return Response(serializer.data)
