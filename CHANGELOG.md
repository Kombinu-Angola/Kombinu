# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

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
