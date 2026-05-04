from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView, LoginView, MeView, ChangePasswordView,
    AccountListView, AccountDetailView, AccountBalanceView, TopUpView,
)

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/me/', MeView.as_view(), name='auth-me'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='auth-change-password'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('accounts/', AccountListView.as_view(), name='account-list'),
    path('accounts/<uuid:pk>/', AccountDetailView.as_view(), name='account-detail'),
    path('accounts/<uuid:pk>/balance/', AccountBalanceView.as_view(), name='account-balance'),
    path('accounts/<uuid:pk>/top-up/', TopUpView.as_view(), name='account-top-up'),
]
