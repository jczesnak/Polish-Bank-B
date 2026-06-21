from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView, LoginView, MeView, ChangePasswordView,
    AccountListView, AccountDetailView, AccountBalanceView, TopUpView,
    SetBlikPinView, JuniorListView, JuniorDetailView, JuniorTopUpView, JuniorCardTopUpView,
    JuniorTransactionHistoryView,
    JuniorTransferRequestCreateView, JuniorTransferRequestListView,
    ParentTransferRequestListView, ParentTransferRequestApproveView, ParentTransferRequestRejectView,
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
    path('accounts/junior/', JuniorListView.as_view(), name='junior-list'),
    path('accounts/junior/<int:pk>/', JuniorDetailView.as_view(), name='junior-detail'),
    path('accounts/junior/<int:pk>/topup/', JuniorTopUpView.as_view(), name='junior-topup'),
    path('accounts/junior/<int:pk>/topup-card/', JuniorCardTopUpView.as_view(), name='junior-topup-card'),
    path('accounts/junior/<int:pk>/history/', JuniorTransactionHistoryView.as_view(), name='junior-history'),
    path('auth/pin/', SetBlikPinView.as_view(), name='auth-blik-pin'),
    # Przelewy Junior
    path('accounts/junior/transfer-requests/', JuniorTransferRequestCreateView.as_view(), name='junior-transfer-request-create'),
    path('accounts/junior/transfer-requests/my/', JuniorTransferRequestListView.as_view(), name='junior-transfer-requests-my'),
    path('accounts/parent/transfer-requests/', ParentTransferRequestListView.as_view(), name='parent-transfer-requests'),
    path('accounts/parent/transfer-requests/<int:pk>/approve/', ParentTransferRequestApproveView.as_view(), name='parent-transfer-approve'),
    path('accounts/parent/transfer-requests/<int:pk>/reject/', ParentTransferRequestRejectView.as_view(), name='parent-transfer-reject'),
]
