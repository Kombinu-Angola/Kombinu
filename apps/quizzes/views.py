from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import IntegrityError, transaction
from .serializers import (
    QuizDetailSerializer,
    QuizManualCadeiraSerializer,
    QuizSubmissionSerializer,
)
from .models import Option, Question, Quiz, QuizAnswer, QuizSubmission
from apps.contents.models import Content
from apps.rankings.models import XPEvent
from apps.rankings.services import quiz_submission_xp, record_xp
from apps.tenancy.scoping import WorkspaceScopedMixin, can_create_in
from apps.trilhas.services import on_quiz_submitted

GENERATION_DISABLED_MESSAGE = (
    "A geração automática de quizzes está temporariamente indisponível."
)


class _InvalidAnswer(Exception):
    pass


class QuizDetailView(WorkspaceScopedMixin, generics.RetrieveAPIView):
    queryset = Quiz.objects.select_related("content", "cadeira")
    serializer_class = QuizDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        return self.scope(super().get_queryset())


class QuizGenerationView(APIView):
    """
    Geração automática pela OpenTDB, desligada (K6) até chegar a geração por
    IA. O serviço `generate_quiz_from_opentdb` mantém-se no código.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={410: OpenApiResponse(description=GENERATION_DISABLED_MESSAGE)},
        deprecated=True,
    )
    def post(self, request, content_id):
        return Response(
            {"error": GENERATION_DISABLED_MESSAGE}, status=status.HTTP_410_GONE
        )


class QuizManualCreationView(WorkspaceScopedMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, content_id):
        if not can_create_in(request.user, self.workspace):
            return Response(
                {"error": "Only creators can create quizzes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        content = get_object_or_404(self.scope(Content.objects.all()), id=content_id)
        if content.creator_id != request.user.pk:
            return Response(
                {"error": "Only the content creator can create its quiz."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Verifica se já existe um quiz para este conteúdo
        if hasattr(content, "quiz"):
            return Response(
                {"error": "A quiz already exists for this content."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        questions_data = request.data.get("questions", [])
        if not questions_data:
            return Response({"error": "No questions provided."}, status=status.HTTP_400_BAD_REQUEST)

        # C-K4: `cadeira` opcional (id ou null), do catálogo global.
        cadeira_serializer = QuizManualCadeiraSerializer(data=request.data)
        cadeira_serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            quiz = Quiz.objects.create(
                title=f"Quiz: {content.title}",
                content=content,
                organizacao=content.organizacao,
                cadeira=cadeira_serializer.validated_data.get("cadeira"),
            )
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


class QuizSubmissionView(WorkspaceScopedMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quiz_id):
        quiz = get_object_or_404(self.scope(Quiz.objects.all()), id=quiz_id)
        user = request.user

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
        total_questions = quiz.questions.count()

        # D12: tentativas múltiplas; o XP só é concedido na primeira.
        previous_attempts = QuizSubmission.objects.filter(user=user, quiz=quiz).count()
        attempt = previous_attempts + 1

        try:
            with transaction.atomic():
                submission = QuizSubmission.objects.create(
                    user=user,
                    quiz=quiz,
                    score=0,
                    attempt=attempt,
                    total_questions=total_questions,
                    organizacao=self.workspace,
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
                        # Levantar dentro do atomic faz rollback da submissão,
                        # para não consumir a tentativa (e o XP da 1.ª).
                        raise _InvalidAnswer(
                            f"Option {selected_option_id} does not exist "
                            f"for question {question_id}."
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
                            "correct_option_id": str(correct_option.id)
                            if correct_option
                            else None,
                        }
                    )

                # Score guardado em XP (respostas correctas × 10) para suportar
                # o sistema de níveis — level = (total_xp // 100) + 1.
                # D12: XP só na primeira tentativa.
                xp_earned = quiz_submission_xp(correct_count, attempt)
                submission.correct_count = correct_count
                submission.xp_awarded = xp_earned
                submission.score = xp_earned
                submission.save()
                record_xp(
                    user=user,
                    amount=xp_earned,
                    source_type=XPEvent.SOURCE_QUIZ_SUBMISSION,
                    source_id=submission.pk,
                    organizacao=self.workspace,
                )
                on_quiz_submitted(user, submission, self.workspace)
        except _InvalidAnswer as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError:
            return Response(
                {"error": "Concurrent submission detected. Please try again."},
                status=status.HTTP_409_CONFLICT,
            )

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
