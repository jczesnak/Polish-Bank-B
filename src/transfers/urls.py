from django.urls import path
from .views import TransferListCreateView, TransferDetailView, InternalTransferView, IncomingTransferListView

urlpatterns = [
    path('transfers/', TransferListCreateView.as_view(), name='transfer-list'),
    path('transfers/incoming/', IncomingTransferListView.as_view(), name='transfer-incoming'),
    path('transfers/<uuid:pk>/', TransferDetailView.as_view(), name='transfer-detail'),
    path('internal/', InternalTransferView.as_view(), name='internal_transfer'),
]
