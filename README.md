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
(PBKDF2) e a suite fica muito mais lenta.

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
| `/api/auth/register/` | POST | Registo de utilizadores |
| `/api/auth/login/` | POST | Login por email — devolve `access_token`, `refresh_token` e `user` (com `memberships` e `must_change_password`) |
| `/api/auth/institutional/login/` | POST | Login institucional: `{ school_code, student_code, password }` (`school_code` = código de 6 caracteres da escola, não o UUID). Mesmo envelope; qualquer falha → 401 igual |
| `/api/auth/password/change/` | POST | `{ current_password, new_password }` → novos `access_token`/`refresh_token`; os anteriores deixam de valer |
| `/api/auth/token/refresh/` | POST | `{ refresh }` → `{ access, refresh }`: novo access e novo refresh (guardar os dois). 401 `token_not_valid` se a password mudou depois de o refresh ser emitido |
| `/api/auth/profile/` | GET | Perfil com nome, pontos (XP) e nível |
| `/api/dashboard/learner/stats/` | GET | Estatísticas do aprendiz |
| `/api/dashboard/learner/courses/` | GET | Cursos frequentados |
| `/api/dashboard/creator/stats/` | GET | Estatísticas do criador |
| `/api/contents/` | GET/POST | Listar e criar conteúdos |
| `/api/contents/{id}/` | GET/PUT/DELETE | Detalhes de um conteúdo |
| `/api/quizzes/{id}/` | GET | Detalhes de um quiz |
| `/api/quizzes/{content_id}/generate/` | POST | Gerar quiz via OpenTDB (creator) |
| `/api/quizzes/{content_id}/manual/` | POST | Criar quiz manual (creator) |
| `/api/quizzes/{quiz_id}/submit/` | POST | Submeter respostas — devolve XP ganho |
| `/api/rankings/global/` | GET | Ranking global com posição do utilizador |
| `/api/enquetes/` | GET/POST | Enquetes do `X-Workspace`: publicadas e fechadas, mais os rascunhos do próprio. POST (teacher/admin; `creator` no marketplace) cria em `rascunho` |
| `/api/enquetes/{id}/publish/` · `/close/` | POST | Criador: `rascunho` → `activa` (publicada) → `encerrada` (fechada). Transição inválida → 409. Só se vota em `activa` |
| `/api/trilhas/` | GET/POST | Listar trilhas do `X-Workspace` (publicadas, mais os rascunhos do próprio) e criar (teacher/admin na escola, `creator` no marketplace). Nasce rascunho |
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

**Limites de pedidos (provisórios):** login 30/min por IP e 5/min por conta;
registo 10/hora por IP; refresh 30/min por IP. Acima do limite a API devolve
`429 Too Many Requests`. Na submissão de quiz, cada pergunta só pode ser
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
    "username": "testuser",
    "email": "test@example.com",
    "password": "securepassword123"
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
