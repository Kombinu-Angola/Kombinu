# KOMBINU — Auditoria do backend e proposta de modelagem (Fase 1, SLA §9.3)

**Estado:** versão final para entrega a Bernardo e Carlos (ERD + dicionário). Decisões D1–D13 fechadas pelo CTO (ver §4); **D9 com validação legal ainda pendente**. Nenhum código, model ou migration foi escrito.
**Base:** SLA v2.0.0 (§8, §9, §10), `arquitetura_atual_kombinu.md` (v2.7.0), `proposta_modelagem_bd.docx`, código actual de `apps/accounts|contents|quizzes|rankings`, migrations `0001`, `Kombinu API.yaml` (só os paths foram comparados com as urls; schemas não foram comparados campo a campo).
**Contrato frontend:** as formas TypeScript colocadas no pedido (`TrailNode`, `LearningTrail`, `AdaptiveStep`, `AdaptiveTrail`, `SurveyDraft`, `SurveyResult`). Não li o repositório do frontend.

---

## 0. Resumo executivo

1. **Conflito de direcção resolvido (D1):** o SLA §9.2 dizia "schema-per-tenant"; o CTO decidiu **isolamento lógico** (FK `organizacao`, `NULL` = marketplace), como na proposta do `.docx`. O §9.2 do SLA será corrigido na nota de revisão v2.0.1 (emitida à parte).
2. **Os documentos descrevem um modelo que não é o do código.** `arquitetura_atual_kombinu.md` afirma que `CustomUser`, `QuizSubmission` e `QuizAnswer` têm PK UUID. Nas migrations são `BigAutoField` (inteiro). Só `Content`, `Quiz`, `Question` e `Option` são UUID.
3. **`QuizSubmission.score` guarda só XP.** Não há acertos nem total de perguntas, logo não dá para calcular `stars`, `initialAccuracy` nem `failureRate`, que o frontend já espera.
4. **A app `rankings` não tem modelos** e o endpoint carrega todos os utilizadores em memória, expondo emails. Isto tem de ser redesenhado, porque ranking por instituição é entregável da Fase 2.
5. **`AdaptiveTrail` fica fora do âmbito desta fase (D5).** Não está na lista do SLA §9.3 nem nos entregáveis [ALTA] da Fase 3, apesar de já ter ecrã no frontend. Nenhum campo ou modelo dedicado é fechado aqui; ver §2.4 para o que deve ser mantido compatível.
6. **Já hoje há fugas de acesso** (qualquer autenticado pode editar/apagar qualquer `Content`). Em multi-tenant isto passa de bug a incidente.

---

## 1. O que existe vs. o que falta

### 1.1 Estado actual (verificado no código)

| Modelo | PK real | Notas relevantes para esta fase |
|---|---|---|
| `accounts.CustomUser` | **BigAutoField** | `user_type` ∈ {creator, learner} global; sem perfil (ano, faculdade, curso); sem relação com organização |
| `contents.Content` | UUID | `creator` FK CASCADE; `category` com 3 choices fixas; `type` string livre (default `"text"`, sem choices); `duration` CharField livre; `tags` CSV; sem organização, sem visibilidade |
| `quizzes.Quiz` | UUID | `OneToOne` com `Content` (um quiz só existe agarrado a um conteúdo) |
| `quizzes.Question` / `Option` | UUID | `Question` sem tema/tópico; `Option.is_correct` |
| `quizzes.QuizSubmission` | **BigAutoField** | `score` = XP (acertos × 10, constante no código da view); `unique_together(user, quiz)`; sem acertos/total/duração |
| `quizzes.QuizAnswer` | **BigAutoField** | submission + question + selected_option |
| `rankings` | — | `models.py` vazio; ranking calculado em `GlobalRankingView` por `Sum("score")` |

Também não existem: progresso/matrícula, notificações, medalhas, qualquer noção de contexto (workspace) na API ou no JWT.

### 1.2 Lacunas por entidade pedida

| Entidade (SLA §9.3) | Existe? | O que falta |
|---|---|---|
| **Organizacao/Tenant** | Não | Modelo novo + FK nullable em `Content` (e em `Quiz`, `Trilha`, `Enquete`, submissões, ranking). `NULL` = marketplace público |
| **Workspace/Membership** | Não | `Membership` (user × organização, papel, atributos académicos). "Workspace" como entidade própria tem pouco a acrescentar — ver D2 |
| **Trilha** | Não | Modelo novo (+ progresso por utilizador, que a proposta deixou como pergunta aberta nº 3 e o frontend já exige: `status`, `stars`) |
| **TrilhaItem** | Não | Junção com `order` e tipo; referência a Content/Quiz/Enquete |
| **Enquete** | Não | Modelo novo; sem equivalente reaproveitável (`Quiz` tem `is_correct`, enquete não) |
| **EnqueteOpcao** | Não | Novo; precisa de `valor` para escalas |
| **EnqueteVoto** | Não | Novo; mais uma tabela de exibição/dispensa (o frontend mede `shown` e `dismissed`) — ver §2.3 |
| Papéis por organização | Não | `user_type` global não serve: a mesma pessoa pode ser *learner* na escola e *creator* no marketplace |
| Ledger de XP | Não | Hoje XP só existe como soma de `QuizSubmission.score`. Enquetes com XP, multiplicador adaptativo e ranking por instituição exigem registo próprio |
| Notificações por workspace (§9.4) | Não | Nem a tabela de notificações existe |

### 1.3 Divergências entre documentos que precisam de decisão

| Tema | SLA | `proposta_modelagem_bd.docx` | Proposta deste relatório |
|---|---|---|---|
| Isolamento | Schema-per-tenant (§9.2) | FK lógica `institution` | D1 |
| Nomes | `Organizacao`, `Trilha`, `Enquete…` | `Institution`, `LearningPath`, `Poll…` | Nomes do SLA (é o documento aprovado por ti) |
| Enquete | Pergunta única + opções + voto (§10) | `Poll` → N `PollQuestion` → opções → `PollAnswer` | Pergunta única (o frontend também é pergunta única) |
| Trilha Mista | Modelo e endpoints próprios (§10, §8.2 cita `TrilhaMista`) | `is_mixed` boolean | Sem modelo `TrilhaMista`: uma só `Trilha` com itens de tipos diferentes (D4) |
| Tipo de item | conteúdo/quiz/enquete (§9.3) | só `Content` | O do SLA |
| Código em inglês (§8.1) vs. nomes em PT (§9.3) | contraditório | — | D6 |

---

## 2. Proposta de campos — Trilha e Enquete

Convenção: campos de BD em inglês, como em §8.1 e como as chaves do contrato TS (`title`, `summary`, `minutes`…). Valores de enum **exactamente como o frontend** (`"concluido"`, `"fim-simulado"`…), para não haver tradução. PKs novas em UUID; FKs para `CustomUser` são inteiras (ver §3, R1).

### 2.1 Trilha (`LearningTrail`)

> **Âmbito:** só `LearningTrail`/`TrailNode`. `AdaptiveTrail`/`AdaptiveStep` estão **adiados (D5)** e tratados em §2.4. Tudo o que na versão anterior era exclusivo do adaptativo (`mode`, `role`, `TrilhaInscricao`, `multiplier`, `gaps/strengths`, `failureRate`, `dataMb`, `badge`, `topic` em `Question`) foi retirado do modelo desta fase.

#### Modelos

**`Trilha`**

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `organizacao` | FK Organizacao, null | `NULL` = marketplace |
| `creator` | FK CustomUser, `PROTECT` | |
| `title` | Char(255) | |
| `headline` | Char(255) | → `headline` |
| `subject` | Char(120) | → `subject`. Se vier a existir entidade Disciplina, passa a FK |
| `year` | Char(30), blank | → `year` (ex.: texto do ano curricular) |
| `semester` | Char(30), blank | → `semester` |
| `final_exam` | FK Quiz, null | → `finalExam`; um exame por trilha |
| `is_published` | Bool | |
| `created_at` | DateTime | |

**`TrilhaItem`**

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | → `id` |
| `trilha` | FK Trilha, CASCADE | |
| `order` | PositiveInt | → `order`; `UniqueConstraint(trilha, order)` deferível |
| `kind` | Char choices `conteudo`/`quiz`/`enquete` | eixo do SLA §9.3 |
| `content` / `quiz` / `enquete` | 3 FKs null | `CheckConstraint`: exactamente uma preenchida, coerente com `kind`. Alternativa `GenericForeignKey` rejeitada: perde integridade referencial e filtragem por tenant |
| `title_override`, `summary` | Char/Text, blank | → `title`, `summary`; se vazio, herda do alvo |
| `minutes` | PositiveSmallInt, null | → `minutes` (ver nota abaixo) |
| `xp_reward` | PositiveInt, null | → `xp`; se nulo, calcula-se do quiz |

**`TrilhaProgresso`** (novo, estado por utilizador): `user`, `item`, `state` (`concluido`/`em_curso`), `stars` (0–3, null), `completed_at`; `unique(user, item)`.

#### Mapeamento fidelidade-a-fidelidade

| Campo TS | Origem | Observação |
|---|---|---|
| `TrailNode.id` | `TrilhaItem.id` | |
| `.order` | `TrilhaItem.order` | |
| `.title` / `.summary` | `title_override` ou alvo | serializer |
| `.minutes` | `TrilhaItem.minutes` | `Content.duration` é texto livre (`"15 min"`?) — não é fiável; guardar inteiro no item |
| `.xp` | `xp_reward` ou `nº perguntas × 10` | cálculo no serializer; a constante 10 hoje vive só na view |
| `.status` | **calculado** | `concluido` se há `TrilhaProgresso`; `ativo` se é o primeiro não concluído; `bloqueado` os restantes. Regra sequencial confirmada? (D7) |
| `.stars` | **calculado** de `TrilhaProgresso.stars` | precisa de acertos/total na submissão (R2); limiares a definir |
| `.href` | **só frontend** | a rota é do SPA. API devolve `kind` + id do alvo |
| `LearningTrail.subject/headline/year/semester` | `Trilha` | campos próprios |
| `.nodes` | `TrilhaItem` com `role != exame_final`, ordenados | |
| `.finalExam` | `Trilha.final_exam` | objecto separado: `title` do quiz, `minutes`/`xp` calculados, `href` no frontend |
| `AdaptiveTrail` / `AdaptiveStep` (todos os campos) | **fora do âmbito (D5)** | ver §2.4 |

**Fica só no frontend:** `href`, formatação de `year`/`semester`.

### 2.1.1 Nota sobre `TrilhaItem.kind = exame_final`
O exame final é `Trilha.final_exam` (FK), não um item; `nodes` nunca o inclui.

### 2.2 `Quiz` precisa de duas mudanças

- Hoje é `OneToOne(Content)`. Um simulado, checkpoint ou exame final não é "de" um conteúdo. Proposta: `content` passa a nullable, `Quiz` ganha `organizacao` (null) e `creator`.
- `unique_together(user, quiz)` impede repetir tentativa (R3).

### 2.3 Enquete

#### Modelos

**`Enquete`**

| Campo TS (`SurveyDraft`) | Campo Django | Notas |
|---|---|---|
| `question` | `question` Text | |
| `kind` | `kind` Char choices `escala`/`escolha`/`binaria` | |
| `decision` | `decision` Text | decisão de negócio que a enquete informa. **Interno:** nunca vai para o votante |
| `faculty` | `faculty` Char | segmentação (texto; FK se existir estrutura) |
| `subject` | `subject` Char | |
| `trigger` | `trigger` Char choices `fim-simulado`/`fim-leitura`/`fim-modulo` | |
| `sampleTarget` | `sample_target` PositiveInt | nº de respostas que fecha a enquete |
| `segmentSize` | `segment_size` PositiveInt | ver nota |
| `options: string[]` | `EnqueteOpcao` | filhas, não array |
| — | `organizacao` FK null, `creator` FK PROTECT | |
| — | `state` Char `rascunho`/`activa`/`encerrada` | |
| `closedAt` (Result) | `closed_at` DateTime null | |
| — | `anonymous` Bool default True | D9 (**validação legal pendente**) |

**`EnqueteOpcao`:** `id`, `enquete` FK, `label`, `order`, `value` (int, null; para escala).

**`EnqueteVoto`:** `id`, `enquete` FK, `opcao` FK, `user` FK, `voted_at`, `year_snapshot` (Char; ano do votante no momento), `unique(enquete, user)`.

**`EnqueteExibicao`** (necessária por `shown`/`dismissed`): `enquete`, `user`, `outcome` (`vista`/`respondida`/`dispensada`), `at`; `unique(enquete, user)`.

#### Mapeamento do `SurveyResult`

| Campo TS | Origem |
|---|---|
| `question`, `decision`, `subject` | `Enquete` |
| `closedAt` | `Enquete.closed_at` (ISO no serializer) |
| `answers` | `COUNT(EnqueteVoto)` |
| `dismissed` | `COUNT(EnqueteExibicao, outcome=dispensada)` |
| `shown` | `COUNT(EnqueteExibicao)` (todas as exibições) |
| `distribution[{label,value}]` | agregação por `EnqueteOpcao`; **`value` = percentagem 0–100 sobre `answers`** (D10; o frontend usa `(value/100)*answers`) |
| `byYear[{year, answers, topChoice, share}]` | agregação por `year_snapshot`; `topChoice` = label da opção mais votada; **`share` = percentagem 0–100** dessa opção sobre as respostas do ano (D10; o frontend renderiza `{share}%` sem multiplicar) |

Regras de serialização (D10): percentagens como número (não string), arredondamento definido uma vez no serializer (sugestão: 1 casa decimal), e `distribution` deve somar ~100 (tolerância de arredondamento). Com `answers = 0`, devolver `value`/`share` = 0, nunca dividir por zero.

Tudo isto é **calculado**; nenhuma coluna de resultado é guardada.

#### Notas de desenho

- `year_snapshot` existe porque `Membership.academic_year` muda com o tempo; sem snapshot, `byYear` reescreve a história.
- Anonimato: `user` é necessário para impedir voto duplo. Se a enquete for anónima, a API nunca devolve quem votou. Se houver risco legal/reputacional, considerar guardar hash do utilizador em vez de FK (D9).
- `trigger` é só um tipo. Para disparar de facto, falta o alvo ("depois de **este** simulado"). Proposta: `trigger_quiz`/`trigger_content` FK nulls, ou associar via `TrilhaItem(kind=enquete)`. Em trilhas já resolvido pelo item; fora delas, é D11.
- `segmentSize` — não consigo determinar só pelo tipo se é a **dimensão do universo** (total de alunos elegíveis) ou o tamanho de cada fatia de segmentação. Assumi o primeiro. Confirmar com Carlos/Augusto.
- XP por enquete: pergunta aberta nº 2 da proposta. Se sim, entra no ledger de XP (R2), não em `QuizSubmission`.

### 2.4 `AdaptiveTrail` — adiado (D5)

Não se cria nenhum modelo, campo ou migration para `AdaptiveTrail`/`AdaptiveStep` nesta fase. O ecrã do frontend continua a funcionar com dados mock. Para não criar retrabalho quando for retomado:

- **Reutilizável sem mudança:** `Trilha`, `TrilhaItem`, `TrilhaProgresso`. Adaptativa deverá ser uma extensão destes, não um modelo paralelo.
- **Em aberto (não desenhar agora):** instantâneo por aluno (`initialAccuracy`, `multiplier`, `gaps`, `strengths`), papel do passo (`reforco`/`simulado`/`checkpoint`), `topic` em `Question`, `data_mb`, `badge`, `failureRate`, regra do multiplicador, e o enum de estado `disponivel` vs. `ativo`.
- **Dependências que esta fase já resolve e que o adaptativo vai reutilizar:** `correct_count`/`total_questions` em `QuizSubmission` e o ledger de XP (R2), tentativas múltiplas (R3/D12).
- **Compatibilidade:** `TrilhaItem.kind` é char com choices, pelo que acrescentar um eixo `role` depois é migração aditiva e nullable.
- **Frontend:** a API de Trilhas desta fase **não** devolve o contrato `AdaptiveTrail`. Confirmar com Augusto que o ecrã adaptativo continua em mock até haver decisão.

---

## 3. Riscos de migração e dados que a nova modelagem deve resolver

### R1. PKs: documentação ≠ código  *(Alto, afecta o ERD)*
`CustomUser`, `QuizSubmission` e `QuizAnswer` são `BigAutoField` (migrations `0001`). A documentação e o ERD actual dizem UUID. Além disso `TopUserSerializer.user_id` é `UUIDField`, mas o serializer nem é usado pela view (devolveria int).
**Recomendação:** não migrar a PK de `CustomUser` para UUID (migração destrutiva, quebra FKs e JWTs). Corrigir o ERD e usar UUID só nas tabelas novas.

### R2. `score` inteiro simples  *(Alto)*
`QuizSubmission.score` = XP; acertos e total de perguntas perdem-se. Consequências concretas:
- `stars` (esta fase) e, mais tarde, `initialAccuracy`/`failureRate`/`gaps` do adaptativo (D5, adiado) não são calculáveis.
- A regra "10 XP por acerto" está hardcoded na view; o nível `XP // 100 + 1` está duplicado em `UserProfileSerializer.get_nivel` e `LearnerStatsView`.
- A resposta da API tem inconsistências que o frontend herdará: chave `"xp earned"` (com espaço); `totalPoints` devolve o nº de perguntas, não pontos.
- `Question` não tem tópico → `gaps/strengths` impossíveis (relevante só quando D5 for retomado).

**A resolver:** adicionar a `QuizSubmission` `correct_count`, `total_questions`, `xp_awarded`, `organizacao` (null), `attempt` e, opcionalmente, `duration_s`. Criar um **ledger de XP** (`XPEvent`: user, organizacao null, source_type/source_id, amount, created_at) como fonte única da carteira, do nível e dos rankings.
**Backfill:** `correct_count = score // 10` é exacto só enquanto a constante foi sempre 10; `total_questions` seria o `count()` actual (pode ter mudado). Marcar como aproximado.

### R3. `unique_together(user, quiz)` e `Quiz 1:1 Content`  *(Médio-Alto)*
Uma tentativa por quiz para sempre. Incompatível com reforço, simulado repetível e checkpoint. E, com a trilha, o mesmo quiz pode aparecer em duas trilhas/workspaces. Decidir: tentativas múltiplas com XP só na primeira, ou nova constraint `(user, quiz, attempt)`.

### R4. Rankings vazio e ineficiente  *(Alto)*
- `rankings/models.py` vazio; sem escopo (global/organização/trilha) nem período.
- `GlobalRankingView` faz `list()` de **todos** os utilizadores com submissões e calcula posição em Python a cada pedido (O(n)); sem paginação.
- **Expõe `email` dos top 100 a qualquer autenticado.** Num contexto B2B isto vaza identidade entre tenants e entre B2C/B2B.
- Empates têm posições distintas para o topo e "posição igual" para o utilizador (inconsistência).

**A resolver:** ranking derivado do ledger com filtro por `organizacao`; mostrar nome de exibição, não email; posição via `RANK()`/count indexado; snapshot materializado só se o volume o exigir.

### R5. Apagar em cascata destrói o histórico  *(Alto, conflita com "carteira única")*
`Content.creator` e `QuizSubmission.quiz` são `CASCADE`. Apagar um criador apaga os conteúdos, os quizzes e **as submissões (XP) de todos os alunos**. O SLA exige carteira digital única e histórico de XP preservado. Com o ledger independente + `PROTECT`/`SET_NULL` e arquivamento (soft delete) em vez de delete, isto fecha-se.

### R6. Papéis globais vs. por organização  *(Alto)*
`user_type` é global e `IsCreator` decide só por ele. Na escola o papel é `student/teacher/admin` (proposta §4.1). Mover o papel para `Membership.role`; manter `user_type` como valor por omissão no marketplace.

### R7. Fugas de isolamento já existentes  *(Alto, a corrigir antes do multi-tenant)*
- `ContentViewSet` é `ModelViewSet` com `IsAuthenticated` para `update/partial_update/destroy`: **qualquer utilizador autenticado edita ou apaga qualquer conteúdo.** Só `create` exige `IsCreator`; não há verificação de `creator == request.user`.
- `QuizGenerationView` e `QuizManualCreationView` exigem `user_type == creator`, mas não que o conteúdo seja do utilizador.
- `QuizDetailView`, `QuizSubmissionView`, `ContentViewSet.queryset` usam `objects.all()`; filtro `creator` aberto.
- `LearnerCoursesView` devolve `progress: 100` fixo; `CreatorStatsView` devolve `averageRating`/`totalRevenue` = 0 fixos.

A regra §8.3 ("isolamento sempre no backend") exige um ponto único de scoping (manager/mixin por contexto activo), não filtros por view.

### R8. Contexto activo (workspace) inexistente na API  *(Médio)*
Nem o JWT nem os headers transportam contexto. Falta decidir como o backend sabe o workspace activo (claim vs. header `X-Workspace`) e validar a pertença em cada pedido. É a pergunta nº 4 da proposta (notificações) em versão geral.

### R9. Ambiente de desenvolvimento  *(Médio)*
`settings.py` usa SQLite por omissão (`DATABASE_URL` ausente). Schema-per-tenant é impossível em SQLite, e a paridade Postgres é entregável da Fase 1. Qualquer decisão de modelo deve ser testada em Postgres.

### R10. Conteúdo: campos que não suportam o novo domínio  *(Médio)*
`category` com 3 valores fixos (não representa "disciplina"); `type` sem choices; `duration` texto; `tags` CSV; sem `data_mb`; sem visibilidade/organização. Muitos alimentam directamente `TrailNode`.

### R11. Backfill e ordem das migrations  *(Baixo se feito por esta ordem)*
1. App `tenancy` (Organizacao, Membership). 2. FK `organizacao` **nullable** em `Content`/`Quiz`/`QuizSubmission`: dados existentes ficam `NULL` = marketplace, sem data migration. 3. Colunas novas em `QuizSubmission` com backfill aproximado (R2). 4. `XPEvent` + backfill a partir das submissões. 5. `Trilha*`/`Enquete*`. Não editar migrations aplicadas (SLA §8.1).

### R12. Paginação  *(Baixo)*
`PageNumberPagination` global devolve `{count, next, results}`. As formas TS são objectos/arrays directos; confirmar que os novos endpoints seguem ou isentam.

---

## 4. Registo de decisões (CTO)

| # | Decisão | Estado | Resolução e consequência para o ERD |
|---|---|---|---|
| **D1** | Isolamento | ✅ Decidido: **B** | FK lógica `organizacao`, `NULL` = marketplace. SLA §9.2 será corrigido na nota v2.0.1 (à parte). Reforço opcional com Row-Level Security |
| **D2** | Workspace como entidade? | ✅ Aceite | Sem modelo `Workspace`: `Membership` + contexto activo (`Organizacao` ou marketplace) |
| **D3** | PK de `CustomUser` | ✅ Aceite | Mantém-se inteira (BigAutoField); corrigir ERD/docs (R1). Tabelas novas em UUID |
| **D4** | Trilha Mista | ✅ Aceite | Sem modelo `TrilhaMista`: uma só `Trilha` com itens `conteudo`/`quiz`/`enquete` |
| **D5** | `AdaptiveTrail` | ⏸ **Adiado** | Fora do âmbito. Sem `TrilhaInscricao`, `role`, `multiplier`, `topic`, `data_mb`, `badge` (ver §2.4) |
| **D6** | Idioma dos nomes | ✅ Aceite | Classes PT do SLA §9.3; campos EN; enums e chaves de API como o contrato TS |
| **D7** | Desbloqueio de trilha | ✅ Aceite | Sequencial por omissão com flag por trilha; **limiares de `stars` ainda por fixar** (sugestão 50/75/90%) |
| **D8** | `course` / `faculty` | ✅ Aceite | Texto livre em `Membership`; sem entidades Faculdade/Curso nesta fase |
| **D9** | Anonimato das enquetes | ⚠️ Técnica aceite, **validação legal pendente** | FK interna ao utilizador, API nunca expõe identidade. **Não tratar como resolvido** até haver parecer sobre protecção de dados (lei angolana). Se o parecer exigir, a alternativa é hash em vez de FK; `EnqueteVoto.user` deve ser isolável numa migration futura |
| **D10** | Unidades de resultados | ✅ Decidido | `distribution.value` e `byYear.share` em **percentagem 0–100** (confirmado em `SurveyResultsScreen.tsx`) |
| **D11** | Alvo do gatilho da enquete | ✅ Aceite | Via `TrilhaItem(kind=enquete)` nesta fase; FK directa em `Enquete` fica para depois |
| **D12** | Tentativas de quiz | ✅ Aceite | Múltiplas tentativas, XP só na primeira (substitui `unique_together(user, quiz)`) |
| **D13** | XP por enquete | ✅ Aceite | Sim, via ledger de XP. Valor por voto a fixar (sugestão: 5) |

### Itens ainda abertos (não são decisões de modelagem)

1. **Parecer legal D9** (protecção de dados) antes de a funcionalidade de enquetes ir a produção.
2. **Limiares de `stars`** (D7) e **valor de XP por enquete** (D13).
3. **Semântica de `segmentSize`** — assumi "universo elegível"; confirmar com Carlos/Augusto.
4. Confirmar com Augusto que o ecrã adaptativo continua em mock (D5).
5. Corrigir `arquitetura_atual_kombinu.md` (PKs, `type`) para reflectir R1.
---

## 5. O que não verifiquei

- Repositório do frontend (usei só os tipos que colaste).
- Conteúdo detalhado dos schemas em `Kombinu API.yaml` (comparei só os paths).
- `admin.py`, testes e `contents/urls.py` linha a linha.
- Volume real de dados em produção (afecta se um snapshot de ranking é necessário e a fiabilidade do backfill de `correct_count`).
