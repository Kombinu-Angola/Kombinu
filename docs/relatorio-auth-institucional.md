# KOMBINU — Autenticação institucional (proposta de desenho, Fase 2)

| Campo | Valor |
|---|---|
| Documento | Proposta de desenho — autenticação e provisionamento institucional |
| Base | SLA v2.0.0 §2 (Ponto Cego 1), §10 Fase 2 ("Autenticação institucional — credenciais geradas pela escola"); estado de `develop` em `5848934` |
| Estado | **Aprovada pelo CTO (Novembro de 2026).** D1–D13 decididas (§7). D14 (parecer legal) pendente: bloqueia só o piloto com alunos reais, não a implementação. Implementação pela ordem da §7.1 |
| Âmbito | Login e provisionamento de contas de alunos e professores de uma `Organizacao`; primeiro acesso; impacto no login existente |
| Fora de âmbito | UI, recuperação por email (não existe infra de email), SSO/OAuth, cobrança de licenças |

---

## 0. Resumo

1. **Hoje uma organização não consegue trazer ninguém para dentro sem mexer na base de dados à mão.** Não há endpoint que crie utilizador com `Membership`; só o Django admin (um a um).
2. **Proposta:** credencial institucional = *código da escola + código de aluno + password temporária* (sem exigir email), com email real opcional. Contas criadas em **lote por um admin da organização** via API, cada uma já com a sua `Membership`. Primeiro acesso com **troca de password obrigatória** e sessões anteriores revogadas.
3. **Login:** manter `POST /api/auth/login/` (email + password) intacto e acrescentar um caminho próprio para o login institucional, com o mesmo envelope de resposta mais `memberships` e `mustChangePassword`.
4. **Encontrei três lacunas no código actual que condicionam o desenho:** não há *throttling* nem revogação de tokens; `IsCreator` ignora o papel na `Membership` (um professor provisionado como `learner` não conseguiria criar conteúdo na escola); e hashing de password lento torna o provisionamento em lote um problema de timeout (§3.4).
5. **Há 14 decisões** na §7: D1–D13 aprovadas pelo CTO conforme as recomendações; D14 (parecer legal) pendente e só bloqueia o piloto com alunos reais.

---

## 1. Estado actual (verificado no código)

### 1.1 Autenticação

| Aspecto | Hoje | Fonte |
|---|---|---|
| Identificador de login | Email (`USERNAME_FIELD = "email"`); o registo grava `username = email` | `accounts/models.py`, `serializers.py` |
| Login | `POST /api/auth/login/` → `authenticate(username=email, password=...)` → JWT (`access` 60 min, `refresh` 1 dia) + perfil | `accounts/views.py` |
| Registo | `POST /api/auth/register/`, **aberto**, sem verificação de email; o próprio utilizador escolhe `user_type` (`creator` ou `learner`) | `UserRegistrationSerializer` |
| JWT | HS256, `ROTATE_REFRESH_TOKENS = False`, `BLACKLIST_AFTER_ROTATION = False`, `UPDATE_LAST_LOGIN = False`; sem claim de workspace | `settings.SIMPLE_JWT` |
| Revogação | **Inexistente.** Um refresh roubado vale 1 dia; trocar a password não invalida tokens | settings |
| Brute force | **Sem throttling** em nenhum endpoint | `REST_FRAMEWORK` |
| Email | **Sem `EMAIL_BACKEND` configurado.** Não existe nenhum fluxo por email (reset, verificação) | settings |
| Password | Validators padrão do Django (similaridade, 8 caracteres, comum, numérica) | `AUTH_PASSWORD_VALIDATORS` |
| Perfil devolvido no login | `id`, `email`, `user_type`, `first_name`, `last_name`, `nome`, `pontos`, `nivel`. **Não inclui as memberships** | `UserProfileSerializer` |

### 1.2 Tenancy

- `Organizacao`: `name`, `slug` (único), `domain` (único, opcional, **sem uso**), `org_type`, `is_active`.
- `Membership`: `user`, `organizacao`, `role` (`student`/`teacher`/`admin`), `academic_year`, `faculty`, `course`, `is_active`; único por (`user`, `organizacao`).
- O contexto activo vem do header `X-Workspace` e é validado contra a `Membership` em cada pedido (`tenancy/scoping.py`).
- **Não existe nenhum caminho para criar `Organizacao`, `Membership` ou o utilizador correspondente fora do Django admin.**

### 1.3 O que falta para uma organização trazer alunos

| Falta | Consequência |
|---|---|
| Criar utilizador + `Membership` numa só operação, em lote | Hoje: um a um no admin, em dois passos separados |
| Identificador de aluno dentro da organização | `Membership` não tem código/número de aluno; só email global |
| Conta sem email próprio | `CustomUser.email` é obrigatório e único |
| Primeiro acesso seguro | Não há conceito de password temporária nem de troca obrigatória |
| Quem é admin da organização | Existe `role="admin"`, mas nada o usa para autorizar acções de gestão |
| Reset de password sem email | Não existe |
| Throttling / revogação | Não existem; críticos assim que haja milhares de contas com passwords geradas |

### 1.4 Lacuna encontrada: `IsCreator` ignora a `Membership`

`ContentViewSet.create` exige `IsCreator`, que só olha para `user_type == "creator"`. O `can_create_in` (que verifica o papel `teacher`/`admin` na organização) corre **depois**. Resultado: um professor provisionado com `user_type="learner"` leva 403 ao criar conteúdo na escola, mesmo sendo `teacher`. Ver D11.

---

## 2. Formato das credenciais

O SLA §2 diz "credenciais geradas pela própria escola (ou por nós)". Isto pode significar duas coisas diferentes, e **ambas ficam cobertas** nesta proposta:

| | A. Email + password | B. Código da escola + código de aluno + password |
|---|---|---|
| Para quem | Professores, alunos com email, universitários | Alunos sem email próprio (ensino médio) |
| Identificador | Email real | `(código da escola, código de aluno)` |
| Conta no sistema | Email real em `CustomUser.email` | Email técnico não entregável (ver abaixo) |
| Recuperação | Reset por admin (não há email) | Reset por admin |
| Login | `/api/auth/login/` (já existe) | Novo caminho institucional |

### 2.1 Como representar um aluno sem email

`CustomUser.email` é `unique` e obrigatório, e `USERNAME_FIELD = "email"`. Alterá-lo para opcional afecta autenticação, registo, serializers e todos os testes. **Proposta:** não mexer nisso; gerar um **email técnico** determinístico e não entregável:

```
<código-de-aluno>@<slug-da-escola>.kombinu.invalid
```

- `.invalid` é TLD reservado (RFC 2606): nunca resolve, nunca recebe email, sem risco de colisão com domínios reais.
- É único por construção (código único por organização + slug único).
- Passa na validação de `EmailField` do Django.
- Deve ser **tratado como identificador interno**: não aparece em ecrãs, listas nem exportações. Hoje `UserProfileSerializer` devolve `email`; para estas contas devolver `null` (ou omitir) — a decidir com o frontend.
- O utilizador pode **substituir por um email real** mais tarde (migração para o marketplace, §6.3).

### 2.2 Código da escola

`Organizacao.slug` já existe e é único, mas é um *slug* de URL (`colegio-sao-jose`), longo para um aluno escrever. Duas opções: reutilizar o `slug` ou acrescentar um `code` curto (ex.: 6 caracteres). Ver D2.

### 2.3 Código de aluno

Atribuído **pela escola** (número de processo/matrícula que já existe), não gerado por nós: é o que o aluno já conhece e permite à secretaria reconciliar com os seus registos. Único por organização. Texto livre, normalizado (maiúsculas, sem espaços) para evitar duplicados por formatação.

---

## 3. Fluxo de provisionamento

### 3.1 Quem cria as contas

| Opção | Descrição | Prós | Contras |
|---|---|---|---|
| **P1. Só Django admin / comando** | Equipa Kombinu importa a lista | Zero superfície de ataque nova; rápido de entregar | Não escala; cada escola depende de nós; contradiz "geradas pela escola" |
| **P2. Admin da organização, via API** | Utilizador com `Membership.role="admin"` envia lote para um endpoint | Autonomia da escola; mesma lógica que o admin usaria | Nova superfície autenticada; exige autorização e auditoria bem feitas |
| **P3. Self-service com convite** | Link/código de convite para o aluno se registar | Sem passwords temporárias | Precisa de email ou canal de entrega; o aluno sem email não usa |

**Recomendação:** P2 como caminho principal e P1 para o **bootstrap** (o primeiro admin de cada organização é criado por nós, via comando de gestão; ver D3). P3 fica para depois.

### 3.2 Endpoint de lote (descrição, sem implementação)

Acção de um admin da organização do workspace activo (`X-Workspace`). Entrada: lista de linhas.

| Campo da linha | Obrig. | Notas |
|---|---|---|
| `studentCode` | Sim | Único por organização; normalizado |
| `firstName`, `lastName` | Sim | Nome de exibição (o ranking já usa nome, não email) |
| `role` | Não | `student` por omissão; `teacher`/`admin` só criáveis por admin |
| `academicYear`, `faculty`, `course` | Não | Vão para `Membership` (D8 do relatório da Fase 1) |
| `email` | Não | Se existir, usado como identificador real (formato A) |

Comportamento proposto:

- **Atómico por lote** ou **parcial com relatório por linha**? Proposta: modo `dryRun` que só valida e devolve erros por linha; o envio real é **tudo ou nada** (D4).
- Limite de linhas por pedido (proposta: 200; ver §3.4).
- Resposta: por linha, `studentCode` + estado + **password temporária** (única vez em que é devolvida). Nada é guardado em claro.
- Cada conta nasce **dentro da mesma transacção** com utilizador, `Membership` (papel e atributos académicos) e a marca de "troca de password pendente". Não há estado intermédio em que exista utilizador sem `Membership`.
- Conflitos: `studentCode` já existente na organização → erro de linha; email real já registado → erro de linha (nunca anexar uma `Membership` a uma conta existente sem consentimento; D12).

Endpoints auxiliares necessários para a escola operar sem nós: listar membros, desactivar/reactivar, **reset de password** (nova temporária), e re-emitir folha de credenciais.

### 3.3 Atributos novos necessários (descrição)

| Onde | Atributo | Para quê |
|---|---|---|
| `Membership` | `student_code` (único por organização, anulável) | Identificar o aluno na escola |
| `Membership` | `provisioned_by`, `provisioned_at` | Auditoria: quem criou a conta |
| `CustomUser` | `must_change_password` | Forçar troca no primeiro acesso e após reset |
| `CustomUser` | `password_changed_at` | Invalidar tokens emitidos antes da troca (D7) |
| `CustomUser` | `temp_password_expires_at` (ou na `Membership`) | Expirar passwords temporárias não usadas |
| Novo | registo de lote (organização, autor, quando, nº de contas) | Trilho de auditoria do provisionamento |

### 3.4 Risco de desempenho: hashing em lote

O Django 5.2 usa PBKDF2 com cerca de 1,2 milhões de iterações. Nos testes locais (Windows, Python 3.13.5) a criação de utilizadores com hashing real foi lenta ao ponto de a suite demorar cerca de 20–30 minutos (contra segundos com um hasher rápido). **Não medi o custo por hash em produção (Render/Linux)**, mas a ordem de grandeza obriga a tratar o lote como potencial *timeout* de pedido HTTP: 200 contas × centenas de ms pode passar o limite do proxy.

Opções: limitar o lote a um valor medido; processar em *chunks* com resposta por partes; ou trabalho em segundo plano com consulta de estado (mais infra). **Pedir benchmark em produção antes de fixar o limite (D4).**

---

## 4. Primeiro acesso e segurança

### 4.1 Password temporária com troca obrigatória (proposta)

**Mecanismo:**

1. O sistema gera uma password aleatória com `secrets` (nunca derivada do código de aluno, nome ou data de nascimento).
2. Mostra-a **uma única vez**, na resposta do lote/reset, ao admin que a provisionou. Só o *hash* é guardado.
3. A conta fica marcada com `must_change_password = true` e uma expiração (proposta: 7 dias).
4. No login com sucesso, enquanto a marca estiver activa, **toda a API devolve 403 com código `password_change_required`, excepto o endpoint de troca de password** (e logout/refresh). O gate é uma permission class lida do utilizador já carregado pelo JWT; não depende de claims que possam ficar desactualizadas.
5. A troca exige: password actual (a temporária), nova password a passar nos validators existentes, e **diferente da temporária**. Ao concluir: limpa a marca, grava `password_changed_at`, e invalida os tokens anteriores (D7).

**Formato da password temporária (proposta):** 8–10 caracteres de um alfabeto sem ambíguos (sem `0/O`, `1/l/I`). Com 31 símbolos, 8 caracteres dão cerca de 40 bits e 10 dão cerca de 50 bits. É fraco em absoluto, mas aceitável **se** (a) for de uso único e expirar, (b) houver throttling, (c) a troca for obrigatória. Sem throttling não é aceitável (D8).

### 4.2 Riscos que ficam escritos, não assumidos

| # | Risco | Mitigação proposta | Risco residual |
|---|---|---|---|
| S1 | **A password temporária fica em papel/CSV** na posse da secretaria; quem a vir pode entrar antes do aluno | Expiração; troca obrigatória no 1.º login; aviso na UI; reset por admin | Aluno nunca activa a conta e alguém o faz antes. Detectável por `last_login` (hoje desligado) |
| S2 | **Códigos de aluno são sequenciais e adivinháveis**; o código da escola é quase público | Throttling por conta e por IP; mensagem de erro igual para "escola inexistente", "aluno inexistente" e "password errada"; custo de hash igual em todos os caminhos (evita *timing*) | Ataque distribuído lento |
| S3 | **Sem throttling hoje.** Toda a proposta assume que passa a existir | Escopos de throttle para login (por IP e por identificador) | Escolas partilham IP (NAT): limite por IP tem de ser generoso, ou bloqueia a turma |
| S4 | **Bloqueio por tentativas falhadas é um vector de DoS** (alguém bloqueia a conta de um colega de propósito) | Lockout temporário curto (minutos), não permanente; sem revelar se a conta existe | Incómodo, não perda de acesso |
| S5 | **Tokens não são revogáveis.** Trocar/resetar a password não corta sessões antigas | `password_changed_at` verificado na regra de autenticação do JWT, ou *blacklist* do simplejwt (acrescenta app e tabelas) | Janela até à implementação de D7 |
| S6 | **Quem pode provisionar é poder elevado**: um admin cria contas e vê passwords | Autorização estrita por `Membership.role="admin"` **da organização do workspace**; registo de auditoria; limites por pedido | Conta de admin comprometida |
| S7 | **`user_type` auto-atribuído no registo aberto**: qualquer pessoa pode registar-se como `creator` | Fora do âmbito desta proposta; nas contas institucionais o `user_type` é definido pelo servidor, nunca pelo cliente | Pré-existente, a tratar à parte |
| S8 | **Adesão automática por domínio de email** (`Organizacao.domain`) permitiria a qualquer pessoa reclamar uma escola com um email não verificado | **Não implementar.** Sem verificação de email, não é seguro | — |
| S9 | **Dados de menores.** Alunos podem ser menores; a conta guarda nome e código | Minimização: nenhum campo extra (sem data de nascimento, morada, telefone) | **Parecer legal pendente** (protecção de dados, como em D9 do relatório da Fase 1) |
| S10 | **Email técnico exposto** em perfil/exportações revela estrutura de identificadores | Não devolver `email` técnico à UI | — |
| S11 | **Sessão sem limite máximo** (D7, rotação sem blacklist): cada refresh emite um refresh novo válido por 1 dia, por isso uma sessão em uso nunca expira; um refresh roubado e usado com regularidade mantém o acesso, e o refresh antigo continua válido até expirar | Troca de password revoga todos os tokens (`password_changed_at`); desactivar a conta corta o acesso. **Mitigação futura:** `rest_framework_simplejwt.token_blacklist` com `BLACKLIST_AFTER_ROTATION` (app e tabelas novas) e/ou um limite absoluto de sessão (ex.: claim com a hora do login original, recusada ao fim de N dias) | Aceite pelo CTO em D7; rever antes do piloto com alunos reais |

### 4.3 Reset e recuperação

Sem infra de email, **não há recuperação self-service** para contas de formato B. O reset é feito por um admin da organização (nova password temporária, `must_change_password` reactivado, sessões antigas revogadas) e fica no registo de auditoria. Para contas com email real, o fluxo por email é uma fase posterior.

---

## 5. O que muda no login existente

### 5.1 Recomendação: caminho próprio, mesmo envelope

| | `POST /api/auth/login/` | `POST /api/auth/institutional/login/` (novo) |
|---|---|---|
| Entrada | `email`, `password` | `school`, `studentCode`, `password` |
| Quem usa | Marketplace, professores com email, qualquer conta com email real | Alunos sem email próprio |
| Resposta | Igual à actual (compatível) | Mesmo envelope: `access_token`, `refresh_token`, `user` |
| Acrescenta a ambas | `memberships` (lista) e `mustChangePassword` | idem |

**Porquê separado e não um endpoint polimórfico:** (a) o contrato actual do frontend não parte; (b) *throttling* e mensagens de erro com regras próprias; (c) o corpo de entrada tem semântica diferente e misturá-los complica validação e documentação; (d) permite desligar um sem afectar o outro.

**Alternativa:** um só endpoint que aceita `email` **ou** `school`+`studentCode`. Menos URLs, mais condicionais. Ver D10.

### 5.2 O que o login passa a devolver

`UserProfileSerializer` não tem as memberships; o frontend não tem como saber que workspaces o utilizador tem, nem qual definir em `X-Workspace`. Proposta: `memberships: [{organizacaoId, name, role}]` e, se houver exactamente uma, esse é o workspace por omissão. Isto é aditivo, não quebra o contrato existente.

### 5.3 Impacto no resto do sistema

| Componente | Impacto |
|---|---|
| `X-Workspace` / scoping | Nenhum: já resolve por `Membership` |
| Ranking, dashboards, quizzes, trilhas, enquetes | Nenhum: já filtram por contexto |
| `IsCreator` | **Muda** (D11): deve considerar `Membership.role` no contexto activo |
| `UserProfileSerializer` | Passa a incluir `memberships` e `mustChangePassword`; `email` pode ser nulo |
| Registo (`/register/`) | Sem alteração; as contas institucionais não passam por aqui |
| JWT | Sem claims novas; o gate de troca lê o utilizador na BD |
| Testes | Hasher rápido nos testes para o provisionamento em lote não custar minutos |

---

## 6. Ciclo de vida

### 6.1 Professores e admins

Provisionados como os alunos, com `role` `teacher` ou `admin`. **O primeiro admin de cada organização é criado por nós** (comando de gestão): é o ponto de partida da cadeia de confiança. Um admin da organização só gere a **sua** organização (autorização por workspace activo).

### 6.2 Saída de um aluno

A `Membership` fica `is_active=false`; a conta, o XP e o histórico mantêm-se (carteira única, SLA §2). O código de aluno **não é reutilizado** na mesma organização.

### 6.3 Funil B2B → B2C

O aluno que quer continuar fora da escola precisa de um email real (para recuperação e login normal). Proposta para uma fase seguinte: um passo "associar email real" com verificação. Enquanto não existir, o aluno que sai fica sem recuperação por conta própria. Ver D13.

---

## 7. Decisões (aprovadas pelo CTO, excepto D14)

| # | Decisão | Opções | Recomendação |
|---|---|---|---|
| **D1** ✅ | **Formato das credenciais** — **DECIDIDO pelo CTO: C** | (A) só email+password; (B) só código escola + código aluno; (C) ambos | **C**: B por omissão para alunos sem email, A para quem tem email real; email técnico `<código>@<slug>.kombinu.invalid` |
| **D2** ✅ | **Identificador da escola no login** — **DECIDIDO: `code` curto de 6 caracteres** | Reutilizar `slug`; ou novo `code` curto | **`code` curto** se for ditado/escrito por alunos; senão reutilizar `slug` e poupar uma migração |
| **D3** ✅ | **Quem dispara o provisionamento** — **DECIDIDO pelo CTO: P2** | P1 só nós; P2 admin da organização via API; P3 convite | **P2**, com P1 (comando) só para o 1.º admin de cada escola |
| **D4** ✅ | **Semântica do lote** — **DECIDIDO: tudo-ou-nada + `dryRun`, até 100 linhas** | Tudo-ou-nada com `dryRun`; parcial com relatório | **Tudo-ou-nada + `dryRun`**; limite fixado após benchmark de hashing em produção |
| **D5** ✅ | **Password temporária** — **DECIDIDO: gerada com `secrets`, uso único, expira em 7 dias** | Gerada e mostrada uma vez; derivada do código (rejeitada); link de activação (precisa de email) | **Gerada, uso único, expira em 7 dias** (confirmar prazo) |
| **D6** ✅ | **Troca obrigatória** — **DECIDIDO: obrigatória no 1.º login** | Obrigatória; opcional | **Obrigatória**, com gate na API e nova password diferente da temporária |
| **D7** ✅ | **Revogação de sessões** — **DECIDIDO: `password_changed_at` + rotação do refresh** | `password_changed_at` na regra de autenticação; *blacklist* do simplejwt | **`password_changed_at`** (sem tabelas novas); *blacklist* só se precisares de logout remoto |
| **D8** ✅ | **Throttling e lockout** — **DECIDIDO: os limites do hotfix 2.7.1** (login 30/min por IP e 5/min por conta; registo 10/h; refresh 30/min) | Valores a definir | Por IP generoso (NAT escolar) + por conta mais estrito; lockout curto (minutos). Preciso dos números que aceitas |
| **D9** ✅ | **Quem faz reset de password** — **DECIDIDO: só `admin`, auditado** | Só `admin`; `admin` e `teacher` (da turma) | **Só `admin`** nesta fase; tudo auditado |
| **D10** ✅ | **Endpoint de login** — **DECIDIDO: separado** | Separado; único polimórfico | **Separado** (§5.1) |
| **D11** ✅ | **Papel de criador** — **DECIDIDO: `IsCreator` usa `Membership.role`** | Provisionar professores com `user_type="creator"`; e/ou corrigir `IsCreator` para usar `Membership.role` | **Ambos**: corrigir `IsCreator` (a fonte de verdade na escola é a `Membership`) |
| **D12** ✅ | **Aluno que já tem conta com o mesmo email** — **DECIDIDO: rejeitar a linha** | Rejeitar a linha; anexar `Membership`; convite com aceitação | **Rejeitar** nesta fase; convite numa fase seguinte (anexar sem consentimento viola a conta do utilizador) |
| **D13** ✅ | **Aluno que sai da escola** — **DECIDIDO: mantém conta e XP; login institucional só com contexto marketplace** | Manter só login institucional; exigir email real; permitir login com membership inactiva | **Manter conta; permitir login institucional com contexto marketplace**; "associar email real" na fase seguinte |
| **D14** ⏳ | **Parecer legal (menores/protecção de dados)** — **PENDENTE; bloqueia só o piloto com alunos reais** | Antes de produção; ou antes do piloto | **Antes de qualquer piloto com alunos reais.** Pendente, como D9 da Fase 1 |

### 7.1 Ordem de implementação

1. Atributos novos + migrations (membership, utilizador) e **hasher rápido nos testes**.
2. Throttling e `password_changed_at` na regra JWT (pré-requisitos de segurança).
3. Correcção do `IsCreator` (D11).
4. Login institucional + gate de troca + endpoint de troca.
5. Endpoint de lote (`dryRun`, atómico) + comando do 1.º admin.
6. Listar/desactivar/reset.
7. Testes de isolamento: um admin da escola A não provisiona nem lê a escola B (SLA §8.3).

O throttling (D8) já entrou no hotfix 2.7.1 e o hasher rápido nos testes entra em `test/hasher-rapido-e-teste-instavel`.

### 7.2 Plano de branches (cada uma a partir de `develop`, com testes, CHANGELOG e schema)

| # | Branch | Conteúdo | Contrato para o frontend |
|---|---|---|---|
| 1 | `feature/auth-institucional-modelos` | `Organizacao.code` (6 caracteres, único, sem ambíguos); `Membership.student_code` (único por organização, normalizado), `provisioned_by`, `provisioned_at`; `CustomUser.must_change_password`, `password_changed_at`, `temp_password_expires_at`; modelo de auditoria `ProvisionamentoLote`. Migrations aditivas e nuláveis (sem backfill destrutivo); `code` gerado para as organizações existentes | Nenhum |
| 2 | `feature/auth-institucional-sessoes` | Regra de autenticação JWT que rejeita tokens emitidos antes de `password_changed_at` (D7); `ROTATE_REFRESH_TOKENS=True` (sem blacklist) | Refresh devolve também um novo `refresh` |
| 3 | `feature/auth-institucional-iscreator` | `IsCreator` e as verificações `user_type == "creator"` dos quizzes passam a `can_create_in(user, workspace)` (D11); testes de isolamento | Professor `teacher` com `user_type=learner` cria na escola |
| 4 | `feature/auth-institucional-login` | `POST /api/auth/institutional/login/` (`school`, `studentCode`, `password`), erro único 401 sem revelar o que falhou, custo de hash igual em todos os caminhos, throttles do login; `memberships` e `mustChangePassword` no envelope dos dois logins; gate 403 `password_change_required`; `POST /api/auth/password/change/` | Endpoint novo + 2 campos novos no login + código de erro 403 |
| 5 | `feature/auth-institucional-provisionamento` | `POST /api/tenancy/members/bulk/` (admin do workspace activo; `dryRun`; tudo-ou-nada; até 100 linhas; passwords temporárias devolvidas uma vez); comando `criar_admin_organizacao` para o 1.º admin; rejeitar emails existentes (D12) | Endpoint de lote |
| 6 | `feature/auth-institucional-gestao` | Listar membros, desactivar/reactivar (D13: a conta e o XP ficam), reset de password pelo admin (D9) com auditoria | Endpoints de gestão |

Testes de isolamento em todas as branches 3–6: um admin da escola A não provisiona, não lista, não desactiva e não faz reset na escola B, nem no marketplace; o `code` de uma escola não autentica alunos de outra.

---

## 8. O que não verifiquei

- **Custo real do hashing em produção** (Render/Linux); só observei o efeito nos testes locais.
- **Comportamento do frontend** de login e como guarda o `X-Workspace`.
- **Limites de timeout do proxy** no Render.
- **Se `.invalid` é aceite** pela validação de email do frontend. O `validate_email` do Django aceita-o (verificado); o frontend não foi lido.
- **Requisitos legais concretos** (menores, retenção); é o parecer de D14.
