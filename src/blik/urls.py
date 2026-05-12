from django.urls import path
from .views import BlikGenerateView, BlikWebhookAuthorizeView, BlikPingView, BlikTransactionListView

urlpatterns = [
    path('blik/generate/', BlikGenerateView.as_view(), name='blik-generate'),
    path('blik/webhook/authorize/', BlikWebhookAuthorizeView.as_view(), name='blik-webhook-authorize'),
    path('blik/webhook/ping/', BlikPingView.as_view(), name='blik-webhook-ping'),
    path('blik/transactions/', BlikTransactionListView.as_view(), name='blik-transactions'),
]
