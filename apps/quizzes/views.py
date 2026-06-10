from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from .serializers import (
    QuizDetailSerializer,
    QuizGenerationSerializer,
    QuizSubmissionSerializer,
)
from .models import Option, Question, Quiz, QuizAnswer, QuizSubmission
from apps.contents.models import Content
from .services import generate_quiz_from_opentdb


class QuizDetailView(generics.RetrieveAPIView):
    queryset = Quiz.objects.all()
    serializer_class = QuizDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"


class QuizGenerationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, content_id):
        # Verifica se o usuário é um criador
        if request.user.user_type != "creator":
            return Response(
                {"error": "Only creators can generate quizzes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        content = get_object_or_404(Content, id=content_id)
        serializer = QuizGenerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        difficulty = serializer.validated_data.get("difficulty")
        number_of_questions = serializer.validated_data.get("number_of_questions")

        # Verifica se já existe um quiz para este conteúdo
        if hasattr(content, "quiz"):
            return Response(
                {"error": "A quiz already exists for this content."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Chama o serviço para gerar o quiz
        quiz = generate_quiz_from_opentdb(content, difficulty, number_of_questions)

        if quiz:
            return Response(
                {
                    "message": "Quiz generated successfully",
                    "quiz_id": str(quiz.pk),
                    "content_id": str(content.pk),
                },
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(
                {"error": "Failed to generate quiz from Open Trivia DB."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class QuizManualCreationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, content_id):
        if request.user.user_type != "creator":
            return Response(
                {"error": "Only creators can create quizzes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        content = get_object_or_404(Content, id=content_id)

        # Verifica se já existe um quiz para este conteúdo
        if hasattr(content, "quiz"):
            return Response(
                {"error": "A quiz already exists for this content."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        questions_data = request.data.get("questions", [])
        if not questions_data:
            return Response({"error": "No questions provided."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            quiz = Quiz.objects.create(title=f"Quiz: {content.title}", content=content)
            for q_data in questions_data:
                q_text = q_data.get("question", "")
                options = q_data.get("options", [])
                correct_idx = q_data.get("correctAnswer", 0)
                
                question = Question.objects.create(quiz=quiz, question_text=q_text)
                for i, opt_text in enumerate(options):
                    is_correct = (i == correct_idx)
                    Option.objects.create(question=question, text=opt_text, is_correct=is_correct)
            
        return Response(
            {"message": "Quiz created successfully", "quiz_id": str(quiz.pk)},
            status=status.HTTP_201_CREATED,
        )


class QuizSubmissionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quiz_id):
        quiz = get_object_or_404(Quiz, id=quiz_id)
        user = request.user

        # Verificar se o usuário já respondeu a este quiz
        if QuizSubmission.objects.filter(user=user, quiz=quiz).exists():
            return Response(
                {"error": "You have already submitted this quiz."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = QuizSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        answers_data = serializer.validated_data["answers"]

        # Validação adicional: se todas as questões pertencem ao quiz
        submitted_question_ids = set()
        for answer in answers_data:
            submitted_question_ids.add(answer["question_id"])

        quiz_question_ids = set(quiz.questions.values_list("pk", flat=True))
        if not submitted_question_ids.issubset(quiz_question_ids):
            return Response(
                {"error": "One or more questions do not belong to this quiz."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        correct_count = 0
        details = []

        with transaction.atomic():
            submission = QuizSubmission.objects.create(
                user=user, quiz=quiz, score=0
            )

            for answer in answers_data:
                question_id = answer["question_id"]
                selected_option_id = answer["selected_option_id"]

                try:
                    question = quiz.questions.get(pk=question_id)
                except Question.DoesNotExist:
                    continue

                try:
                    selected_option = question.options.get(id=selected_option_id)
                except Option.DoesNotExist:
                    return Response(
                        {
                            "error": f"Option {selected_option_id} does not exist for question {question_id}."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                is_correct = selected_option.is_correct
                if is_correct:
                    correct_count += 1

                QuizAnswer.objects.create(
                    submission=submission,
                    question=question,
                    selected_option=selected_option,
                )

                correct_option = question.options.filter(is_correct=True).first()
                details.append(
                    {
                        "question_id": str(question_id),
                        "correct": is_correct,
                        "correct_option_id": str(correct_option.id) if correct_option else None,
                    }
                )

            # Score guardado em XP (respostas correctas × 10) para suportar
            # o sistema de níveis — level = (total_xp // 100) + 1
            xp_earned = correct_count * 10
            submission.score = xp_earned
            submission.save()

        total_questions = quiz.questions.count()
        return Response(
            {
                "score": xp_earned,
                "totalPoints": total_questions,
                "correctAnswers": correct_count,
                "totalQuestions": total_questions,
                "xp earned": xp_earned,
                "details": details,
            },
            status=status.HTTP_200_OK,
        )
