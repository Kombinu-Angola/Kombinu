from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .throttles import TokenRefreshRateThrottle
from .views import RegisterView, LoginView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth_register"),
    path("login/", LoginView.as_view(), name="auth_login"),
    path(
        "token/refresh/",
        TokenRefreshView.as_view(throttle_classes=[TokenRefreshRateThrottle]),
        name="token_refresh",
    ),
]
