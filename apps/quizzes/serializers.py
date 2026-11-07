from rest_framework import serializers
from .models import Option, Question, Quiz, QuizSubmission


class OptionSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="pk", read_only=True)

    class Meta:
        model = Option
        fields = ("id", "text")


class QuestionSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="pk", read_only=True)
    text = serializers.CharField(source="question_text", read_only=True)
    options = OptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ("id", "text", "options")


class QuizDetailSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="pk", read_only=True)
    description = serializers.CharField(source="content.description", read_only=True)
    questions = QuestionSerializer(many=True, read_only=True)
    timeLimit = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = ("id", "title", "description", "questions", "timeLimit")

    def get_timeLimit(self, obj):
        return 15


class QuizAnswerSubmissionSerializer(serializers.Serializer):
    question_id = serializers.UUIDField()
    selected_option_id = serializers.UUIDField()


class QuizSubmissionSerializer(serializers.Serializer):
    answers = QuizAnswerSubmissionSerializer(many=True)

    def validate(self, data):
        if not data.get('answers'):
            raise serializers.ValidationError("At least one answer is required.")
        # Uma resposta por pergunta: respostas repetidas inflacionavam o XP.
        question_ids = [answer["question_id"] for answer in data["answers"]]
        if len(question_ids) != len(set(question_ids)):
            raise serializers.ValidationError(
                "Each question can only be answered once per submission."
            )
        return data


class QuizGenerationSerializer(serializers.Serializer):
    difficulty = serializers.ChoiceField(
        choices=["easy", "medium", "hard"], required=False
    )
    number_of_questions = serializers.IntegerField(  # CORRIGIDO: era number_of_question
        min_value=1, max_value=50, required=False, default=10
    )
