from django.urls import path
from .views import (
    ApprovalDecisionView,
    ApprovalListView,
    IncomingTransferListView,
    InternalTransferView,
    TransferDetailView,
    TransferListCreateView,
)

urlpatterns = [
    path('transfers/', TransferListCreateView.as_view(), name='transfer-list'),
    path('transfers/incoming/', IncomingTransferListView.as_view(), name='transfer-incoming'),
    path('transfers/<uuid:pk>/', TransferDetailView.as_view(), name='transfer-detail'),
    path('approvals/', ApprovalListView.as_view(), name='approval-list'),
    path('approvals/<uuid:pk>/approve/', ApprovalDecisionView.as_view(), {'decision': 'approve'}, name='approval-approve'),
    path('approvals/<uuid:pk>/reject/', ApprovalDecisionView.as_view(), {'decision': 'reject'}, name='approval-reject'),
    path('internal/', InternalTransferView.as_view(), name='internal_transfer'),
]
