# Kombinu - Plataforma Educacional

[![Version](https://img.shields.io/badge/version-2.6.0-blue.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.13-green.svg)](https://www.python.org/downloads/)
[![Django](https://img.shields.io/badge/django-5.2_LTS-green.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Sistema Django com API REST para gestão de conteúdos educacionais, quizzes interativos, rankings e gamificação.

> 📝 **Novidades da v2.6**: Confira todas as mudanças no [CHANGELOG.md](CHANGELOG.md)

## 🌐 Aplicação Online

A aplicação está disponível online em: **[https://kombinu.onrender.com](https://kombinu.onrender.com)**

### Acesso Rápido à Documentação da API

- **Documentação Swagger**: [https://kombinu.onrender.com/api/docs/](https://kombinu.onrender.com/api/docs/)
- **Documentação ReDoc**: [https://kombinu.onrender.com/api/redoc/](https://kombinu.onrender.com/api/redoc/)
- **Schema OpenAPI**: [https://kombinu.onrender.com/api/schema/](https://kombinu.onrender.com/api/schema/)

## Funcionalidades

### 🎯 Sistema de Conteúdos
- Gestão completa de conteúdos educacionais (texto, vídeo, quiz)
- Sistema de permissões (criadores podem editar, todos podem visualizar)
- API REST para CRUD completo

### 📝 Sistema de Quizzes
- Criação e gestão de questionários interativos
- Múltiplas opções de resposta por pergunta
- Submissão e correção automática
- Cálculo de pontuação e feedback

### 🏆 Sistema de Rankings
- Rastreamento de pontuações por usuário
- Rankings globais
- Gamificação educacional

### 👥 Autenticação
- **JWT Authentication**: Sistema seguro com tokens de acesso e refresh
- **Tipos de Usuário**: Creator (criador de conteúdo) e Learner (estudante)
- **Gestão de Perfis**: Registro, login e gerenciamento de perfil

### 📚 Documentação da API
- **Swagger UI**: Interface interativa para testar endpoints
- **ReDoc**: Documentação alternativa elegante
- **OpenAPI 3.0**: Schema completo disponível

## Requisitos

Antes de iniciar, certifique-se de ter instalado:

- Python 3.13 (fixado em `.python-version`, que o Render lê no build)
- Django 5.2 LTS (suporte até Abril de 2028)
- Django REST Framework
- Pip e virtualenv (recomendado)

## Instalação e Configuração

1. **Clone este repositório:**

   ```bash
   git clone https://github.com/Emcy963/Kombinu.git
   cd Kombinu
   ```

2. **Crie e ative um ambiente virtual:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate     # Windows
   ```

3. **Configure as variáveis de ambiente:**

   ```bash
   # Copie o arquivo de exemplo
   copy .env.example .env  # Windows
   # cp .env.example .env  # Linux/macOS
   
   # Edite o arquivo .env e configure:
   # - SECRET_KEY (gere uma nova chave)
   # - DEBUG=True (para desenvolvimento)
   # - ALLOWED_HOSTS=localhost,127.0.0.1
   # - CORS_ALLOWED_ORIGINS=http://localhost:5173 (CORS fechado por omissão)
   ```

   Em produção (`DEBUG=False`) a app assume que está atrás de um proxy que
   termina o TLS e envia `X-Forwarded-Proto` (caso do Render): redirecciona
   para HTTPS, envia HSTS (`SECURE_HSTS_SECONDS`, 3600 por omissão) e marca
   as cookies como seguras. Ver `.env.example` para todas as variáveis.

4. **Instale as dependências:**

   ```bash
   pip install -r requirements.txt
   ```

5. **Configure as migrações do banco de dados:**

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Crie um superusuário:**

   ```bash
   python manage.py createsuperuser
   ```

   Para criar o 1.º admin de uma organização (escola), com password temporária
   de troca obrigatória, mostrada uma única vez:

   ```bash
   python manage.py criar_admin_organizacao <slug-ou-código-da-escola> --email admin@escola.ao --first-name Nome
   ```

7. **Inicie o servidor:**

   ```bash
   python manage.py runserver
   ```

8. **Acesse o sistema localmente:**

   - **API Docs (Swagger)**: [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/)
   - **API ReDoc**: [http://127.0.0.1:8000/api/redoc/](http://127.0.0.1:8000/api/redoc/)
   - **Admin**: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

### Dados de demonstração (`seed_demo`)

O comando enche a plataforma com dados fictícios para demonstrações. Cria duas escolas (`demo-uan` e `demo-colegio-kiala`), 24 contas em `@demo.kombinu.com` e 28 conteúdos (15 no marketplace). Cria também quizzes com submissões, trilhas publicadas com progresso, enquetes com votos e notificações.

Foi pensado para correr também contra uma base remota. Faz cerca de 180 consultas na 1.ª execução e cerca de 35 numa repetição, e mostra uma linha de progresso por fase. Com 200 ms por consulta, a 1.ª execução com `--set-password` demora cerca de 40 s. Com passwords geradas, junta-se o tempo dos hashes (um por conta, em paralelo).

```bash
python manage.py seed_demo                          # cria (ou completa) os dados demo
python manage.py seed_demo --redefinir-passwords    # gera passwords novas para as contas demo
python manage.py seed_demo --set-password           # pede (sem eco) uma password para todas as contas demo
python manage.py seed_demo --limpar                 # remove só os dados demo
```

- **Idempotente:** correr de novo não duplica nada.
- **Passwords:** a prioridade é `--set-password` > `SEED_DEMO_PASSWORD` > gerada com `secrets`.
  - Uma password escolhida nunca é impressa; a tabela mostra só email e papel. As geradas aparecem uma única vez no fim, numa tabela email/papel/password.
  - `--set-password` sem valor pede a password duas vezes, sem eco, e não a deixa no histórico do terminal nem na lista de processos. Também aceita `--set-password=<valor>`, mas avisa que a password fica no histórico da shell.
  - A password escolhida passa pelos validadores do Django; se for recusada, o comando pára sem alterar nada.
  - Também se aplica às contas demo que já existem, o que serve para as repor antes de uma demonstração. Contas fora de `@demo.kombinu.com` nunca são tocadas.
  - A variável `SEED_DEMO_PASSWORD` exige pelo menos 12 caracteres.
  - As contas demo não têm troca obrigatória de password.
- **Domínio reservado:** o domínio `@demo.kombinu.com` não aceita registos nem provisionamento. Se já existirem contas nesse domínio antes da 1.ª execução, o comando recusa correr. Qualquer reposição de password invalida os tokens antigos.
- **Produção:** com `DEBUG=False`, o comando só corre com `--confirmar-producao`, incluindo o `--limpar`.
- **Limpeza segura:** o `--limpar` apaga só as contas `@demo.kombinu.com`, as organizações `demo-*` e o que delas depende. Se houver dados reais ligados aos de demonstração, recusa e não apaga nada. É o caso, por exemplo, de um utilizador real que respondeu a um quiz demo ou de uma trilha real que usa um conteúdo demo.

## Testes

O projeto possui uma suíte completa de testes usando pytest.

### Executando os Testes

```bash
# Executar todos os testes
pytest

# Executar com verbose
pytest -v

# Executar testes de um app específico
pytest apps/accounts/tests.py
pytest apps/contents/tests.py
pytest apps/quizzes/tests.py

# Executar com cobertura (requer pytest-cov)
pytest --cov=apps
```

O `pytest` usa `core/settings_test.py` (definido no `pytest.ini`), que herda
de `core/settings.py` e só troca o hasher de passwords por MD5 para a suite
correr rápido. Esse ficheiro nunca é carregado em produção: `manage.py`, WSGI
e ASGI usam `core.settings`. Com `python manage.py test` o hasher é o real
(Argon2id) e a suite fica mais lenta.

**Hasher de passwords:** Argon2id com os parâmetros mínimos da OWASP (19 MiB,
2 iterações, 1 thread; ver `apps/accounts/hashers.py`), em vez dos 100 MiB por
hash do `Argon2PasswordHasher` do Django, que esgotariam a RAM com muitos
logins em simultâneo. O PBKDF2 continua configurado para verificar as senhas
antigas, que passam a Argon2id sozinhas no login seguinte.

### Cobertura de Testes

- **accounts**: 20 testes (autenticação, perfil com XP/nível, dashboard stats, cursos do aprendiz, token refresh)
- **contents**: 11 testes (CRUD e permissões)
- **quizzes**: 18 testes (criação, submissão, score XP, rate limit OpenTDB, fallback PT→EN)
- **rankings**: 11 testes (ordenação, posição, agregação, isolamento entre utilizadores)
- **Total**: 66 testes ✅

## Estrutura do Projeto

```text
backend/
├── apps/
│   ├── accounts/          # Autenticação, perfis e dashboard
│   ├── contents/          # Conteúdos educacionais
│   ├── quizzes/           # Quizzes, submissões e scoring XP
│   └── rankings/          # Rankings globais
├── core/                  # settings.py, urls.py, wsgi.py
├── manage.py
├── requirements.txt
└── build.sh               # Script de deploy (Render)
```

## Rotas Principais

### Interface Web

| Rota | Descrição |
|------|-----------|
| `/` | Página inicial |
| `/login/` | Login de usuários |
| `/dashboard/` | Dashboard (requer login) |
| `/termos_condicoes/` | Termos e condições |

### API REST

| Rota | Método | Descrição |
| --- | --- | --- |
| `/api/auth/register/` | POST | Registo de utilizadores. Cria sempre uma conta `learner`. Obrigatórios: `email`, `password`, `ano_nascimento` (1900 até ao ano actual) e `aceita_termos: true`; opcionais: `first_name`, `last_name` e `marketing_opt_in`. O `user_type` está obsoleto: continua aceite mas é ignorado, e a promoção a criador faz-se pelo admin. A resposta é `{message, user_id, email, user_type}`. Grava a versão dos termos aceite (3.0) e o estado do consentimento do encarregado: `pendente` se a idade, calculada só pelo ano, for inferior a `IDADE_LIMITE_CONSENTIMENTO` (18), senão `nao_necessario` |
| `/api/auth/login/` | POST | Login por email — devolve `access_token`, `refresh_token` e `user` (com `memberships` e `must_change_password`) |
| `/api/auth/institutional/login/` | POST | Login institucional: `{ school_code, student_code, password }` (`school_code` = código de 6 caracteres da escola, não o UUID). Mesmo envelope; qualquer falha → 401 igual |
| `/api/auth/password/change/` | POST | `{ current_password, new_password }` → novos `access_token`/`refresh_token`; os anteriores deixam de valer |
| `/api/auth/token/refresh/` | POST | `{ refresh }` → `{ access, refresh }`: novo access e novo refresh (guardar os dois). 401 `token_not_valid` se a password mudou depois de o refresh ser emitido |
| `/api/auth/profile/` | GET | Perfil com nome, pontos (XP) e nível |
| `/api/dashboard/learner/stats/` | GET | Estatísticas do aprendiz |
| `/api/dashboard/learner/courses/` | GET | Cursos frequentados |
| `/api/dashboard/creator/stats/` | GET | Estatísticas do criador |
| `/api/contents/` | GET/POST | Listar e criar conteúdos. Filtros: `category`, `creator`, `cadeira` (id), `has_quiz` e `search`, sempre dentro do `X-Workspace`. Cada conteúdo traz `cadeira` (id ou `null`), que também se pode enviar ao criar ou editar |
| `/api/contents/{id}/` | GET/PUT/DELETE | Detalhes de um conteúdo |
| `/api/quizzes/{id}/` | GET | Detalhes de um quiz |
| `/api/quizzes/contents/{content_id}/generate-quiz/` | POST | **Desligado:** devolve `410 Gone` até chegar a geração por IA. Usar o `manual-quiz/` |
| `/api/quizzes/{content_id}/manual/` | POST | Criar quiz manual (creator) |
| `/api/quizzes/{quiz_id}/submit/` | POST | Submeter respostas — devolve XP ganho |
| `/api/rankings/global/` | GET | Ranking global com posição do utilizador |
| `/api/rankings/me/` | GET | XP e ofensiva do próprio utilizador: `xp_total` (carteira global), `xp_workspace` (workspace activo), `level`, `streak` (dias seguidos com XP, em Africa/Luanda, terminando hoje ou ontem), `best_streak` e `last_activity_date`. Respeita o `X-Workspace` |
| `/api/enquetes/` | GET/POST | Enquetes do `X-Workspace`: publicadas e fechadas, mais os rascunhos do próprio. POST (teacher/admin; `creator` no marketplace) cria em `rascunho` |
| `/api/enquetes/{id}/publish/` · `/close/` | POST | Criador: `rascunho` → `activa` (publicada) → `encerrada` (fechada). Transição inválida → 409. Só se vota em `activa` |
| `/api/trilhas/` | GET/POST | Listar trilhas do `X-Workspace` (publicadas, mais os rascunhos do próprio) e criar (teacher/admin na escola, `creator` no marketplace). Nasce rascunho. Filtro `?cadeira=<id>`; a lista vem da mais recente para a mais antiga, por isso a primeira trilha publicada de uma cadeira no contexto activo é o primeiro resultado (usada no fim do onboarding) |
| `/api/me/` | GET/PATCH | Perfil académico do próprio utilizador (onboarding), criado no primeiro GET; sem id no URL. Também devolve `ano_nascimento`, `marketing_opt_in` e `consentimento_encarregado` (da conta); destes, o PATCH só altera o `marketing_opt_in`. Resposta: `id`, `nome`, `email`, `intent`, `instituicao` (`{id, nome, sigla, provincia}` ou `null`), `instituicao_outra`, `curso`, `ano` (1 a 6), `cadeira_foco` (`{id, nome}` ou `null`), `minutos_por_dia` (5/15/30/60), `provincia` (slug de uma das 21 províncias), `ano_entrada` e `onboarding_completed_at`. No PATCH todos os campos são opcionais, `instituicao` e `cadeira_foco` recebem ids, e `"concluir": true` grava a conclusão (só da primeira vez). Se mudar a `instituicao` sem `provincia` no pedido, a província passa a ser a da instituição |
| `/api/instituicoes/` | GET | Catálogo de instituições (`id`, `nome`, `sigla`, `provincia`), sem paginação. Preenche-se pelo admin |
| `/api/cadeiras/` | GET | Catálogo global de cadeiras (`id`, `nome`, `curso`), igual em todos os workspaces e sem paginação. Filtro `?curso=` (sem diferenciar maiúsculas). Preenche-se pelo admin |
| `/api/trilhas/{id}/` | GET/PATCH/DELETE | Detalhe; editar e apagar só pelo criador. DELETE → 409 se algum aluno já tem progresso |
| `/api/trilhas/{id}/publish/` | POST | Publicar (exige pelo menos um passo) |
| `/api/trilhas/{id}/archive/` · `/unarchive/` | POST | Arquivar ou desarquivar (criador). Arquivada, sai das listagens dos alunos; o progresso mantém-se |
| `/api/trilhas/{id}/items/` | POST | Acrescentar um passo `{ kind, targetId, titleOverride?, summary?, minutes?, xpReward? }`; o alvo tem de ser do mesmo workspace da trilha |
| `/api/trilhas/{id}/items/{itemId}/` | PATCH/DELETE | Editar metadados ou remover um passo (409 se tem progresso) |
| `/api/trilhas/{id}/items/reorder/` | POST | `{ itemIds: [...] }` com todos os passos pela nova ordem |
| `/api/notifications/` | GET | Notificações do próprio utilizador no `X-Workspace` activo (escola → só dessa escola; marketplace → só do marketplace), paginadas; `?unread=true`. Item: `{ id, category, tone, title, body, at, read, target: { kind, id } \| null }` |
| `/api/notifications/unread-count/` | GET | `{ count }` no contexto activo. Para polling (sugestão: 60 s); throttle 60/min |
| `/api/notifications/{id}/read/` | POST | Marcar como lida (idempotente). De outro utilizador ou contexto → 404 |
| `/api/notifications/read-all/` | POST | Marcar todas como lidas, só no contexto activo → `{ updated }` |
| `/api/tenancy/members/` | GET | Membros da organização do `X-Workspace` (só admin), paginado; filtros `role`, `is_active`, `search`. Nunca devolve o email técnico |
| `/api/tenancy/members/{id}/deactivate/` · `/reactivate/` | POST | Desactivar ou reactivar a pertença (a conta e o XP mantêm-se). Um admin não se desactiva a si próprio e a organização mantém sempre um admin activo |
| `/api/tenancy/members/{id}/reset-password/` | POST | Nova password temporária (7 dias, troca obrigatória), mostrada uma vez; revoga as sessões. Só para contas provisionadas pela organização e sem pertença a outra |
| `/api/tenancy/marketplace-visit/` | POST | Chamado pelo seletor de workspace ao mudar para o marketplace. Regista a 1.ª entrada no marketplace por escola de origem (idempotente). Responde sempre 204 |
| `/api/tenancy/members/bulk/` | POST | Provisionamento em lote pelo admin da organização do `X-Workspace`: `{ dry_run, rows: [{ student_code, first_name, last_name, role, academic_year, faculty, course, email }] }`. Tudo ou nada, até `PROVISIONING_MAX_ROWS` linhas (20 por omissão); devolve as passwords temporárias uma única vez |

**Workspace activo (`X-Workspace`):** os endpoints de conteúdos, quizzes,
ranking, dashboards, trilhas, enquetes e organizações leem o header
`X-Workspace` (UUID da organização, o `organizacao_id` de `user.memberships`,
ou `marketplace`; ausente = marketplace). Exige pertença activa: UUID inválido
→ 400, sem pertença → 403, objectos de outro contexto → 404. O Swagger mostra
o header em cada um destes endpoints.

**Limites de pedidos (provisórios):** login 120/min por IP e 5/min por conta;
registo 10/hora por IP; refresh 30/min por IP. Acima do limite a API devolve
`429 Too Many Requests`, com o cabeçalho `Retry-After` e a mensagem
`{"detail": "Demasiadas tentativas. Tenta novamente dentro de N segundos."}`.

**IP do cliente atrás do proxy (`DRF_NUM_PROXIES`):** os limites por IP lêem o
IP do `X-Forwarded-For`. Sem `DRF_NUM_PROXIES`, o DRF usa o cabeçalho inteiro
como chave, e como o cliente controla o início do cabeçalho, consegue fugir ao
limite por IP. No Render o pedido passa por Cloudflare → proxy do Render → app,
e o cabeçalho chega como `<o que o cliente enviou>, <IP do cliente>, <IP do
nó Cloudflare>`: o Render acrescenta, não substitui. O DRF usa a entrada
`DRF_NUM_PROXIES` posições a contar da direita, por isso o valor proposto é
**`2`** (o IP do cliente, ignorando o nó Cloudflare). Com `1`, todos os
utilizadores que passam pelo mesmo nó Cloudflare partilhariam o limite. Este
valor vem de um exemplo publicado por um cliente do Render, não da
documentação oficial: confirma-o depois de o definir, por exemplo com pedidos
de duas redes diferentes, cada uma a esgotar o seu próprio limite sem afectar
a outra. Na submissão de quiz, cada pergunta só pode ser
respondida uma vez por pedido (respostas repetidas devolvem `400`). A troca de
password está limitada a 10/hora por utilizador (provisório).

**Troca obrigatória:** enquanto `user.must_change_password` for `true`, qualquer
endpoint autenticado devolve `403 { "detail", "code": "password_change_required" }`,
excepto `POST /api/auth/password/change/` e o refresh do token.

### Documentação

| Rota | Descrição | URL de Produção |
|------|-----------|----------------|
| `/api/docs/` | Documentação Swagger | [https://kombinu.onrender.com/api/docs/](https://kombinu.onrender.com/api/docs/) |
| `/api/redoc/` | Documentação ReDoc | [https://kombinu.onrender.com/api/redoc/](https://kombinu.onrender.com/api/redoc/) |
| `/api/schema/` | Schema OpenAPI | [https://kombinu.onrender.com/api/schema/](https://kombinu.onrender.com/api/schema/) |

## Testando a API

### Ambiente de Produção

Para testar a API diretamente no ambiente de produção, utilize a base URL:
```
https://kombinu.onrender.com/api/
```

### Exemplo de Uso

```bash
# Registrar um novo usuário
curl -X POST https://kombinu.onrender.com/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "securepassword123",
    "ano_nascimento": 2005,
    "aceita_termos": true
  }'

# Fazer login
curl -X POST https://kombinu.onrender.com/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "securepassword123"
  }'
```

## Documentação da API

Para informações detalhadas sobre como usar a API, consulte nossa **[Documentação da API](docs/API_DOCUMENTATION.md)** que inclui:

- Guia completo de endpoints
- Exemplos de requisições e respostas
- Códigos de erro e suas descrições
- Fluxos de uso comuns
- Boas práticas de implementação

Você também pode acessar a documentação interativa através das rotas:
- **Produção**: 

[https://kombinu.onrender.com/api/docs/](https://kombinu.onrender.com/api/docs/) (Swagger) ou [https://kombinu.onrender.com/api/redoc/](https://kombinu.onrender.com/api/redoc/) (ReDoc)

- **Desenvolvimento**: `/api/docs/` (Swagger) ou `/api/redoc/` (ReDoc)

## Tecnologias Utilizadas

- **Backend**: Django 5.2 LTS, Django REST Framework
- **Banco de Dados**: SQLite (desenvolvimento) / PostgreSQL (produção)
- **Autenticação**: Token-based authentication
- **Documentação**: drf-spectacular (OpenAPI/Swagger)
- **Frontend**: HTML5, CSS3, JavaScript
- **Deploy**: Render (Produção)

## Contribuição

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## Autores

### Chefe do Projeto

- **Anderson Cafurica** - *Desenvolvedor Principal*
  - GitHub: [@Emicy963](https://github.com/Emicy963)
  - Email: andersonpaulo931@gmail.com
  - LinkedIn: [Anderson Cafurica](https://linkedin.com/in/anderson-cafurica)

### Equipe de Desenvolvimento

- **DOMAG Tech** - *Desenvolvimento e Suporte*

## Contato

Se tiver alguma dúvida, sugestão ou quiser contribuir com o projeto, entre em contato através do GitHub ou pelos contatos do chefe do projeto listados acima.

---

**Kombinu** - Transformando a educação através da tecnologia 🚀

**🌐 Acesse agora**: [https://kombinu.onrender.com](https://kombinu.onrender.com)
