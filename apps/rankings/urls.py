from django.urls import path
from .views import GamificationMeView, GlobalRankingView


urlpatterns = [
    path("global/", GlobalRankingView.as_view(), name="ranking-global"),
    path("me/", GamificationMeView.as_view(), name="ranking-me"),
]
