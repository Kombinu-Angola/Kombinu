from rest_framework import serializers


class TopUserSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    name = serializers.CharField()
    total_score = serializers.IntegerField()
    position = serializers.IntegerField()


class UserPositionSerializer(serializers.Serializer):
    position = serializers.IntegerField()
    total_score = serializers.IntegerField()


class GlobalRankingSerializer(serializers.Serializer):
    top_users = TopUserSerializer(many=True)
    user_position = UserPositionSerializer()


class GamificationMeSerializer(serializers.Serializer):
    """Contrato do K4: `GET /api/rankings/me/`. Sem gemas (D4)."""

    xp_total = serializers.IntegerField(help_text="XP da carteira global.")
    xp_workspace = serializers.IntegerField(
        help_text="XP do workspace activo; no marketplace, o XP sem organização."
    )
    level = serializers.IntegerField(help_text="xp_total // 100 + 1.")
    streak = serializers.IntegerField(
        help_text=(
            "Dias seguidos com XP (data em Africa/Luanda, carteira global), "
            "terminando hoje ou ontem; senão 0."
        )
    )
    best_streak = serializers.IntegerField(help_text="Maior sequência de sempre.")
    last_activity_date = serializers.DateField(
        allow_null=True, help_text="Data do último XP (YYYY-MM-DD) ou null."
    )
