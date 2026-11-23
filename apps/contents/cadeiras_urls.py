from django.urls import path

from .views import CadeiraListView

urlpatterns = [
    path("", CadeiraListView.as_view(), name="cadeira-list"),
]
