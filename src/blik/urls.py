from django.urls import path
from .views import (
    BlikGenerateView,
    BlikWebhookAuthorizeView,
    BlikPingView,
    BlikTransactionListView,
    P2PAliasView,
    P2PAliasDeleteView,
    P2PLookupView,
    P2PTransferView,
    P2PContactView,
    P2PContactDeleteView,
)

urlpatterns = [
    path('blik/generate/', BlikGenerateView.as_view(), name='blik-generate'),
    path('blik/transactions/', BlikTransactionListView.as_view(), name='blik-transactions'),

    # Webhooki od KLIK. KLIK woła {webhook_url}/authorize oraz {webhook_url}/ping
    # BEZ końcowego slasha, więc rejestrujemy warianty bez slasha (operator
    # ustawia w KLIK webhook_url = http://<bank>/api/blik/webhook).
    path('blik/webhook/authorize', BlikWebhookAuthorizeView.as_view(), name='blik-webhook-authorize'),
    path('blik/webhook/authorize/', BlikWebhookAuthorizeView.as_view()),
    path('blik/webhook/ping', BlikPingView.as_view(), name='blik-webhook-ping'),
    path('blik/webhook/ping/', BlikPingView.as_view()),

    # P2P (przelew na telefon)
    path('blik/p2p/aliases/', P2PAliasView.as_view(), name='blik-p2p-aliases'),
    path('blik/p2p/aliases/<str:phone>/', P2PAliasDeleteView.as_view(), name='blik-p2p-alias-delete'),
    path('blik/p2p/lookup/<str:phone>/', P2PLookupView.as_view(), name='blik-p2p-lookup'),
    path('blik/p2p/transfer/', P2PTransferView.as_view(), name='blik-p2p-transfer'),
    path('blik/p2p/contacts/', P2PContactView.as_view(), name='blik-p2p-contacts'),
    path('blik/p2p/contacts/<uuid:contact_id>/', P2PContactDeleteView.as_view(), name='blik-p2p-contact-delete'),
]
