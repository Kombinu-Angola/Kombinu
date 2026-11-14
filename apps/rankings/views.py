from django.core.paginator import Paginator
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy.scoping import WorkspaceScopedMixin

from . import selectors

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 100


def display_name(entry):
    """
    Nome de exibição para o ranking. Nunca devolve email: no registo o
    `username` é o próprio email, por isso também não serve de fallback.
    """
    name = f"{entry['user__first_name']} {entry['user__last_name']}".strip()
    return name or f"Utilizador {entry['user_id']}"


def _int_param(request, name, default, minimum, maximum):
    try:
        value = int(request.query_params.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(value, maximum))


class GlobalRankingView(WorkspaceScopedMixin, APIView):
    """
    Ranking do workspace activo (header X-Workspace). O ranking escolar
    nunca mistura XP do marketplace nem de outra organização. Paginado:
    `?page=1&page_size=100`.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        organizacao = self.workspace
        page_size = _int_param(
            request, "page_size", DEFAULT_PAGE_SIZE, 1, MAX_PAGE_SIZE
        )
        page_number = _int_param(request, "page", 1, 1, 10**9)

        paginator = Paginator(selectors.ranking_queryset(organizacao), page_size)
        page = paginator.get_page(page_number)

        top_users = [
            {
                "user_id": entry["user_id"],
                "name": display_name(entry),
                "total_score": entry["total_score"],
                "position": entry["position"],
            }
            for entry in page.object_list
        ]

        return Response(
            {
                "top_users": top_users,
                "user_position": selectors.user_standing(request.user, organizacao),
                "workspace": str(organizacao.pk) if organizacao else None,
                "count": paginator.count,
                "page": page.number,
                "page_size": page_size,
                "total_pages": paginator.num_pages,
            },
            status=status.HTTP_200_OK,
        )
