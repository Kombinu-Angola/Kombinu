from django.urls import path

from .perfil_views import InstituicaoListView, MeView

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
    path("instituicoes/", InstituicaoListView.as_view(), name="instituicao-list"),
]
