from django.db import migrations


def backfill(apps, schema_editor):
    """Uma linha de ledger por QuizSubmission existente com XP > 0."""
    QuizSubmission = apps.get_model("quizzes", "QuizSubmission")
    XPEvent = apps.get_model("rankings", "XPEvent")

    events = []
    for s in QuizSubmission.objects.filter(score__gt=0).iterator():
        events.append(
            XPEvent(
                user_id=s.user_id,
                organizacao_id=s.organizacao_id,
                source_type="quiz_submission",
                source_id=str(s.pk),
                amount=s.score,
            )
        )
        if len(events) >= 500:
            XPEvent.objects.bulk_create(events, ignore_conflicts=True)
            events = []
    if events:
        XPEvent.objects.bulk_create(events, ignore_conflicts=True)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("rankings", "0001_xpevent"),
        ("quizzes", "0004_backfill_submission_counts"),
    ]

    operations = [migrations.RunPython(backfill, noop)]
