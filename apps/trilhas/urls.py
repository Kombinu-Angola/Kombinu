from django.urls import path

from .views import (
    TrilhaArchiveView,
    TrilhaDetailView,
    TrilhaItemCompleteView,
    TrilhaItemCreateView,
    TrilhaItemDetailView,
    TrilhaItemReorderView,
    TrilhaListView,
    TrilhaPublishView,
    TrilhaUnarchiveView,
)

urlpatterns = [
    path("", TrilhaListView.as_view(), name="trilha-list"),
    path("<uuid:id>/", TrilhaDetailView.as_view(), name="trilha-detail"),
    path("<uuid:id>/publish/", TrilhaPublishView.as_view(), name="trilha-publish"),
    path("<uuid:id>/archive/", TrilhaArchiveView.as_view(), name="trilha-archive"),
    path(
        "<uuid:id>/unarchive/",
        TrilhaUnarchiveView.as_view(),
        name="trilha-unarchive",
    ),
    path("<uuid:id>/items/", TrilhaItemCreateView.as_view(), name="trilha-item-create"),
    path(
        "<uuid:id>/items/reorder/",
        TrilhaItemReorderView.as_view(),
        name="trilha-item-reorder",
    ),
    path(
        "<uuid:id>/items/<uuid:item_id>/",
        TrilhaItemDetailView.as_view(),
        name="trilha-item-detail",
    ),
    path(
        "items/<uuid:id>/complete/",
        TrilhaItemCompleteView.as_view(),
        name="trilha-item-complete",
    ),
]
