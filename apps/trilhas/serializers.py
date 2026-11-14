from rest_framework import serializers

from . import services
from .models import Trilha, TrilhaItem


def _node_title(item):
    if item.title_override:
        return item.title_override
    target = item.target
    if item.kind == "enquete":
        return target.question
    return target.title


def _node_summary(item):
    if item.summary:
        return item.summary
    if item.kind == "conteudo":
        return item.content.description
    return ""


class LearningTrailSerializer(serializers.ModelSerializer):
    """
    Forma de `LearningTrail` (src/features/trail/types.ts) + `id` e
    `progress`. `href` fica no frontend: o backend devolve `kind` + `targetId`.
    O estado dos nós é calculado para o utilizador do pedido.
    """

    nodes = serializers.SerializerMethodField()
    finalExam = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    headline = serializers.CharField(read_only=True)
    isSequential = serializers.BooleanField(source="is_sequential", read_only=True)
    isPublished = serializers.BooleanField(source="is_published", read_only=True)
    archivedAt = serializers.DateTimeField(source="archived_at", read_only=True)

    class Meta:
        model = Trilha
        fields = (
            "id", "subject", "title", "headline", "year", "semester",
            "nodes", "finalExam", "progress", "isSequential", "isPublished", "archivedAt",
        )

    def _computed(self, obj):
        cache = self.context.setdefault("_nodes_cache", {})
        if obj.pk not in cache:
            cache[obj.pk] = services.node_statuses(obj, self.context["request"].user)
        return cache[obj.pk]

    def get_nodes(self, obj):
        nodes = []
        for item, status, prog in self._computed(obj):
            node = {
                "id": str(item.pk),
                "order": item.order,
                "title": _node_title(item),
                "summary": _node_summary(item),
                "minutes": item.minutes or 0,
                "xp": services.potential_xp(item),
                "status": status,
                "kind": item.kind,
                "targetId": str(item.target.pk),
            }
            if prog is not None and prog.stars is not None:
                node["stars"] = prog.stars
            nodes.append(node)
        return nodes

    def get_finalExam(self, obj):
        quiz = obj.final_exam
        if quiz is None:
            return None
        return {
            "title": quiz.title,
            "minutes": services.DEFAULT_EXAM_MINUTES,
            "xp": quiz.questions.count() * services.XP_PER_CORRECT,
            "quizId": str(quiz.pk),
        }

    def get_progress(self, obj):
        computed = self._computed(obj)
        total = len(computed)
        done = sum(1 for _, status, _ in computed if status == "concluido")
        return {
            "completed": done,
            "total": total,
            "percent": round(100.0 * done / total, 1) if total else 0,
        }


class TrilhaWriteSerializer(serializers.ModelSerializer):
    """Criação e edição (B1). `is_published` muda só por `publish/`."""

    isSequential = serializers.BooleanField(source="is_sequential", required=False)
    finalExamId = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Trilha
        fields = (
            "title", "headline", "subject", "year", "semester",
            "isSequential", "finalExamId",
        )


class TrilhaItemWriteSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=TrilhaItem.KIND_CHOICES)
    targetId = serializers.UUIDField(source="target_id")
    titleOverride = serializers.CharField(
        source="title_override", max_length=255, required=False, allow_blank=True
    )
    summary = serializers.CharField(required=False, allow_blank=True)
    minutes = serializers.IntegerField(
        min_value=0, max_value=32767, required=False, allow_null=True
    )
    xpReward = serializers.IntegerField(
        source="xp_reward", min_value=0, required=False, allow_null=True
    )


class TrilhaItemUpdateSerializer(serializers.ModelSerializer):
    """Só metadados; para mudar o alvo remove-se o passo e adiciona-se outro."""

    titleOverride = serializers.CharField(
        source="title_override", max_length=255, required=False, allow_blank=True
    )
    xpReward = serializers.IntegerField(
        source="xp_reward", min_value=0, required=False, allow_null=True
    )

    class Meta:
        model = TrilhaItem
        fields = ("titleOverride", "summary", "minutes", "xpReward")


class TrilhaItemReorderSerializer(serializers.Serializer):
    itemIds = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
