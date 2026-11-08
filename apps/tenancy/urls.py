from django.urls import path

from .views import ProvisionMembersView

urlpatterns = [
    path("members/bulk/", ProvisionMembersView.as_view(), name="tenancy-members-bulk"),
]
