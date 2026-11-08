from django.urls import path

from .throttles import TokenRefreshRateThrottle
from .views import (
    InstitutionalLoginView,
    LoginView,
    PasswordAwareTokenRefreshView,
    PasswordChangeView,
    RegisterView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth_register"),
    path("login/", LoginView.as_view(), name="auth_login"),
    path(
        "institutional/login/",
        InstitutionalLoginView.as_view(),
        name="auth_institutional_login",
    ),
    path("password/change/", PasswordChangeView.as_view(), name="auth_password_change"),
    path(
        "token/refresh/",
        PasswordAwareTokenRefreshView.as_view(
            throttle_classes=[TokenRefreshRateThrottle]
        ),
        name="token_refresh",
    ),
]
