# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não Lançado] - Auth institucional (6/6): gestão de membros

### Adicionado

- **`GET /api/tenancy/members/`:** membros da organização do `X-Workspace`, só para o admin dela, paginado, com filtros `role`, `is_active` e `search` (número de aluno ou nome). O email técnico nunca sai (`email: null`); o `first_name` usa o número de aluno como fallback.
- **`POST /api/tenancy/members/<id>/deactivate/` e `/reactivate/`** (D13): só a pertença muda; a conta e o XP mantêm-se. Um admin não se desactiva a si próprio, e a organização nunca fica sem admin activo (`select_for_update`). Repetir a acção não muda nada nem duplica a auditoria.
- **`POST /api/tenancy/members/<id>/reset-password/`** (D9): password temporária nova (`secrets`, 7 dias), `must_change_password` e `password_changed_at` gravados juntos (revoga as sessões). Mostrada uma vez, com `Cache-Control: no-store`. Throttle `provisioning`.
- **`AuditoriaMembro`** (migração `tenancy/0005`, aditiva): regista o reset, a desactivação e a reactivação (organização, autor, pertença, acção, data). Só leitura no admin.

### Segurança

- **O reset só vale para contas geridas só por esta organização:** contas provisionadas por ela e sem pertença a outra organização. A password é da conta, por isso o admin de uma escola não pode tomar uma conta que também pertence a outra escola ou ao marketplace. O admin também não faz reset a si próprio (400; usa a troca de password).
- Uma pertença de outra organização dá 404 pelo próprio workspace (não revela que existe) e 403 pelo workspace alheio.

### Testes

- 13 testes novos (`apps/tenancy/test_gestao.py`). Isolamento:
  - listagem só da própria escola;
  - acções sobre um membro de outra escola → 404 e 403, sem auditoria;
  - professor e não-membro → 403.
- Também: auditoria, idempotência, perda de acesso ao workspace, auto-desactivação, último admin, e reset com revogação das sessões e login com a nova password.
- Contas não geridas só pela escola → 403. Este teste falha sem a regra.

---

## [Não Lançado] - `X-Workspace` no schema da API

### Adicionado

- **O header `X-Workspace` passa a estar documentado no OpenAPI/Swagger** em todas as operações com scoping por workspace (25: conteúdos, quizzes, ranking, dashboards, trilhas, enquetes, organizações), com a descrição do valor (UUID da organização ou `marketplace`) e dos erros (400, 403, 404). Os endpoints de autenticação não o têm. Implementado com `apps.tenancy.schema.WorkspaceAutoSchema` (`DEFAULT_SCHEMA_CLASS`), que acrescenta o parâmetro às views com `WorkspaceScopedMixin`. O resto do schema e os avisos do drf-spectacular não mudam.
- README: secção sobre o `X-Workspace`.

### Testes

- Header presente em seis endpoints com scoping e ausente no login e no registo.

---

## [Não Lançado] - Auth institucional (5/6): provisionamento em lote

### Adicionado

- **`POST /api/tenancy/members/bulk/`** (D3 = P2, D4): o admin da organização do `X-Workspace` activo cria contas em lote: `{ dry_run, rows: [{ student_code, first_name, last_name, role, academic_year, faculty, course, email }] }`.
  - **Tudo ou nada:** se alguma linha falhar, nada é criado e a resposta `400 { errors: [{ row, student_code, errors }] }` traz o detalhe. Com `dry_run`, só valida (`200`).
  - Cada conta nasce na mesma transacção com a `Membership` (papel e dados académicos, `provisioned_by`/`provisioned_at`) e a auditoria em `ProvisionamentoLote`.
  - **Password temporária** (D5): gerada com `secrets`, 10 caracteres sem ambíguos, válida 7 dias, troca obrigatória no 1.º acesso. Só aparece nesta resposta (com `Cache-Control: no-store`); não é gravada em claro nem registada em logs. `password` e `password_changed_at` são gravados juntos.
  - O `student_code` é normalizado antes de qualquer validação ou escrita, e só aceita letras, números, `-`, `_`, `/` e `.`, porque também forma o email técnico `<aluno>@<escola>.kombinu.invalid`.
  - Recusa números repetidos no lote ou já existentes na organização, emails já registados (D12), o domínio técnico e emails repetidos.
  - O nome de exibição é o número de aluno quando a escola não manda nome.
- **Limite do lote configurável:** `PROVISIONING_MAX_ROWS` (20 por omissão; ver `.env.example`). Cada conta custa um hash PBKDF2 (cerca de 5,4 s medidos na máquina de desenvolvimento) e o lote tem de caber no timeout do worker. O valor final (D4 previa 100) depende de um benchmark no servidor. Throttle `provisioning`: 30/hora por utilizador (provisório).
- **`manage.py criar_admin_organizacao <slug|código> --email …`:** cria o 1.º admin de uma organização (D3, bootstrap), com password temporária mostrada uma vez na saída do comando.

### Testes

- 17 testes novos (`apps/tenancy/test_provisionamento.py`). Isolamento:
  - o admin da escola A com `X-Workspace` da escola B → 403;
  - marketplace → 403;
  - professor, aluno e admin inactivo → 403;
  - cada admin só cria na sua escola.
- Também: lote atómico, erros por linha, `dry_run`, limite do lote, login institucional da conta criada, email real opcional, passwords fora dos logs e o comando do 1.º admin.

---

## [Não Lançado] - Auth institucional (4/6): login, troca obrigatória e troca de password

### Adicionado

- **`POST /api/auth/institutional/login/`** (D1, D10): `{ school_code, student_code, password }`. `school_code` é o `Organizacao.code` de 6 caracteres, não o UUID. Devolve o mesmo envelope do login por email. Qualquer falha (escola inexistente ou inactiva, aluno inexistente, password errada, conta inactiva, password temporária expirada) devolve o mesmo `401 { "error": "Invalid credentials." }`, e o hash corre mesmo quando a conta não existe (S2). Throttling: 30/min por IP e 5/min por par (escola, aluno).
- **`POST /api/auth/password/change/`** (D6): `{ current_password, new_password }` → `{ access_token, refresh_token }` novos. Grava `password` e `password_changed_at` juntos, o que revoga as sessões anteriores (D7), e desliga `must_change_password`. Erros 400 nas mesmas chaves. Limite: 10/hora por utilizador (provisório).
- **Gate de troca obrigatória** (D6): com `must_change_password`, qualquer endpoint autenticado devolve `403 { "detail", "code": "password_change_required" }`, excepto a troca de password e o refresh.
- **`user` nos dois logins:** `must_change_password` e `memberships: [{ organizacao_id, name, code, role }]` (só activas, em organizações activas; D13).

### Alterado

- **`user.email` é `null` nas contas institucionais** (email técnico `*.kombinu.invalid`), e o email técnico nunca sai da API. **`first_name` e `nome`** usam o `student_code` como fallback nessas contas.

### Segurança

- **As contas institucionais só entram pelo login institucional:** `POST /api/auth/login/` recusa emails técnicos (`*.kombinu.invalid`, que são previsíveis) com o mesmo `401 Invalid credentials.`. Sem isto, a password temporária expirada continuava a dar acesso pelo login por email, e o throttling por conta tinha orçamento duplicado.
- **Expiração da password temporária numa regra única** (`temp_password_expired`), aplicada aos dois logins.
- **O registo aberto recusa o domínio técnico:** `POST /api/auth/register/` com um email `*.kombinu.invalid` → `400`. Impede que alguém ocupe antecipadamente o email técnico de um aluno e bloqueie o seu provisionamento.

### Corrigido

- **Login e registo com um token antigo no header:** `POST /api/auth/login/` e `POST /api/auth/register/` devolviam `401 token_not_valid` quando o pedido trazia um Bearer expirado ou inválido, mesmo com credenciais certas. Passam a ignorar o header `Authorization` (`authentication_classes = []`). O refresh já não autenticava.

### Testes

- 20 testes novos (`apps/accounts/test_institutional.py`). Isolamento:
  - o mesmo `student_code` em duas escolas resolve pela escola;
  - o código de uma escola não autentica alunos de outra;
  - `memberships` só mostra a própria escola.
- Também: todas as falhas com o mesmo 401, o UUID recusado como código, escola, conta ou password temporária inactivas ou expiradas, aluno que saiu, nome de exibição, Bearer antigo no login, gate em vários endpoints, refresh permitido durante a troca pendente, troca com revogação e validações.

---

## [Não Lançado] - Auth institucional (2/6, complemento): rotação do refresh

### Alterado

- **Rotação do refresh token (D7):** `POST /api/auth/token/refresh/` passa de `{ "access" }` a `{ "access", "refresh" }` (`ROTATE_REFRESH_TOKENS = True`). **Breaking** para clientes que ignoravam a resposta; o frontend já guarda o refresh novo (contrato aprovado pelo CTO).
- Sem blacklist: o refresh anterior continua válido até expirar (1 dia), salvo se a password for trocada depois de ele ser emitido (`password_changed_at`). A blacklist acrescentaria uma app e tabelas, e fica para quando for precisa a revogação remota.

### Testes

- Resposta `{access, refresh}` com tokens utilizáveis; refresh antigo ainda válido sem blacklist; refresh rodado revogado por troca de password.

---

## [Não Lançado] - Autenticação Bearer no Swagger

### Corrigido

- **`/api/docs/` não mostrava autenticação:** `SPECTACULAR_SETTINGS["AUTHENTICATION_WHITELIST"]` só tinha `TokenAuthentication`, que a API não usa. Passa a ter a autenticação JWT da API. O schema ganha o esquema `jwtAuth` (`http`, `bearer`, `JWT`), e o Swagger passa a mostrar o botão "Authorize" e o cadeado nos endpoints protegidos.
- Extensão de schema para `PasswordAwareJWTAuthentication` (`apps/accounts/schema.py`): a do drf-spectacular só reconhece a classe original do simplejwt.
- `POST /api/auth/login/` e `POST /api/auth/register/` passam de `permission_classes = []` a `[AllowAny]`. O comportamento é o mesmo; no schema ficam marcados como públicos (autenticação opcional) em vez de exigirem JWT.

---

## [Não Lançado] - Auth institucional (2/6): revogação de sessões

### Segurança

- **Trocar a password invalida as sessões anteriores (D7):** um access ou refresh token emitido antes de `CustomUser.password_changed_at` passa a ser recusado com `401` e `code: "token_not_valid"` (o formato padrão do simplejwt), em qualquer endpoint autenticado e em `POST /api/auth/token/refresh/`. Sem tabelas novas nem blacklist.
- `password_changed_at` é actualizado por `set_password` em contas já existentes (troca pela API, pelo admin ou por reset). A criação da conta não conta como troca, e o rehash automático do hasher no login grava só o campo `password`, por isso não revoga sessões.
- A comparação é feita ao segundo (resolução do `iat`): os tokens emitidos no mesmo segundo da troca continuam válidos.

### Alterado

- Autenticação por omissão: `apps.accounts.authentication.PasswordAwareJWTAuthentication` (subclasse do `JWTAuthentication` do simplejwt).
- A rotação do refresh token (também D7) fica para depois de o contrato com o frontend fechar.

### Testes

- Tokens sem troca de password, access e refresh anteriores à troca (`401 token_not_valid`), tokens no mesmo segundo, novo login depois da troca, `set_password` só em contas existentes e rehash sem revogação.

---

## [Não Lançado] - Auth institucional (3/6): papel de criador

### Alterado

- **`IsCreator` e criação de quizzes usam o papel no workspace activo (D11):** no marketplace continua a ser preciso `user_type="creator"`; numa organização conta o papel `teacher` ou `admin` na `Membership`, seja qual for o `user_type`. Afecta `POST /api/contents/`, `POST /api/quizzes/contents/<id>/generate-quiz/` e `POST /api/quizzes/contents/<id>/manual-quiz/`.

### Corrigido

- Um professor (`teacher`) com `user_type="learner"` levava 403 ao criar conteúdo ou quiz na própria escola.
- Um utilizador `creator` despromovido a `student` numa escola continuava a poder criar quizzes sobre o seu conteúdo dessa escola.

### Testes

- Isolamento: professor `learner` cria na sua escola, mas não noutra escola nem no marketplace; criador despromovido não cria quiz (manual nem gerado); no marketplace mantém-se a exigência de `creator`.

---

## [Não Lançado] - Auth institucional (1/6): modelos

### Adicionado

- **`Organizacao.code`:** código curto da escola para o login institucional (D2), com 6 caracteres de um alfabeto sem ambíguos (sem `0/O`, `1/I`), único e gerado automaticamente. As organizações existentes recebem código numa migração de dados (`tenancy/0003`), entre a criação do campo nulável (`0002`) e a passagem a obrigatório e único (`0004`).
- **`Membership.student_code`:** número de aluno atribuído pela escola, normalizado (maiúsculas, sem espaços) e único por organização. O mesmo número noutra escola é outra pessoa. `provisioned_by` e `provisioned_at` para auditoria.
- **`CustomUser`:** `must_change_password`, `password_changed_at` e `temp_password_expires_at` (D5–D7), desligados por omissão.
- **`ProvisionamentoLote`:** registo de cada lote de contas criado por um admin (organização, autor, data, nº de contas). `PROTECT` sobre a organização; só leitura no admin.

Sem endpoints nem mudanças de contrato nesta etapa (ver `docs/relatorio-auth-institucional.md` §7.2).

---

## [Não Lançado] - Suite de testes rápida e teste instável

### Alterado

- **Hasher rápido só nos testes:** novo `core/settings_test.py`, que herda de `core/settings.py` e só troca `PASSWORD_HASHERS` por MD5; o `pytest.ini` passa a usá-lo. `manage.py`, WSGI e ASGI continuam em `core.settings`, por isso produção mantém o PBKDF2. Suite completa (167 testes, mesma máquina e mesmo venv): **47m00s → 1m40s** no tempo do pytest.

### Corrigido

- **Teste instável `test_other_school_users_never_leak_into_response`:** procurava `"99"` na resposta inteira e falhava em cerca de 11% das execuções, quando o UUID aleatório do workspace continha `99`. Passa a comparar `user_id`, `total_score`, `user_position` e `count`.

---

## [Não Lançado] - Django 5.2 LTS

### Alterado

- **Django 4.2 → 5.2 LTS** em `requirements.txt` (`Django>=5.2,<5.3`). O 4.2 está fora de suporte desde Abril de 2026; o 5.2 tem suporte até Abril de 2028. As outras dependências ficam alinhadas com o ambiente onde a suite já passava: DRF ≥3.16, simplejwt ≥5.5, django-cors-headers ≥4.9, drf-spectacular ≥0.28, django-filter 25.x, whitenoise ≥6.11, psycopg2-binary ≥2.9.10 (rodas para Python 3.13), dj-database-url ≥2.3, pytest 9, pytest-django ≥4.11, black 25.
- **gunicorn 21 → 23** (o 21 tem a vulnerabilidade de *request smuggling* CVE-2024-1135, corrigida no 22).
- **Python 3.13 fixado** em `.python-version`, que o Render lê no build.
- **`STATICFILES_STORAGE` → `STORAGES`:** o setting antigo deixou de existir no Django 5.1 e seria ignorado em silêncio, e o whitenoise perdia a compressão e o manifest. O comportamento em produção mantém-se.
- `TrilhaItem`: `CheckConstraint(check=…)` → `condition=…` (o `check` sai no Django 6.0). Sem migração nova.

### Corrigido

- **`develop` não fazia deploy no Render:** a migração `trilhas/0001_initial` usa `CheckConstraint(condition=…)`, que não existe no Django 4.2, e o `migrate` do `build.sh` falhava com `TypeError`.

---

## [Não Lançado] - Organização do conteúdo só de leitura

### Segurança

- **Fuga entre tenants em `PUT`/`PATCH /api/contents/<id>/`:** o campo `organizacao` era editável, e o criador podia mover o seu conteúdo para uma organização onde não tem `Membership` (ou para o marketplace). Passa a ser só de leitura: vem sempre do workspace activo na criação e é ignorado no corpo de `POST`, `PUT` e `PATCH`. No schema da API passa a `readOnly` na resposta e sai de `ContentRequest`/`PatchedContentRequest`.
- Revisto o mesmo risco em Quiz, Trilha e Enquete: não há endpoints de edição, os serializers não expõem `organizacao` para escrita e a criação usa sempre o workspace activo.

### Testes

- Isolamento: criar com `organizacao` de outra escola no corpo, mover por `PATCH` (outra escola e `null`) e por `PUT`. O conteúdo fica na escola de origem e não aparece na outra escola nem no marketplace.

---

## [Não Lançado] - Ranking por workspace (R4)

### Alterado

- **Ranking (`GET /api/rankings/global/`):** passa a ler o ledger `XPEvent` em vez de `QuizSubmission.score` e a respeitar o header `X-Workspace`. O ranking escolar já não soma o XP do marketplace nem de outra organização; cada contexto tem a sua tabela.
- **Cálculo na base de dados:** posição por `RANK()` (empates partilham posição) e posição do utilizador por agregação com `HAVING`, em vez de carregar todos os utilizadores em Python.
- **Paginação:** `?page=` e `?page_size=` (máx. 100, por omissão 100). A resposta mantém `top_users` e `user_position` e acrescenta `count`, `page`, `page_size`, `total_pages` e `workspace`.
- **Dashboards (`LearnerStats`, `LearnerCourses`, `CreatorStats`):** respeitam o workspace activo. `totalPoints` é o XP do workspace; `currentLevel` e os `pontos`/`nivel` do perfil vêm da carteira global (XPEvent de todos os contextos).
- **XP de enquetes** passa a contar no ranking e nos pontos, por viver no mesmo ledger.

### Corrigido

- O ranking e os dashboards ignoravam o workspace activo e podiam misturar XP e dados de organizações diferentes (R4/R7).

### Testes

- Isolamento de ranking e dashboards entre duas escolas fictícias e o marketplace, empates, paginação, limite de queries e fonte do XP.

---

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

### Dívida conhecida

- Enquetes: sem endpoints para publicar/encerrar manualmente (só fecham por `sampleTarget`); `segmentSize` guardado mas sem uso (semântica por confirmar); o gatilho (`trigger`) é só um tipo, sem alvo concreto (D11); **D9 (anonimato) pendente de validação legal**.
- Trilhas: sem endpoints de criação/edição (só admin); limiares de estrelas (50/75/90%) e XP por voto (5) são sugestões por confirmar; minutos do exame final fixos em 15 (como `timeLimit` do quiz); reordenar itens exige duas passagens (unique não deferível em SQLite).

---

## [2.7.2] - Login com token antigo no header (Não Lançado)

### Corrigido

- **`POST /api/auth/login/` e `POST /api/auth/register/` recusavam pedidos com um Bearer expirado ou inválido** no header `Authorization` (`401 token_not_valid`), mesmo com credenciais certas, porque a autenticação JWT corria antes da view. Um cliente que mantivesse um token velho ficava sem conseguir entrar. Passam a não autenticar (`authentication_classes = []`). O `POST /api/auth/token/refresh/` já não autenticava (simplejwt).
- Versão da API no schema (`SPECTACULAR_SETTINGS["VERSION"]`) passa a `2.7.2`; estava em `2.7.0`.

### Testes

- Login, registo e refresh com um Bearer inválido no header → sucesso; um endpoint protegido continua a recusá-lo (401).

---

## [2.7.1] - Hotfix de segurança em produção (Não Lançado)

### Segurança

- **HTTPS atrás do proxy do Render:** com `DEBUG=False`, a app passa a confiar em `X-Forwarded-Proto` (`SECURE_PROXY_SSL_HEADER`), o que permite desligar o `DEBUG` em produção sem ciclo de redirecção. Acrescenta HSTS (`SECURE_HSTS_SECONDS`, 3600 por omissão, sem subdomínios nem preload); cookies seguras mantêm-se.
- **CORS fechado por omissão:** `CORS_ALLOW_ALL_ORIGINS` passa a `False` por omissão; as origens permitidas vêm de `CORS_ALLOWED_ORIGINS`. **Breaking:** em produção é obrigatório definir `CORS_ALLOWED_ORIGINS` antes do deploy.
- **Inflação de XP na submissão de quiz:** respostas repetidas à mesma pergunta contavam várias vezes (ex.: 1 pergunta respondida 100 vezes dava 250 XP). A submissão com perguntas repetidas passa a ser rejeitada com `400` e não cria submissão.
- **Throttling** em `POST /api/auth/login/` (30/min por IP e 5/min por conta), `POST /api/auth/register/` (10/hora por IP) e `POST /api/auth/token/refresh/` (30/min por IP). Acima do limite: `429`. Valores provisórios; a cache é local a cada processo. `DRF_NUM_PROXIES` opcional para ler o IP do cliente em `X-Forwarded-For`.

### Testes

- Rejeição de respostas repetidas na submissão de quiz.
- Throttling de login (por IP e por conta), registo e refresh; `conftest.py` limpa a cache entre testes.

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
