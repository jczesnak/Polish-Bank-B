from django.urls import path
from .views import (
    TransferListCreateView,
    TransferDetailView,
    InternalTransferView,
    IncomingTransferListView,
    SwiftReceiveView,
    SwiftAckView,
    SwiftReturnView,
    TransferAMLExplainView,
)

urlpatterns = [
    path('transfers/', TransferListCreateView.as_view(), name='transfer-list'),
    path('transfers/incoming/', IncomingTransferListView.as_view(), name='transfer-incoming'),
    path('transfers/<uuid:pk>/', TransferDetailView.as_view(), name='transfer-detail'),
    path('transfers/<uuid:pk>/aml-explain/', TransferAMLExplainView.as_view(), name='transfer-aml-explain'),
    path('internal/', InternalTransferView.as_view(), name='internal_transfer'),
    # SWIFT endpoints
    path('swift/receive', SwiftReceiveView.as_view(), name='swift-receive'),
    path('swift/ack', SwiftAckView.as_view(), name='swift-ack'),
    path('swift/return', SwiftReturnView.as_view(), name='swift-return'),
]
