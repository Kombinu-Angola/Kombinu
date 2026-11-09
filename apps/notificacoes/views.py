from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.tenancy.scoping import WorkspaceScopedMixin

from .models import Notificacao
from .serializers import (
    NotificationSerializer,
    ReadAllSerializer,
    UnreadCountSerializer,
)


class UnreadCountRateThrottle(UserRateThrottle):
    scope = "notifications_unread"


class _NotificacaoBase(WorkspaceScopedMixin):
    """Só as notificações do próprio utilizador no contexto activo."""

    permission_classes = [IsAuthenticated]

    def own_notifications(self):
        return self.scope(Notificacao.objects.filter(user=self.request.user))


class NotificationListView(_NotificacaoBase, generics.ListAPIView):
    serializer_class = NotificationSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "unread", OpenApiTypes.BOOL, description="Só as não lidas."
            )
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = self.own_notifications().order_by("-created_at")
        if self.request.query_params.get("unread", "").lower() == "true":
            qs = qs.filter(read_at__isnull=True)
        return qs


class NotificationUnreadCountView(_NotificacaoBase, APIView):
    throttle_classes = [UnreadCountRateThrottle]

    @extend_schema(responses={200: UnreadCountSerializer})
    def get(self, request):
        count = self.own_notifications().filter(read_at__isnull=True).count()
        return Response({"count": count})


class NotificationReadView(_NotificacaoBase, APIView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request, id):
        notificacao = get_object_or_404(self.own_notifications(), pk=id)
        if notificacao.read_at is None:
            notificacao.read_at = timezone.now()
            notificacao.save(update_fields=["read_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationReadAllView(_NotificacaoBase, APIView):
    @extend_schema(request=None, responses={200: ReadAllSerializer})
    def post(self, request):
        updated = (
            self.own_notifications()
            .filter(read_at__isnull=True)
            .update(read_at=timezone.now())
        )
        return Response({"updated": updated})
