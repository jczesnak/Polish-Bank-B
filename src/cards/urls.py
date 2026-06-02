from django.urls import path

from .views import CardPaymentView, CardTransactionListView, PrepaidCardListView

urlpatterns = [
    path('cards/', PrepaidCardListView.as_view(), name='card-list'),
    path('cards/transactions/', CardTransactionListView.as_view(), name='card-transaction-list'),
    path('cards/<uuid:card_id>/payments/', CardPaymentView.as_view(), name='card-payment'),
]
