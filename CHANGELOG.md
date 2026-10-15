# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não Lançado] - Fase de Expansão B2B/B2C — Fundação multi-tenant

### Adicionado

- **App `tenancy`:** modelos `Organizacao` e `Membership` (papéis `student`/`teacher`/`admin`, ano/faculdade/curso em texto livre). Isolamento **lógico** por FK `organizacao` — `NULL` = marketplace (decisão D1; SLA §9.2 revisto).
- **FK `organizacao` nullable** em `Content`, `Quiz` e `QuizSubmission`. Dados existentes ficam no marketplace sem data migration.
- **Scoping central por workspace:** `OrganizacaoQuerySet.for_context()` e `WorkspaceScopedMixin`. O contexto activo vem do header `X-Workspace` (UUID da organização; ausente ou `marketplace` = B2C) e a pertença é validada contra `Membership` em cada pedido. Objectos de outro contexto devolvem 404.
- **`XPEvent` (app `rankings`):** ledger único de XP, idempotente por `(source_type, source_id)`, com backfill a partir das submissões existentes.
- **`QuizSubmission`:** `attempt`, `correct_count`, `total_questions` e `xp_awarded`. Backfill aproximado (`correct_count = score // 10`; `total_questions` = nº actual de perguntas).
- **Testes de isolamento** entre duas organizações fictícias e o marketplace (SLA §8.3).
- **Enquetes (`apps.enquetes`):** modelos `Enquete`, `EnqueteOpcao`, `EnqueteVoto` e `EnqueteExibicao`. Endpoints em `/api/enquetes/`: criar (forma `SurveyDraft`), listar/detalhe, votar (`optionId`), marcar vista/dispensada e resultados agregados (forma `SurveyResult`, percentagens 0–100). Voto único por utilizador (409 na repetição), XP simbólico de 5 por voto via `XPEvent`, fecho automático ao atingir `sampleTarget`. A API nunca expõe a identidade do votante e a vista do votante omite `decision`.
- **Trilhas (`apps.trilhas`):** modelos `Trilha`, `TrilhaItem` (conteúdo/quiz/enquete, com `CheckConstraint` de alvo único) e `TrilhaProgresso`. `GET /api/trilhas/` e `/api/trilhas/<id>/` na forma `LearningTrail` com `status` (`concluido`/`ativo`/`bloqueado`) e `stars` calculados por utilizador. Itens de quiz e enquete concluem-se ao submeter/votar; itens de conteúdo via `POST /api/trilhas/items/<id>/complete/`. Sem `TrilhaMista` e sem campos de `AdaptiveTrail` (D4/D5).

### Alterado

- **Tentativas múltiplas de quiz (D12):** `unique_together(user, quiz)` substituído por `UniqueConstraint(user, quiz, attempt)`. O XP só é concedido na primeira tentativa; `score` mantém-se como espelho de `xp_awarded`. A repetição deixa de devolver 400.
- **Histórico protegido (R5):** `Content.creator` e `QuizSubmission.quiz` passam de `CASCADE` a `PROTECT`. `DELETE` de conteúdo com submissões devolve 409.
- **Ranking global:** `top_users` devolve `name` (nome de exibição, ou `Utilizador <id>`) em vez de `email`. **Breaking change** para consumidores que liam `email`.

### Corrigido

- **Fugas de acesso (R7):** só o criador pode fazer `update`/`partial_update`/`destroy` de um `Content`; geração e criação manual de quiz exigem que o conteúdo pertença ao utilizador; criar conteúdo numa organização exige papel `teacher` ou `admin`.
- **Submissão com opção inválida** deixava a submissão criada com score 0 (a transacção fazia commit ao devolver 400). Passa a fazer rollback, para não consumir a tentativa nem o XP.

### Dívida conhecida (a tratar na semana seguinte)

- O ranking global continua a somar `score` de todos os contextos; filtro por `organizacao`, paginação e ranking por instituição ficam por fazer.
- `LearnerStatsView`, `LearnerCoursesView` e `CreatorStatsView` não respeitam o workspace activo.
- O ranking e os dashboards ainda leem `QuizSubmission.score`, não o `XPEvent`.
- Enquetes: sem endpoints para publicar/encerrar manualmente (só fecham por `sampleTarget`); `segmentSize` guardado mas sem uso (semântica por confirmar); o gatilho (`trigger`) é só um tipo, sem alvo concreto (D11); **D9 (anonimato) pendente de validação legal**.
- Trilhas: sem endpoints de criação/edição (só admin); limiares de estrelas (50/75/90%) e XP por voto (5) são sugestões por confirmar; minutos do exame final fixos em 15 (como `timeLimit` do quiz); reordenar itens exige duas passagens (unique não deferível em SQLite).

---

## [2.7.0] - Geração de Quiz OpenTDB (10 de Junho 2026)

### Corrigido

- **Encoding incompatível com html.unescape:** Removido `"encode": "url3986"` dos parâmetros da OpenTDB. O encoding padrão da API devolve entidades HTML (`&amp;`, `&#039;`) que o `html.unescape()` já descodifica — com `url3986` o texto ficava com `%20` em vez de espaços.

### Adicionado

- **Perguntas em português com fallback para inglês:** Geração de quiz tenta primeiro `lang=pt`; se a OpenTDB devolver `response_code=1` (sem resultados) ou lista vazia, faz nova chamada sem `lang` para obter perguntas em inglês. Loop de retry extraído para `_call_opentdb(params)` reutilizável.

### Testes

- Adicionado `test_generate_quiz_fallback_to_english`: verifica que a primeira chamada à OpenTDB usa `lang=pt` e que o fallback para inglês é activado quando não há resultados em PT.

---

## [2.6.0] - Estabilização para Demo AngoTic 2026 (10 de Junho 2026)

### Corrigido

- **Sistema de pontos partido:** `QuizSubmission.score` passa a guardar XP (respostas correctas × 10). Threshold de nível ajustado de 1000 para 100 XP — utilizador sobe ao nível 2 após 1 quiz perfeito de 10 perguntas, tornando a progressão visível na demo.
- **Perfil sem pontos e nível:** `UserProfileSerializer` expõe agora `nome` (first + last name com fallback para email), `pontos` (total XP) e `nivel` calculados em tempo real — frontend obtém estes dados directamente no login sem pedidos adicionais.
- **OpenTDB rate limit em demo:** Serviço de geração de quiz implementa retry automático (até 2 tentativas, 2s de espera) quando `response_code=5`. Retorna HTTP 503 com mensagem em PT após esgotar tentativas, em vez de 500 genérico.
- **Backend não arranca sem DATABASE_URL:** `settings.py` usa `sqlite:///db.sqlite3` como fallback quando `DATABASE_URL` não está definida no ambiente.

### Testes

- Adicionados 5 testes para `LearnerStatsView`: nível 1 sem submissões, score como XP, nível 2 após 100 XP, nível 1 abaixo de 100 XP, 401 sem autenticação.
- Adicionados 2 testes de perfil no login: `nome` composto e fallback para email.
- Adicionado teste de rate limit OpenTDB: verifica que `OpenTDBRateLimitError` resulta em 503 com mensagem descritiva.

---

## [2.5.0] - Sprint AngoTic 2026 — Semana 2 (Junho 2026)

### Adicionado

- Endpoint `POST /api/auth/token/refresh/` para renovação de access tokens JWT sem forçar novo login, eliminando sessões a expirar após 60 minutos em produção.

### Corrigido

- `UserProfileSerializer` actualizado para expor `first_name` e `last_name` na resposta do login — dashboard frontend passa a exibir o nome correcto do utilizador.
- `GlobalRankingView` refactorizado de N+1 queries (até 101 por request) para uma única query SQL com JOIN via `.values("user_id", "user__email")`.
- `LearnerCoursesView` substituiu dados hardcoded (`lastAccessed: "2024-03-10"` e thumbnail Unsplash) por dados reais: data da última `QuizSubmission` e `thumbnail` do próprio `Content`.

### Testes

- Adicionados 3 testes de autenticação: refresh com token válido, refresh inválido, e login com verificação de `first_name`/`last_name`.
- Adicionados 8 testes para `LearnerCoursesView`: 401, lista vazia, data real, thumbnail real, fallback de thumbnail, deduplicação e isolamento entre utilizadores.

---

## [2.4.0] - Sprint AngoTic 2026 (Junho 2026)

### Corrigido

- Mapeamento de categorias da Open Trivia DB substituído por constante estática em `quizzes/services.py`, eliminando chamada HTTP extra a cada geração de quiz e prevenindo rate limiting em gerações consecutivas.
- Removidas funções auxiliares `get_opentdb_categories()` e `map_local_category_to_opentdb()` que causavam dupla requisição à API externa.
- Corrigidos typos nos comentários e mensagens de log do serviço de quizzes.

### Adicionado

- Testes completos para `GlobalRankingView` em `rankings/tests.py`, cobrindo autenticação, estrutura da resposta, ordenação por pontuação, cálculo de posição e agregação de múltiplas submissões.

---

## [2.3.0] - Correções Quizzes do MVP (Março 2026)

### Adicionado

- Novo campo genérico `type` na modelagem do `Content` para correta diferenciação tipológica nos formulários Frontend de Vídeos vs Textos vs Quizzes.
- Novo View Customizado `QuizManualCreationView` para suportar inserção de perguntas, opções e validação de pontos provindas da plataforma UI.

### Corrigido

- Sincronização dos Serializadores (`OptionSerializer`, `QuestionSerializer` e `QuizDetailSerializer`) de modo a exporem os campos `id`, `text` e `timeLimit` padronizados, prevenindo bugs de interface do aluno.
- Ajustes de Payload na View `QuizSubmissionView` para retornar os campos `totalPoints`, `xp earned` equivalentes à tipagem do front-end original.
- Alteração no `lookup_field` de `pk` para `id` no `QuizDetailView` evitando a sobreposição 500 ao extrair detalhes por UUID.

---

## [2.2.0] - Otimizações MVP e Preparação para Deploy (Render)

### Adicionado

- Scripts automatizados para deploy `build.sh` no render.
- Suporte para banco de dados via URL com `dj-database-url` para provisionamento no Neon/Render.
- Adição da biblioteca `gunicorn` no `requirements.txt` para produção.

### Corrigido

- Ajuste das permissões e configurações de CORS e ALLOWED_HOSTS no `settings.py`.
- Correção da geração de token no registo.

---

## [2.1.0] - 2026-01-11

### Adicionado

#### 📊 Dashboard Statistics API

- Novos endpoints para estatísticas de usuário em `/api/dashboard/`:
  - `GET /api/dashboard/learner/stats/` - Estatísticas do aprendiz (cursos, pontos, nível, quizzes)
  - `GET /api/dashboard/learner/courses/` - Cursos em que o aprendiz participou
  - `GET /api/dashboard/creator/stats/` - Estatísticas do criador (estudantes, cursos)
- Arquivo `apps/accounts/dashboard_urls.py` criado para organização
- Views `LearnerStatsView`, `LearnerCoursesView`, `CreatorStatsView` em `accounts/views.py`
- Agregação de dados baseada em `QuizSubmission` e `Content` models

---

## [2.0.1] - 2026-01-15

### Corrigido

- Correção do formato de string no logging de erros para Open Trivia DB API.

## [2.0.0] - 2025-12-02

### Adicionado

#### 🎯 Sistema de Conteúdos Educacionais

- App `contents` para gestão de conteúdos educacionais
- Modelo `Content` com suporte a diferentes tipos (text, video, quiz)
- API REST completa para CRUD de conteúdos
- Sistema de permissões personalizadas (criadores podem editar, todos podem visualizar)
- Testes completos (11 testes) para todas as funcionalidades

#### 📝 Sistema de Quizzes

- App `quizzes` para criação e gestão de questionários
- Modelo `Quiz` com relacionamento one-to-one com conteúdos
- Modelo `Question` com múltiplas opções de resposta
- Sistema de submissão e correção automática de quizzes
- Cálculo de pontuação e feedback para usuários
- Serviço `QuizService` para lógica de negócio
- Testes completos (16 testes) incluindo validações e edge cases

#### 🏆 Sistema de Rankings

- App `rankings` para gestão de pontuações e classificações
- Modelo `UserScore` para rastreamento de pontos por usuário
- API para visualização de rankings globais
- Serializers para exposição de dados de ranking

#### 👥 Sistema de Autenticação Aprimorado

- Modelo `CustomUser` com tipos de usuário (Creator/Learner)
- Autenticação JWT com `djangorestframework-simplejwt`
- Endpoints de registro, login e perfil
- Testes completos (9 testes) para autenticação

#### 📚 Documentação da API

- Integração com `drf-spectacular` para OpenAPI 3.0
- Interface Swagger UI interativa (`/api/docs/`)
- Interface ReDoc alternativa (`/api/redoc/`)
- Schema OpenAPI disponível (`/api/schema/`)

#### 🧪 Sistema de Testes

- 36 testes implementados usando pytest-django
- Cobertura completa dos endpoints da API
- Testes de modelos, serializers e views
- Testes de permissões e autenticação
- Configuração pytest com `pytest.ini`

### Alterado

- Migração de autenticação para JWT (anteriormente token-based)
- Estrutura do projeto reorganizada em apps modulares
- Configurações de CORS para suporte a aplicações frontend
- Sistema de paginação configurado (20 itens por página)

### Configurações Técnicas

- **Django**: 4+
- **Django REST Framework**: Integração completa
- **Banco de Dados**: SQLite (desenvolvimento) / PostgreSQL (produção)
- **Autenticação**: JWT com refresh tokens (60min access, 1 dia refresh)
- **CORS**: Configurado com `django-cors-headers`
- **Static Files**: Whitenoise para servir arquivos estáticos
- **Localização**: Português do Brasil (pt-br), Timezone: Africa/Luanda

### Deploy

- Aplicação disponível em produção: [Kombinu](https://kombinu.onrender.com)
- Documentação API em produção: [Kombinu Docs](https://kombinu.onrender.com/api/docs/)

---

## [1.0.0] - Data Anterior

### Adicionado

- Estrutura inicial do projeto Django
- Configuração básica de apps
- Sistema de autenticação inicial
