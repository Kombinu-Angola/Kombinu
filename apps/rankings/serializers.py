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
