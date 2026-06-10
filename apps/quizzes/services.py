import time
import requests
import html
from django.db import transaction
from .models import Option, Question, Quiz

import logging

logger = logging.getLogger(__name__)

# IDs estáticos da Open Trivia DB — https://opentdb.com/api_category.php
# None = sem filtro de categoria ("Any Category")
CATEGORY_MAPPING = {
    "tecnologia": 18,  # Science: Computers
    "negocios": None,
    "design": None,
}

OPENTDB_MAX_RETRIES = 2
OPENTDB_RETRY_DELAY = 2  # segundos entre tentativas quando rate limited


class OpenTDBRateLimitError(Exception):
    """Lançada quando a OpenTDB retorna response_code 5 após todas as tentativas."""
    pass


def generate_quiz_from_opentdb(content, difficulty=None, num_questions=10):
    """
    Gera um quiz chamando a API da Open Trivia DB.
    Faz retry automático (até OPENTDB_MAX_RETRIES vezes) quando a API
    retorna rate limit (response_code 5).
    """
    category_id = CATEGORY_MAPPING.get(content.category)
    logger.debug(f"Mapeamento de categoria: {content.category} -> {category_id}")

    params = {
        "amount": num_questions,
        "type": "multiple",
        "encode": "url3986",
    }
    if category_id is not None:
        params["category"] = category_id
    if difficulty:
        params["difficulty"] = difficulty

    api_url = "https://opentdb.com/api.php"

    for attempt in range(OPENTDB_MAX_RETRIES + 1):
        try:
            response = requests.get(api_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data["response_code"] == 0:
                break  # sucesso — sai do loop de retry

            if data["response_code"] == 5:
                if attempt < OPENTDB_MAX_RETRIES:
                    logger.warning(
                        f"OpenTDB rate limit (tentativa {attempt + 1}/{OPENTDB_MAX_RETRIES + 1}). "
                        f"A aguardar {OPENTDB_RETRY_DELAY}s..."
                    )
                    time.sleep(OPENTDB_RETRY_DELAY)
                    continue
                logger.error("OpenTDB rate limit excedido após todas as tentativas.")
                raise OpenTDBRateLimitError("Too many requests to OpenTDB")

            logger.error(f"Erro da API Open Trivia DB: response_code={data['response_code']}")
            return None

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar a API da Open Trivia DB: {e}")
            return None

    try:
        questions_data = data["results"]

        with transaction.atomic():
            quiz = Quiz.objects.create(
                title=f"Quiz: {content.title}", content=content
            )

            for q_data in questions_data:
                question_text = html.unescape(q_data["question"])
                correct_answer = html.unescape(q_data["correct_answer"])
                incorrect_answers = [
                    html.unescape(ans) for ans in q_data["incorrect_answers"]
                ]

                question_obj = Question.objects.create(
                    quiz=quiz, question_text=question_text
                )

                Option.objects.create(
                    question=question_obj, text=correct_answer, is_correct=True
                )

                for inc_ans in incorrect_answers:
                    Option.objects.create(
                        question=question_obj, text=inc_ans, is_correct=False
                    )

            return quiz

    except Exception as e:
        logger.error(f"Erro inesperado ao gerar o quiz: {e}")
        return None
