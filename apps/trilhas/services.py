"""
Progresso em Trilhas (SLA §8.4). Regras num só sítio: estado dos nós, estrelas
e conclusão de itens.
"""
from django.db import transaction
from django.utils import timezone

from .models import TrilhaItem, TrilhaProgresso

# XP por resposta correcta num quiz. Hoje vive hardcoded em QuizSubmissionView;
# mantido aqui só para calcular `xp` potencial dos nós.
XP_PER_CORRECT = 10
# QuizDetailSerializer.get_timeLimit devolve 15 fixo; sem campo próprio no Quiz.
DEFAULT_EXAM_MINUTES = 15

# D7 (sugestão a confirmar pelo CTO): % de acertos -> estrelas.
STAR_THRESHOLDS = ((90, 3), (75, 2), (50, 1))


def stars_for(correct_count, total_questions):
    if not total_questions:
        return 0
    pct = 100.0 * correct_count / total_questions
    for threshold, stars in STAR_THRESHOLDS:
        if pct >= threshold:
            return stars
    return 0


def _complete(user, item, *, submission=None, stars=None):
    with transaction.atomic():
        progress, created = TrilhaProgresso.objects.get_or_create(
            user=user, item=item, defaults={"state": "em_curso"}
        )
        progress.state = "concluido"
        if progress.completed_at is None:
            progress.completed_at = timezone.now()
        if stars is not None:
            # melhor resultado conta
            progress.stars = max(progress.stars or 0, stars)
        if submission is not None:
            progress.submission = submission
        progress.save()
    return progress


def complete_content_item(user, item):
    """Conclusão explícita de um item `conteudo`."""
    return _complete(user, item)


def on_quiz_submitted(user, submission, organizacao):
    """Marca como concluídos os itens `quiz` (do mesmo contexto) deste quiz."""
    items = TrilhaItem.objects.filter(
        kind="quiz",
        quiz_id=submission.quiz_id,
        trilha__is_published=True,
        trilha__organizacao=organizacao,
    )
    stars = stars_for(submission.correct_count, submission.total_questions)
    for item in items:
        _complete(user, item, submission=submission, stars=stars)


def on_enquete_voted(user, enquete, organizacao):
    items = TrilhaItem.objects.filter(
        kind="enquete",
        enquete=enquete,
        trilha__is_published=True,
        trilha__organizacao=organizacao,
    )
    for item in items:
        _complete(user, item)


def node_statuses(trilha, user):
    """
    Devolve [(item, status, progress)] por ordem. `concluido` vem de
    TrilhaProgresso; com `is_sequential`, o primeiro não concluído é `ativo` e
    os restantes `bloqueado`; sem sequência, todos os não concluídos são `ativo`.
    """
    items = list(trilha.items.all())  # ordenados por `order`
    progress = {
        p.item_id: p
        for p in TrilhaProgresso.objects.filter(user=user, item__trilha=trilha)
    }
    result = []
    found_active = False
    for item in items:
        prog = progress.get(item.pk)
        if prog is not None and prog.state == "concluido":
            status = "concluido"
        elif trilha.is_sequential and found_active:
            status = "bloqueado"
        else:
            status = "ativo"
            found_active = True
        result.append((item, status, prog))
    return result


def item_status(item, user):
    """Estado de um item específico (usado para validar conclusão)."""
    for it, status, _ in node_statuses(item.trilha, user):
        if it.pk == item.pk:
            return status
    return "bloqueado"


def potential_xp(item):
    if item.xp_reward is not None:
        return item.xp_reward
    if item.kind == "quiz":
        return item.quiz.questions.count() * XP_PER_CORRECT
    if item.kind == "enquete":
        from apps.enquetes.services import ENQUETE_VOTE_XP  # evita import circular

        return ENQUETE_VOTE_XP
    return 0
