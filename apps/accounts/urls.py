from django.urls import path

from .throttles import TokenRefreshRateThrottle
from .views import LoginView, PasswordAwareTokenRefreshView, RegisterView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth_register"),
    path("login/", LoginView.as_view(), name="auth_login"),
    path(
        "token/refresh/",
        PasswordAwareTokenRefreshView.as_view(
            throttle_classes=[TokenRefreshRateThrottle]
        ),
        name="token_refresh",
    ),
]
