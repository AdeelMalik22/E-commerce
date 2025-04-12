from django.shortcuts import render, redirect

import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from allauth.socialaccount.models import SocialApp
from rest_framework_simplejwt.tokens import RefreshToken

from login.models import CustomUser
from login.serializers import  AuthSerializer

from django.shortcuts import render



class GoogleLoginUrlView(APIView):
    def get(self, request):
        client_id = SocialApp.objects.get(provider='google').client_id
        redirect_uri = 'http://127.0.0.1:8000/accounts/google/login/callback/'
        scope = 'openid email profile'

        params = (
            "https://accounts.google.com/o/oauth2/v2/auth"
            "?response_type=code"
            f'&client_id={client_id}'
            f'&redirect_uri={redirect_uri}'
            f'&scope={scope}'
            '&access_type=offline'
            '&prompt=consent'
        )


        # url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        return redirect(params)



class GoogleCallbackView(APIView):

    def get(self, request):
        code = request.GET.get('code')

        app = SocialApp.objects.get(provider='google')
        token_url = 'https://oauth2.googleapis.com/token'
        redirect_uri = 'http://127.0.0.1:8000/accounts/google/login/callback/'

        data = {
            "code": code,
            'client_id': app.client_id,
            'client_secret': app.secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }

        token_response = requests.post(token_url, data=data)
        token_json = token_response.json()

        if "access_token" not in token_json:
            return Response({'error': 'Failed to get access token', 'details': token_json}, status=400)


        access_token = token_json['access_token']

        userinfo_response = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        user_info = userinfo_response.json()
        email = user_info.get('email')

        user, created = CustomUser.objects.get_or_create(
            email=email,
            defaults={
                'username': email.split("@")[0],
                'google_id': user_info.get('id'),
                'picture': user_info.get('picture'),
                'locale': user_info.get('locale'),
            }
        )
        user.save()

        refresh = RefreshToken.for_user(user)

        serializer = AuthSerializer({
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'user': user
        })

        return Response(serializer.data)
