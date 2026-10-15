from django.urls import path

from .views import (
    EnqueteDetailView,
    EnqueteDismissView,
    EnqueteListCreateView,
    EnqueteResultsView,
    EnqueteShownView,
    EnqueteVoteView,
)

urlpatterns = [
    path("", EnqueteListCreateView.as_view(), name="enquete-list"),
    path("<uuid:id>/", EnqueteDetailView.as_view(), name="enquete-detail"),
    path("<uuid:id>/vote/", EnqueteVoteView.as_view(), name="enquete-vote"),
    path("<uuid:id>/shown/", EnqueteShownView.as_view(), name="enquete-shown"),
    path("<uuid:id>/dismiss/", EnqueteDismissView.as_view(), name="enquete-dismiss"),
    path("<uuid:id>/results/", EnqueteResultsView.as_view(), name="enquete-results"),
]
