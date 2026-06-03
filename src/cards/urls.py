from django.urls import path
from .views import OrderCardView, UserCardsView, CardSettlementWebhookView, BlockCardView, CardDetailsView

urlpatterns = [
    path('order/', OrderCardView.as_view(), name='order-card'),
    path('my-cards/', UserCardsView.as_view(), name='my-cards'),
    path('webhook/settle/', CardSettlementWebhookView.as_view(), name='webhook-settle'),
    path('<int:card_id>/block/', BlockCardView.as_view(), name='block-card'),
    path('<int:card_id>/details/', CardDetailsView.as_view(), name='card-details'),
]