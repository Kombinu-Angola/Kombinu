from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum
from apps.quizzes.models import QuizSubmission


def display_name(entry):
    """
    Nome de exibição para o ranking. Nunca devolve email: no registo o
    `username` é o próprio email, por isso também não serve de fallback.
    """
    name = f"{entry['user__first_name']} {entry['user__last_name']}".strip()
    return name or f"Utilizador {entry['user_id']}"


class GlobalRankingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Uma única query com JOIN — elimina o problema N+1 anterior
        user_scores = list(
            QuizSubmission.objects
            .values("user_id", "user__first_name", "user__last_name")
            .annotate(total_score=Sum("score"))
            .order_by("-total_score")
        )

        top_users_data = [
            {
                "user_id": entry["user_id"],
                "name": display_name(entry),
                "total_score": entry["total_score"],
                "position": i + 1,
            }
            for i, entry in enumerate(user_scores[:100])
        ]

        current_user_id = request.user.pk
        current_user_entry = next(
            (entry for entry in user_scores if entry["user_id"] == current_user_id),
            None,
        )
        current_user_total_score = (
            current_user_entry["total_score"] if current_user_entry else 0
        )

        current_user_position = (
            sum(1 for entry in user_scores if entry["total_score"] > current_user_total_score)
            + 1
        )

        return Response(
            {
                "top_users": top_users_data,
                "user_position": {
                    "position": current_user_position,
                    "total_score": current_user_total_score,
                },
            },
            status=status.HTTP_200_OK,
        )
