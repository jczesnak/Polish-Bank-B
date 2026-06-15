from django.urls import path
from .views import (
    OrderCardView, 
    UserCardsView, 
    AuthorizeWebhookView, 
    CaptureWebhookView, 
    RefundWebhookView, 
    BlockCardView, 
    UnblockCardView,
    DeleteCardView,
    CardDetailsView,
    ActivateCardView,
    TopUpCardView,
    DevSimulateShippingView,
    CardTransactionListView
)

urlpatterns = [
    path('transactions/', CardTransactionListView.as_view(), name='card-transactions'),
    path('order/', OrderCardView.as_view(), name='order-card'),
    path('my-cards/', UserCardsView.as_view(), name='my-cards'),
    path('authorize', AuthorizeWebhookView.as_view(), name='webhook-authorize'),
    path('capture', CaptureWebhookView.as_view(), name='webhook-capture'),
    path('refund', RefundWebhookView.as_view(), name='webhook-refund'),
    path('<int:card_id>/block/', BlockCardView.as_view(), name='block-card'),
    path('<int:card_id>/unblock/', UnblockCardView.as_view(), name='unblock-card'),
    path('<int:card_id>/delete/', DeleteCardView.as_view(), name='delete-card'),
    path('<int:card_id>/details/', CardDetailsView.as_view(), name='card-details'),
    path('<int:card_id>/activate/', ActivateCardView.as_view(), name='activate-card'),
    path('<int:card_id>/topup/', TopUpCardView.as_view(), name='topup-card'),
    path('<int:card_id>/simulate-shipping/', DevSimulateShippingView.as_view(), name='dev-simulate-shipping'),
]