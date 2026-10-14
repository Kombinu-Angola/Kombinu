from django.db import models
from apps.accounts.models import CustomUser
from apps.contents.models import Content
from apps.tenancy.querysets import OrganizacaoQuerySet
import uuid


class Quiz(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    content = models.OneToOneField(
        Content, on_delete=models.CASCADE, related_name="quiz"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    organizacao = models.ForeignKey(
        "tenancy.Organizacao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quizzes",
        help_text="NULL = marketplace (B2C).",
    )

    objects = OrganizacaoQuerySet.as_manager()

    def __str__(self):
        return self.title


class Question(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    question_text = models.TextField()

    def __str__(self):
        return self.question_text[:50]


class Option(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="options"
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.text[:30]}... ({'Correct' if self.is_correct else 'Incorrect'})"


class QuizSubmission(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    submitted_at = models.DateTimeField(auto_now_add=True)
    score = models.PositiveIntegerField()
    organizacao = models.ForeignKey(
        "tenancy.Organizacao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quiz_submissions",
        help_text="NULL = marketplace (B2C).",
    )

    objects = OrganizacaoQuerySet.as_manager()

    class Meta:
        unique_together = ("user", "quiz")

    def __str__(self):
        return f"{self.user.email} - {self.quiz.title} - Score: {self.score}"


class QuizAnswer(models.Model):
    submission = models.ForeignKey(
        QuizSubmission, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.ForeignKey(Option, on_delete=models.CASCADE)

    def __str__(self):
        return f"Answer to {self.question.pk} in submission {self.submission.pk}"
