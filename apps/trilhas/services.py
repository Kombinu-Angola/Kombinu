"""
Progresso em Trilhas (SLA §8.4). Regras num só sítio: estado dos nós, estrelas
e conclusão de itens.
"""
from django.db import transaction
from django.utils import timezone

from apps.notificacoes.services import notify_trilha_published

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


# --- Autoria (B1): criar, editar, publicar e gerir itens -------------------


class TrilhaError(Exception):
    """Erro de regra de negócio da autoria; `status` é o HTTP status da resposta."""

    def __init__(self, message, status=400, field=None):
        super().__init__(message)
        self.status = status
        self.field = field

    def as_response_data(self):
        if self.field:
            return {self.field: [str(self)]}
        return {"error": str(self)}


TARGET_NOT_FOUND = "Item não encontrado neste workspace."


def resolve_target(kind, target_id, organizacao, user):
    """
    Devolve o objecto alvo de um item, só se pertencer ao mesmo contexto
    (`organizacao`) da trilha. Inexistente ou de outro contexto dão o mesmo
    erro, para não revelar o que existe noutra escola.
    """
    from apps.contents.models import Content
    from apps.enquetes.models import Enquete
    from apps.quizzes.models import Quiz

    models_by_kind = {"conteudo": Content, "quiz": Quiz, "enquete": Enquete}
    target = (
        models_by_kind[kind].objects.for_context(organizacao).filter(pk=target_id).first()
    )
    if target is None:
        raise TrilhaError(TARGET_NOT_FOUND, field="targetId")
    if kind == "enquete" and target.state == "rascunho" and target.creator_id != user.pk:
        raise TrilhaError(TARGET_NOT_FOUND, field="targetId")
    return target


def resolve_final_exam(quiz_id, organizacao):
    from apps.quizzes.models import Quiz

    if quiz_id is None:
        return None
    quiz = Quiz.objects.for_context(organizacao).filter(pk=quiz_id).first()
    if quiz is None:
        raise TrilhaError(TARGET_NOT_FOUND, field="finalExamId")
    return quiz


def _renumber(trilha, ordered_ids):
    """
    Grava `order` = 1..n pela ordem dada. Duas passagens: o unique
    (trilha, order) não é deferível em SQLite, por isso primeiro afasta todas
    as ordens para valores livres e só depois grava as finais.
    """
    items = TrilhaItem.objects.filter(trilha=trilha)
    offset = (max((i.order for i in items), default=0)) + len(ordered_ids) + 1
    for index, item_id in enumerate(ordered_ids):
        TrilhaItem.objects.filter(pk=item_id).update(order=offset + index)
    for index, item_id in enumerate(ordered_ids, start=1):
        TrilhaItem.objects.filter(pk=item_id).update(order=index)


def _lock(trilha):
    from .models import Trilha

    return Trilha.objects.select_for_update().get(pk=trilha.pk)


_TARGET_FIELD = {"conteudo": "content", "quiz": "quiz", "enquete": "enquete"}


def add_item(trilha, user, data):
    with transaction.atomic():
        trilha = _lock(trilha)
        target = resolve_target(data["kind"], data["target_id"], trilha.organizacao, user)
        last = trilha.items.order_by("-order").values_list("order", flat=True).first()
        return TrilhaItem.objects.create(
            trilha=trilha,
            order=(last or 0) + 1,
            kind=data["kind"],
            **{_TARGET_FIELD[data["kind"]]: target},
            title_override=data.get("title_override", ""),
            summary=data.get("summary", ""),
            minutes=data.get("minutes"),
            xp_reward=data.get("xp_reward"),
        )



def remove_item(item):
    with transaction.atomic():
        trilha = _lock(item.trilha)
        if TrilhaProgresso.objects.filter(item=item).exists():
            raise TrilhaError(
                "Este passo já tem progresso de alunos e não pode ser removido.",
                status=409,
            )
        item.delete()
        remaining = list(trilha.items.order_by("order").values_list("pk", flat=True))
        _renumber(trilha, remaining)


def reorder_items(trilha, item_ids):
    with transaction.atomic():
        trilha = _lock(trilha)
        current = set(trilha.items.values_list("pk", flat=True))
        if len(item_ids) != len(set(item_ids)) or set(item_ids) != current:
            raise TrilhaError(
                "Envia todos os passos da trilha, cada um uma vez.", field="itemIds"
            )
        _renumber(trilha, item_ids)


def delete_trilha(trilha):
    with transaction.atomic():
        trilha = _lock(trilha)
        if TrilhaProgresso.objects.filter(item__trilha=trilha).exists():
            raise TrilhaError(
                "Esta trilha já tem progresso de alunos e não pode ser apagada.",
                status=409,
            )
        trilha.delete()


def set_archived(trilha, archived):
    """Arquivar e desarquivar são idempotentes; a data do 1.º arquivo mantém-se."""
    with transaction.atomic():
        trilha = _lock(trilha)
        if archived and trilha.archived_at is None:
            trilha.archived_at = timezone.now()
        elif not archived:
            trilha.archived_at = None
        trilha.save(update_fields=["archived_at"])
    return trilha


def publish_trilha(trilha):
    with transaction.atomic():
        trilha = _lock(trilha)
        if not trilha.items.exists():
            raise TrilhaError("Adiciona pelo menos um passo antes de publicar.")
        # Os alunos não abrem enquetes em rascunho: o passo ficaria inacessível.
        if trilha.items.filter(kind="enquete", enquete__state="rascunho").exists():
            raise TrilhaError(
                "Publica primeiro as enquetes desta trilha que estão em rascunho."
            )
        if not trilha.is_published:
            trilha.is_published = True
            trilha.save(update_fields=["is_published"])
            notify_trilha_published(trilha)
    return trilha
