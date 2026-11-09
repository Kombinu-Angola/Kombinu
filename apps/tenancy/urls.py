from django.urls import path

from .views import (
    MarketplaceVisitView,
    MemberDeactivateView,
    MemberListView,
    MemberPasswordResetView,
    MemberReactivateView,
    ProvisionMembersView,
)

urlpatterns = [
    path(
        "marketplace-visit/",
        MarketplaceVisitView.as_view(),
        name="tenancy-marketplace-visit",
    ),
    path("members/", MemberListView.as_view(), name="tenancy-members"),
    path("members/bulk/", ProvisionMembersView.as_view(), name="tenancy-members-bulk"),
    path(
        "members/<uuid:id>/deactivate/",
        MemberDeactivateView.as_view(),
        name="tenancy-member-deactivate",
    ),
    path(
        "members/<uuid:id>/reactivate/",
        MemberReactivateView.as_view(),
        name="tenancy-member-reactivate",
    ),
    path(
        "members/<uuid:id>/reset-password/",
        MemberPasswordResetView.as_view(),
        name="tenancy-member-reset-password",
    ),
]
