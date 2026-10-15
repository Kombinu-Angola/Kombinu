from django.db import migrations
from django.db.models import Count


def backfill(apps, schema_editor):
    """
    Backfill APROXIMADO (relatório R2): score era XP = acertos x 10, logo
    correct_count = score // 10; total_questions é o nº actual de perguntas do
    quiz (pode ter mudado desde a submissão). attempt já é 1 por defeito.
    """
    QuizSubmission = apps.get_model("quizzes", "QuizSubmission")
    Quiz = apps.get_model("quizzes", "Quiz")

    totals = dict(
        Quiz.objects.annotate(n=Count("questions")).values_list("pk", "n")
    )
    for submission in QuizSubmission.objects.all().iterator():
        submission.xp_awarded = submission.score
        submission.correct_count = submission.score // 10
        submission.total_questions = totals.get(submission.quiz_id, 0)
        submission.save(
            update_fields=["xp_awarded", "correct_count", "total_questions"]
        )


class Migration(migrations.Migration):

    dependencies = [
        ("quizzes", "0003_submission_attempts_and_counts"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
