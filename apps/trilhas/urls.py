from django.urls import path

from .views import TrilhaDetailView, TrilhaItemCompleteView, TrilhaListView

urlpatterns = [
    path("", TrilhaListView.as_view(), name="trilha-list"),
    path("<uuid:id>/", TrilhaDetailView.as_view(), name="trilha-detail"),
    path(
        "items/<uuid:id>/complete/",
        TrilhaItemCompleteView.as_view(),
        name="trilha-item-complete",
    ),
]
