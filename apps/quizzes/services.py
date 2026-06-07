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


def generate_quiz_from_opentdb(content, difficulty=None, num_questions=10):
    """
    Gera um quiz chamando a API da Open Trivia DB.
    """
    category_id = CATEGORY_MAPPING.get(content.category)
    logger.debug(f"Mapeamento de categoria: {content.category} -> {category_id}")

    params = {
        "amount": num_questions,
        "type": "multiple",
        "encode": "url3986",  # Para lidar com caracteres especiais
    }
    if category_id is not None:
        params["category"] = category_id
    if difficulty:
        params["difficulty"] = difficulty

    api_url = "https://opentdb.com/api.php"
    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()

        if data["response_code"] != 0:
            logger.error(f"Erro da API Open Trivia DB: {data['response_code']}")
            return None

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
    except requests.RequestException as e:
        logger.error(f"Erro ao chamar a API da Open Trivia DB: {e}")
        return None
    except Exception as e:
        logger.error(f"Erro inesperado ao gerar o quiz: {e}")
        return None
