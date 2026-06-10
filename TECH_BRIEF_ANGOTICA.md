# BRIEFING TÉCNICO — BACKEND KOMBINU
## Preparação para a AngoTic 2026 · Demo: 13 de Junho de 2026

---

**Para:** Bernardo Martins · Equipa Kombinu  
**De:** Anderson Cafurica — CTO / Tech Lead  
**Data:** 31 de Maio de 2026  
**Classificação:** Interno · Uso Restrito  

---

## 1. Contexto e Objetivo

A demo da AngoTic 2026 acontece a **13 de Junho de 2026**, em 13 dias. O frontend está em sprint activo e já consome o backend em produção (Render). O nosso objectivo é garantir que o backend está estável, sem dados falsos visíveis, e capaz de suportar ambos os fluxos de demonstração — **Criador** e **Aprendiz** — sem falhas.

Este documento define o estado actual do sistema, os riscos identificados por ordem de severidade, o plano de trabalho das duas próximas semanas, e as responsabilidades de cada membro da equipa.

---

## 2. Estado Actual do Sistema

### 2.1 O que está funcional e testado

| Funcionalidade | Estado |
|---|---|
| Registo e Login com JWT | ✅ Funcional — testes cobrem os cenários principais |
| Listagem e filtro de conteúdos | ✅ Funcional — paginação, filtro por categoria, busca por título |
| Criação de conteúdo (Criador) | ✅ Funcional — permissão `IsCreator` aplicada correctamente |
| Geração de quiz via IA (OpenTDB) | ✅ Funcional — com ressalva (ver risco #4) |
| Criação manual de quiz | ✅ Funcional |
| Submissão de quiz e pontuação | ✅ Funcional — feedback por questão incluído |
| Ranking global | ✅ Funcional — com problema de performance (ver risco #3) |
| Dashboard do Criador (stats) | ✅ Funcional — totalStudents e totalCourses são reais |
| Dashboard do Aprendiz (stats) | ✅ Funcional — coursesCompleted, totalPoints, quizzesTaken são reais |
| Dashboard do Aprendiz (cursos) | ⚠️ Parcial — dados de progresso e datas são mock (ver risco #5) |
| Documentação Swagger / ReDoc | ✅ Disponível em `/api/docs/` e `/api/redoc/` |

### 2.2 Stack actual

- Django 4.2 + Django REST Framework 3.14
- JWT via `djangorestframework-simplejwt` (access: 60 min, refresh: 1 dia)
- PostgreSQL em produção via Render / `dj-database-url`
- Whitenoise para ficheiros estáticos
- Gunicorn em produção
- pytest + pytest-django para testes
- drf-spectacular para documentação OpenAPI 3.0

---

## 3. Riscos Identificados

Os riscos estão ordenados por impacto na demo. Qualquer item marcado como 🔴 pode fazer a demo falhar em público.

---

### 🔴 RISCO 1 — Base de dados expirada em produção

**Problema:** O free trial do PostgreSQL no Render expirou. O backend em produção pode estar a responder com erros 500 ou sem dados.

**Impacto:** Bloqueador total. Nenhuma funcionalidade funciona sem base de dados.

**Solução:** Criar uma nova instância PostgreSQL gratuita no [Supabase](https://supabase.com) ou [Neon](https://neon.tech) (ambos têm planos gratuitos persistentes sem trial a expirar), copiar a nova `DATABASE_URL` para as variáveis de ambiente do Render, e correr as migrações:

```bash
python manage.py migrate
```

**Responsável:** Anderson Cafurica  
**Prazo:** Até 2 de Junho (esta semana)

---

### 🔴 RISCO 2 — Cold start do Render durante a demo

**Problema:** O plano gratuito do Render adormece o servidor após 15 minutos de inactividade. O primeiro pedido depois do sleep demora 30 a 60 segundos — tempo suficiente para a demo parecer quebrada.

**Impacto:** Alto. Numa demo ao vivo, 45 segundos de espera é catastrófico.

**Solução:** Configurar um ping automático gratuito no [cron-job.org](https://cron-job.org) — `GET https://<url-do-render>/api/schema/` a cada 14 minutos. O servidor mantém-se activo sem custo.

**Responsável:** Anderson Cafurica  
**Prazo:** Até 2 de Junho

---

### 🔴 RISCO 3 — Endpoint de refresh de token em falta

**Problema:** O `SIMPLE_JWT` está configurado mas não existe o endpoint `POST /api/auth/token/refresh/` nas URLs. Os access tokens expiram em 60 minutos. Numa demo de 2 horas, o utilizador vai receber erros 401 sem conseguir renovar a sessão.

**Ficheiro a alterar:** `apps/accounts/urls.py`

**Solução — 3 linhas de código:**

```python
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth_register"),
    path("login/", LoginView.as_view(), name="auth_login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),  # ADICIONAR
]
```

**Responsável:** Bernardo Martins  
**Prazo:** Até 3 de Junho

---

### 🟡 RISCO 4 — N+1 queries no ranking global

**Problema:** O `GlobalRankingView` faz um `CustomUser.objects.get(pk=...)` dentro de um loop Python para cada utilizador no top 100 — são até 100 queries separadas à base de dados por cada carregamento do ranking.

**Ficheiro a alterar:** `apps/rankings/views.py`

**Solução:** Substituir o loop por uma anotação SQL com JOIN:

```python
from django.db.models import Sum
from apps.accounts.models import CustomUser

user_scores = (
    QuizSubmission.objects
    .values("user_id", "user__email")           # JOIN em vez de loop
    .annotate(total_score=Sum("score"))
    .order_by("-total_score")[:100]
)
```

Com esta alteração, o ranking inteiro é calculado com **1 query** em vez de 101.

**Responsável:** Bernardo Martins  
**Prazo:** Até 4 de Junho

---

### 🟡 RISCO 5 — Dados mock visíveis na demo (LearnerCoursesView)

**Problema:** O endpoint `GET /api/dashboard/learner/courses/` retorna dados hardcoded:
- `"lastAccessed": "2024-03-10"` — data fixa de 2024
- `"thumbnail": "https://images.unsplash.com/..."` — imagem aleatória
- `"progress": 100` — sempre 100%, independente do estado real

Durante a demo, o Aprendiz vai ver a data "2024-03-10" nos seus cursos — que é visivelmente falso.

**Ficheiro a alterar:** `apps/accounts/views.py` — `LearnerCoursesView`

**Solução:**
- `lastAccessed` → usar `QuizSubmission.submitted_at` (data real da última submissão)
- `thumbnail` → usar `content.thumbnail` se preenchido, senão usar um placeholder fixo do projecto
- `progress` → simplificar: se existe submissão = 100%, senão = 0% (MVP aceitável)

**Responsável:** Bernardo Martins  
**Prazo:** Até 5 de Junho

---

### 🟡 RISCO 6 — OpenTDB pode ser rate-limited durante a demo

**Problema:** Cada geração de quiz faz **2 chamadas HTTP** à API da OpenTDB — uma para listar categorias, outra para obter as perguntas. A OpenTDB limita a 1 pedido por sessão a cada 5 segundos. Se dois Criadores gerarem quizzes em sequência durante a demo, a segunda geração vai falhar.

**Ficheiro a alterar:** `apps/quizzes/services.py`

**Solução:** Fixar o mapeamento de categorias como constante em vez de chamar a API a cada geração. O ID da categoria "Tecnologia" na OpenTDB é `18` (Science: Computers) — valor estável.

```python
# Substituir a chamada dinâmica por constante estática
CATEGORY_MAPPING = {
    "tecnologia": 18,   # Science: Computers — ID estável na OpenTDB
    "negocios": None,   # Qualquer categoria
    "design": None,     # Qualquer categoria
}

def map_local_category_to_opentdb(local_category):
    return CATEGORY_MAPPING.get(local_category)
```

**Responsável:** Anderson Cafurica  
**Prazo:** Até 5 de Junho

---

### 🟢 RISCO 7 — `UserProfileSerializer` não expõe o nome completo

**Problema:** A resposta do login retorna `{id, email, user_type}` mas não inclui `first_name` nem `last_name`. Se o frontend mostra o nome do utilizador no header do dashboard, vai aparecer em branco para utilizadores que forneceram o nome no registo.

**Ficheiro a alterar:** `apps/accounts/serializers.py`

**Solução:** Adicionar os campos ao `UserProfileSerializer`:

```python
class Meta:
    model = CustomUser
    fields = ("id", "email", "user_type", "first_name", "last_name")  # + dois campos
    read_only_fields = ("id", "email", "user_type", "first_name", "last_name")
```

**Responsável:** Bernardo Martins  
**Prazo:** Até 3 de Junho

---

### 🟢 RISCO 8 — Chave com espaço na resposta do quiz

**Problema:** A resposta de submissão de quiz inclui `"xp earned": valor` — uma chave JSON com espaço. Se o frontend acede a este campo, é necessário verificar qual o nome exacto que está a ser consumido.

**Acção:** Confirmar com o frontend se e como este campo é consumido antes de alterar. Se não está a ser usado, renomear para `"xp_earned"` (sem espaço).

**Responsável:** Anderson Cafurica (coordenar com o frontend)  
**Prazo:** Até 3 de Junho

---

## 4. Plano de Sprint

### Semana 1 — Estabilização (1 a 7 de Junho)

| Dia | Tarefa | Responsável |
|---|---|---|
| 1–2 Jun | Nova base de dados (Supabase/Neon) + migrações em produção | Anderson |
| 1–2 Jun | Configurar ping anti-sleep no cron-job.org | Anderson |
| 3 Jun | Adicionar endpoint `/api/auth/token/refresh/` | Bernardo |
| 3 Jun | Expor `first_name` e `last_name` no `UserProfileSerializer` | Bernardo |
| 4 Jun | Corrigir N+1 no `GlobalRankingView` | Bernardo |
| 5 Jun | Corrigir dados mock no `LearnerCoursesView` | Bernardo |
| 5 Jun | Corrigir mapeamento de categorias OpenTDB (constante estática) | Anderson |
| 6–7 Jun | Escrever testes para `GlobalRankingView` (actualmente vazio) | Anderson |

### Semana 2 — Polimento e Preparação da Demo (8 a 12 de Junho)

| Dia | Tarefa | Responsável |
|---|---|---|
| 8–9 Jun | Script de seed de dados demo (`manage.py seed_demo`) | Anderson |
| 8–9 Jun | Registar modelos no Django Admin (CustomUser, Content, Quiz) | Bernardo |
| 10 Jun | `pytest` completo — todos os testes têm de passar | Ambos |
| 11 Jun | Smoke test end-to-end: fluxo Criador completo no Render | Bernardo |
| 11 Jun | Smoke test end-to-end: fluxo Aprendiz completo no Render | Anderson |
| **12 Jun** | **FREEZE — nenhuma alteração ao código após as 23h** | **Ambos** |

---

## 5. Definição de "Pronto"

Uma tarefa só é considerada concluída quando:

1. ✅ O `pytest` passa sem erros (`pytest --tb=short`)
2. ✅ O endpoint foi testado manualmente no Render (não no localhost)
3. ✅ Nenhuma regressão foi introduzida nos testes existentes

---

## 6. Checklist de Prontidão — Dia 12 de Junho

Antes do freeze das 23h do dia 12, verificar todos os pontos:

- [ ] `pytest` sem falhas — output limpo
- [ ] Base de dados de produção activa e acessível
- [ ] `/api/auth/login/` responde em < 500ms no Render
- [ ] `/api/auth/token/refresh/` funciona e retorna novo access token
- [ ] `/api/rankings/global/` responde em < 1 segundo
- [ ] `/api/quizzes/contents/{id}/generate-quiz/` gera quiz completo via OpenTDB
- [ ] `/api/dashboard/learner/courses/` mostra datas reais (não "2024-03-10")
- [ ] Dashboard do Aprendiz mostra o nome do utilizador correctamente
- [ ] Servidor não adormece durante 30+ minutos (ping configurado)
- [ ] Base de dados tem dados de demo pré-carregados (conteúdos, quizzes, utilizadores)
- [ ] Fluxo Criador testado ao vivo: registo → criar conteúdo → gerar quiz
- [ ] Fluxo Aprendiz testado ao vivo: registo → ver conteúdo → fazer quiz → ver ranking

---

## 7. O que fica para depois da AngoTic

Os seguintes itens foram identificados mas são deliberadamente excluídos do âmbito desta sprint para não introduzir risco desnecessário antes da AngoTic 2026:

| Item | Justificação |
|---|---|
| Logout com invalidação de token (blacklist JWT) | Requer `simplejwt.token_blacklist` e migração; não visível na demo |
| Password reset / "Esqueci a senha" | Não pedido pelo frontend neste sprint |
| Modelo de enrollment e progresso real | Infra para a fase seguinte do produto |
| Tags de conteúdo como many-to-many | Migração arriscada; CSV funciona para o MVP |
| Remover `drf-yasg` do requirements (não usado) | Cosmético; sem impacto funcional |
| Registar modelos no Django Admin | Útil mas não crítico para a demo |
| Média de avaliações e receita do Criador | Funcionalidade de fase seguinte |

---

## 8. Comunicação

- **Canal de coordenação:** a definir pela equipa (WhatsApp, Slack, Discord)
- **Bloqueadores:** reportar ao Anderson no mesmo dia — não aguardar até ao dia seguinte
- **PRs:** cada tarefa deve ter o seu próprio pull request com descrição clara; nenhum PR é feito merge sem o `pytest` verde
- **Dúvidas sobre o frontend:** coordenar directamente com a equipa frontend antes de alterar qualquer contrato de API (campos, nomes de chaves, estrutura de resposta)

---

*Documento preparado por Anderson Cafurica — CTO / Tech Lead, Kombinu*  
*Versão 1.0 · 31 de Maio de 2026*
