from rest_framework import serializers

from .models import Enquete, EnqueteOpcao

MAX_OPTIONS = 10


class SurveyDraftSerializer(serializers.Serializer):
    """Entrada: forma exacta de `SurveyDraft` (camelCase)."""

    decision = serializers.CharField()
    kind = serializers.ChoiceField(choices=[c[0] for c in Enquete.KIND_CHOICES])
    question = serializers.CharField()
    options = serializers.ListField(
        child=serializers.CharField(max_length=200, allow_blank=False),
        allow_empty=False,
    )
    faculty = serializers.CharField(allow_blank=True, required=False, default="")
    subject = serializers.CharField(allow_blank=True, required=False, default="")
    trigger = serializers.ChoiceField(choices=[c[0] for c in Enquete.TRIGGER_CHOICES])
    sampleTarget = serializers.IntegerField(min_value=1, source="sample_target")
    segmentSize = serializers.IntegerField(
        min_value=1, source="segment_size", required=False, allow_null=True
    )

    def validate_options(self, value):
        cleaned = [o.strip() for o in value]
        if any(not o for o in cleaned):
            raise serializers.ValidationError("Opções vazias não são permitidas.")
        if len({o.lower() for o in cleaned}) != len(cleaned):
            raise serializers.ValidationError("As opções têm de ser distintas.")
        if len(cleaned) > MAX_OPTIONS:
            raise serializers.ValidationError(f"No máximo {MAX_OPTIONS} opções.")
        return cleaned

    def validate(self, data):
        kind, options = data["kind"], data["options"]
        if kind == "binaria" and len(options) != 2:
            raise serializers.ValidationError(
                {"options": "Uma enquete binária tem exactamente 2 opções."}
            )
        if kind in ("escala", "escolha") and len(options) < 2:
            raise serializers.ValidationError(
                {"options": "São necessárias pelo menos 2 opções."}
            )
        return data


class OpcaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnqueteOpcao
        fields = ("id", "label", "value")


class _BaseEnqueteSerializer(serializers.ModelSerializer):
    sampleTarget = serializers.IntegerField(source="sample_target", read_only=True)
    segmentSize = serializers.IntegerField(source="segment_size", read_only=True)
    options = OpcaoSerializer(many=True, read_only=True)


class EnqueteVoterSerializer(_BaseEnqueteSerializer):
    """Vista do votante: nunca inclui `decision` nem quem votou."""

    hasVoted = serializers.SerializerMethodField()

    class Meta:
        model = Enquete
        fields = (
            "id", "kind", "question", "faculty", "subject", "trigger",
            "state", "options", "hasVoted",
        )

    def get_hasVoted(self, obj):
        user = self.context["request"].user
        return obj.votes.filter(user=user).exists()


class EnqueteOwnerSerializer(_BaseEnqueteSerializer):
    """Vista do criador: forma de SurveyDraft + id/estado."""

    closedAt = serializers.DateTimeField(source="closed_at", read_only=True)

    class Meta:
        model = Enquete
        fields = (
            "id", "decision", "kind", "question", "options", "faculty", "subject",
            "trigger", "sampleTarget", "segmentSize", "state", "closedAt",
        )


class VoteSerializer(serializers.Serializer):
    optionId = serializers.UUIDField()
