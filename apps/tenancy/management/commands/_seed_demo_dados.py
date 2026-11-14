"""
Dados do `seed_demo`. Tudo fictício e identificável como demonstração: contas
em `@demo.kombinu.com` e organizações com slug `demo-*`.
"""

from apps.accounts.institutional import DEMO_EMAIL_DOMAIN  # noqa: F401

# chave -> dados da organização (slug fixo: é por ele que o --limpar a encontra)
ORGANIZACOES = {
    "uan": {
        "slug": "demo-uan",
        "name": "Universidade Agostinho Neto (Demo)",
        "org_type": "escola",
    },
    "kiala": {
        "slug": "demo-colegio-kiala",
        "name": "Colégio Kiala (Demo)",
        "org_type": "escola",
    },
}

# (chave, primeiro nome, apelido, user_type)
# As memberships estão em MEMBROS; quem não aparece lá é só do marketplace.
UTILIZADORES = [
    ("admin_uan", "Helena", "Manuel", "learner"),
    ("admin_kiala", "Joaquim", "Tchissola", "learner"),
    ("esperanca", "Esperança", "Kiluange", "creator"),
    ("mateus", "Mateus", "Ndala", "creator"),
    ("teresa", "Teresa", "Lukamba", "creator"),
    ("domingos", "Domingos", "Sebastião", "creator"),
    ("isabel", "Isabel", "Cassoma", "creator"),
    ("nadia", "Nádia", "Mbala", "creator"),
    ("paulo", "Paulo", "Kassoma", "creator"),
    # estudantes
    ("ana", "Ana", "Kiame", "learner"),
    ("bruno", "Bruno", "Fortunato", "learner"),
    ("celeste", "Celeste", "Mavinga", "learner"),
    ("dario", "Dário", "Muxima", "learner"),
    ("edna", "Edna", "Cambuta", "learner"),
    ("filipe", "Filipe", "Ngola", "learner"),
    ("graca", "Graça", "Tchimuku", "learner"),
    ("hugo", "Hugo", "Lussati", "learner"),
    ("ines", "Inês", "Bumba", "learner"),
    ("jose", "José", "Kapinga", "learner"),
    ("luisa", "Luísa", "Nzinga", "learner"),
    ("marcio", "Márcio", "Chipenda", "learner"),
    ("neusa", "Neusa", "Kalandula", "learner"),
    ("osvaldo", "Osvaldo", "Mukuta", "learner"),
    ("rosa", "Rosa", "Kianda", "learner"),
]

# (utilizador, organização, papel, ano, faculdade, curso, número de aluno)
MEMBROS = [
    ("admin_uan", "uan", "admin", "", "", "", None),
    ("esperanca", "uan", "teacher", "", "Engenharia", "Engenharia Informática", None),
    ("mateus", "uan", "teacher", "", "Economia", "Economia", None),
    ("teresa", "uan", "teacher", "", "Arquitectura", "Design", None),
    ("admin_kiala", "kiala", "admin", "", "", "", None),
    ("domingos", "kiala", "teacher", "", "", "Informática", None),
    ("isabel", "kiala", "teacher", "", "", "Empreendedorismo", None),
    # UAN
    ("celeste", "uan", "student", "1.º ano", "Engenharia", "Engenharia Informática", "DEMO-U001"),
    ("dario", "uan", "student", "1.º ano", "Engenharia", "Engenharia Informática", "DEMO-U002"),
    ("edna", "uan", "student", "2.º ano", "Economia", "Economia", "DEMO-U003"),
    ("filipe", "uan", "student", "2.º ano", "Engenharia", "Engenharia Informática", "DEMO-U004"),
    ("graca", "uan", "student", "3.º ano", "Arquitectura", "Design", "DEMO-U005"),
    # Kiala
    ("hugo", "kiala", "student", "10.ª classe", "", "Informática", "DEMO-K001"),
    ("ines", "kiala", "student", "10.ª classe", "", "Informática", "DEMO-K002"),
    ("jose", "kiala", "student", "11.ª classe", "", "Ciências Económicas", "DEMO-K003"),
    ("luisa", "kiala", "student", "12.ª classe", "", "Ciências Económicas", "DEMO-K004"),
    # nas duas escolas
    ("marcio", "uan", "student", "1.º ano", "Economia", "Gestão", "DEMO-U006"),
    ("marcio", "kiala", "student", "12.ª classe", "", "Ciências Económicas", "DEMO-K005"),
    ("neusa", "uan", "student", "2.º ano", "Engenharia", "Engenharia Informática", "DEMO-U007"),
    ("neusa", "kiala", "student", "12.ª classe", "", "Informática", "DEMO-K006"),
]
# Só marketplace: ana, bruno, osvaldo, rosa.

# Probabilidade de cada estudante acertar numa pergunta (dá rankings variados).
APTIDAO = {
    "ana": 0.9, "bruno": 0.55, "celeste": 0.85, "dario": 0.6, "edna": 0.75,
    "filipe": 0.95, "graca": 0.5, "hugo": 0.8, "ines": 0.65, "jose": 0.7,
    "luisa": 0.9, "marcio": 0.6, "neusa": 0.85, "osvaldo": 0.45, "rosa": 0.7,
}


def _q(pergunta, opcoes, certa):
    return {"question": pergunta, "options": opcoes, "correct": certa}


# Conteúdos: chave -> dados. `org` None = marketplace.
CONTEUDOS = {
    # ------------------------------------------------------------ marketplace
    "py_intro": {
        "org": None, "creator": "nadia", "category": "tecnologia",
        "level": "Iniciante", "duration": "45 min",
        "tags": "python,programação,iniciantes",
        "title": "Introdução à programação com Python",
        "description": "Os primeiros passos em Python: instalar, escrever e correr o primeiro programa.",
        "paragraphs": [
            "Python é uma linguagem de programação conhecida pela sintaxe simples e legível. É usada em desenvolvimento web, análise de dados, automação de tarefas e inteligência artificial, o que a torna uma boa primeira linguagem para quem está a começar.",
            "Para programar em Python basta instalar o interpretador a partir do site oficial e usar um editor de texto. O primeiro programa costuma ser uma única linha: print(\"Olá, Luanda!\"). Ao correr o ficheiro, o interpretador lê as instruções de cima para baixo e mostra o resultado no terminal.",
            "Ao longo deste módulo vais conhecer os tipos de dados básicos (números, texto e valores lógicos), aprender a guardar informação em variáveis e a pedir dados ao utilizador com a função input(). No fim, vais escrever um pequeno programa que calcula o troco de uma compra em kwanzas.",
        ],
        "questions": [
            _q("Que função mostra texto no ecrã em Python?", ["print()", "input()", "show()", "echo()"], 0),
            _q("Que função lê dados escritos pelo utilizador?", ["read()", "input()", "scan()", "get()"], 1),
            _q("Qual destes é um valor do tipo texto (string)?", ["42", "True", "\"Kombinu\"", "3.14"], 2),
        ],
    },
    "logica": {
        "org": None, "creator": "nadia", "category": "tecnologia",
        "level": "Iniciante", "duration": "40 min",
        "tags": "lógica,algoritmos,condições",
        "title": "Lógica de programação: variáveis e condições",
        "description": "Como um programa toma decisões com if, elif e else.",
        "paragraphs": [
            "Uma variável é um nome que aponta para um valor guardado na memória. Em Python escreve-se, por exemplo, idade = 19. O valor pode mudar ao longo do programa, e é isso que permite que o mesmo código funcione para dados diferentes.",
            "As condições permitem que o programa escolha entre caminhos. Com if, elif e else comparamos valores usando operadores como ==, !=, <, > e combinamo-los com and, or e not. Por exemplo: se a nota for maior ou igual a 10, o estudante está aprovado; caso contrário, vai a exame.",
            "Um erro comum é confundir = (atribuição) com == (comparação). Outro é esquecer a indentação: em Python, os blocos de código dentro de um if são definidos pelos espaços no início da linha. Pratica com pequenos exercícios até as condições ficarem naturais.",
        ],
        "questions": [
            _q("Que operador compara se dois valores são iguais?", ["=", "==", "!=", "=>"], 1),
            _q("Que palavra-chave trata o caso em que nenhuma condição anterior foi verdadeira?", ["elif", "then", "else", "default"], 2),
            _q("Em Python, o que define os blocos de código dentro de um if?", ["Chavetas {}", "A indentação", "Ponto e vírgula", "A palavra end"], 1),
        ],
    },
    "ciclos": {
        "org": None, "creator": "nadia", "category": "tecnologia",
        "level": "Intermediário", "duration": "50 min",
        "tags": "python,ciclos,listas",
        "title": "Estruturas de repetição em Python",
        "description": "Ciclos for e while para repetir tarefas sem copiar código.",
        "paragraphs": [
            "Quando uma tarefa se repete, não faz sentido escrever o mesmo código várias vezes. O ciclo for percorre os elementos de uma sequência, como uma lista de nomes ou um intervalo de números criado com range().",
            "O ciclo while repete um bloco enquanto uma condição for verdadeira. É útil quando não sabemos à partida quantas repetições vão ser precisas, por exemplo ao pedir uma senha até o utilizador acertar. É preciso garantir que a condição deixa de ser verdadeira em algum momento, para evitar ciclos infinitos.",
            "As instruções break e continue dão mais controlo: break termina o ciclo e continue salta para a próxima repetição. Combinando ciclos com listas, consegues calcular médias de notas, procurar valores e filtrar dados de forma eficiente.",
        ],
        "questions": [
            _q("O que devolve range(3) quando percorrido?", ["1, 2, 3", "0, 1, 2", "0, 1, 2, 3", "3"], 1),
            _q("Que instrução termina imediatamente um ciclo?", ["stop", "exit", "break", "continue"], 2),
            _q("Que ciclo é mais indicado quando não se sabe quantas repetições serão precisas?", ["for", "while", "if", "def"], 1),
        ],
    },
    "html_css": {
        "org": None, "creator": "nadia", "category": "tecnologia",
        "level": "Iniciante", "duration": "60 min",
        "tags": "web,html,css",
        "title": "Introdução ao HTML e CSS",
        "description": "A estrutura e o estilo de uma página web, do zero.",
        "paragraphs": [
            "Todas as páginas web assentam em HTML, a linguagem que descreve a estrutura do conteúdo: títulos, parágrafos, imagens, ligações e formulários. Cada elemento é marcado com etiquetas, como <h1> para o título principal ou <p> para um parágrafo.",
            "O CSS trata da apresentação: cores, tipos de letra, espaçamentos e disposição dos elementos. Separar estrutura (HTML) de estilo (CSS) facilita a manutenção, porque podemos mudar o aspecto de um site inteiro sem tocar no conteúdo.",
            "Hoje a maioria das pessoas em Angola acede à internet pelo telemóvel. Por isso, desde o início, vamos pensar em páginas responsivas, que se adaptam a ecrãs pequenos, usando unidades relativas e media queries.",
        ],
        "questions": [
            _q("Que linguagem define a estrutura de uma página web?", ["CSS", "HTML", "Python", "SQL"], 1),
            _q("Que etiqueta HTML representa um parágrafo?", ["<p>", "<para>", "<h1>", "<div>"], 0),
            _q("Para que servem as media queries em CSS?", ["Ligar a bases de dados", "Adaptar o estilo ao tamanho do ecrã", "Enviar formulários", "Criar animações 3D"], 1),
        ],
    },
    "sql": {
        "org": None, "creator": "nadia", "category": "tecnologia",
        "level": "Intermediário", "duration": "55 min",
        "tags": "sql,bases de dados,dados",
        "title": "Bases de dados relacionais e SQL",
        "description": "Tabelas, chaves e as consultas SQL mais usadas.",
        "paragraphs": [
            "Uma base de dados relacional organiza a informação em tabelas, com linhas (registos) e colunas (campos). Cada tabela tem normalmente uma chave primária que identifica cada registo de forma única, como o número de estudante.",
            "As tabelas relacionam-se através de chaves estrangeiras. Numa escola, a tabela de inscrições pode guardar o número do estudante e o código da disciplina, ligando as duas tabelas sem repetir dados.",
            "A linguagem SQL permite consultar e alterar os dados. As instruções mais usadas são SELECT (consultar), INSERT (inserir), UPDATE (actualizar) e DELETE (apagar). Com WHERE filtramos registos e com JOIN combinamos tabelas relacionadas.",
        ],
        "questions": [
            _q("Que instrução SQL serve para consultar dados?", ["INSERT", "SELECT", "UPDATE", "CREATE"], 1),
            _q("O que identifica de forma única cada registo de uma tabela?", ["A chave primária", "A chave estrangeira", "O índice", "A coluna nome"], 0),
            _q("Que cláusula combina linhas de tabelas relacionadas?", ["WHERE", "ORDER BY", "JOIN", "GROUP"], 2),
        ],
    },
    "seguranca": {
        "org": None, "creator": "nadia", "category": "tecnologia",
        "level": "Iniciante", "duration": "30 min",
        "tags": "segurança,privacidade,internet",
        "title": "Segurança digital no dia-a-dia",
        "description": "Palavras-passe, burlas por mensagem e boas práticas para proteger as tuas contas.",
        "paragraphs": [
            "A maior parte dos ataques não usa técnicas sofisticadas: aproveita palavras-passe fracas ou repetidas e mensagens enganosas. Uma boa palavra-passe é longa, única para cada serviço e guardada num gestor de palavras-passe.",
            "O phishing é uma burla em que alguém se faz passar por um banco, uma operadora ou um amigo para obter dados ou dinheiro. Desconfia de mensagens com urgência exagerada, ligações estranhas ou pedidos de códigos de confirmação: nenhuma entidade séria te pede esses códigos.",
            "Activa a verificação em dois passos sempre que o serviço o permitir e mantém o sistema e as aplicações do telemóvel actualizados. Pequenos hábitos reduzem muito o risco de perderes as tuas contas.",
        ],
        "questions": [
            _q("Qual é a melhor prática para palavras-passe?", ["Usar a mesma em todos os sites", "Usar uma longa e única por serviço", "Usar a data de nascimento", "Partilhá-la com amigos de confiança"], 1),
            _q("Um banco pede-te por SMS o código de confirmação que recebeste. O que fazer?", ["Enviar o código", "Ignorar e contactar o banco pelos canais oficiais", "Responder a pedir mais dados", "Reencaminhar a mensagem a amigos"], 1),
            _q("O que é a verificação em dois passos?", ["Escrever a palavra-passe duas vezes", "Um segundo factor além da palavra-passe", "Ter duas contas", "Mudar a palavra-passe duas vezes por ano"], 1),
        ],
    },
    "git": {
        "org": None, "creator": "nadia", "category": "tecnologia",
        "level": "Intermediário", "duration": "45 min",
        "tags": "git,versões,colaboração",
        "title": "Git e controlo de versões",
        "description": "Guardar o histórico do teu código e trabalhar em equipa sem perder alterações.",
        "paragraphs": [
            "O Git é um sistema de controlo de versões: regista cada alteração feita ao código, quem a fez e porquê. Se algo correr mal, é possível voltar a uma versão anterior sem perder trabalho.",
            "O fluxo básico tem três passos: alterar ficheiros, preparar as alterações com git add e registá-las com git commit, acompanhado de uma mensagem clara. Cada commit é uma fotografia do projecto num momento.",
            "Em equipa, cada pessoa trabalha numa branch própria e depois junta as alterações à branch principal através de um pedido de revisão. Assim, o código é revisto antes de chegar à produção.",
        ],
        "questions": None,
    },
    "abrir_empresa": {
        "org": None, "creator": "paulo", "category": "negocios",
        "level": "Iniciante", "duration": "35 min",
        "tags": "empreendedorismo,empresa,angola",
        "title": "Como abrir uma empresa em Angola",
        "description": "Os passos e as decisões principais antes de formalizar o teu negócio.",
        "paragraphs": [
            "Formalizar um negócio traz vantagens: permite facturar a empresas e ao Estado, aceder a crédito bancário e participar em concursos. Antes de tratar dos papéis, define bem o que vais vender, a quem e a que preço.",
            "Uma das primeiras decisões é a forma jurídica. Um empresário em nome individual responde com o seu património pessoal; numa sociedade por quotas, a responsabilidade fica, em regra, limitada ao capital da empresa. A escolha depende do risco do negócio e do número de sócios.",
            "O registo pode ser tratado nos balcões de atendimento único às empresas, onde se reúnem vários serviços num só sítio. Confirma sempre os documentos e as taxas em vigor junto das entidades oficiais, porque os procedimentos são actualizados com frequência.",
        ],
        "questions": [
            _q("Qual é uma vantagem de formalizar um negócio?", ["Deixar de pagar impostos", "Poder facturar a empresas e aceder a crédito", "Não precisar de clientes", "Evitar ter contabilidade"], 1),
            _q("Numa sociedade por quotas, a responsabilidade dos sócios é, em regra:", ["Ilimitada", "Limitada ao capital da empresa", "Só do sócio maioritário", "Inexistente"], 1),
            _q("Onde deves confirmar documentos e taxas para o registo?", ["Nas redes sociais", "Junto das entidades oficiais", "Com um amigo que já abriu empresa", "Não é preciso confirmar"], 1),
        ],
    },
    "financas_pme": {
        "org": None, "creator": "paulo", "category": "negocios",
        "level": "Iniciante", "duration": "40 min",
        "tags": "finanças,gestão,pme",
        "title": "Gestão financeira para pequenos negócios",
        "description": "Separar contas, controlar o fluxo de caixa e calcular a margem.",
        "paragraphs": [
            "O erro mais comum nos pequenos negócios é misturar o dinheiro da casa com o da empresa. Abre uma conta só para o negócio e paga a ti próprio um valor fixo, como se fosse um salário. Assim sabes se o negócio dá lucro de verdade.",
            "O fluxo de caixa mostra o dinheiro que entra e sai em cada semana ou mês. Um negócio pode vender muito e mesmo assim ficar sem dinheiro, se os clientes pagarem tarde e os fornecedores exigirem pagamento imediato. Regista todas as entradas e saídas, por mais pequenas que sejam.",
            "A margem é a diferença entre o preço de venda e o custo de cada produto. Se compras um artigo por 4 000 Kz e o vendes por 5 000 Kz, a margem é de 1 000 Kz, mas ainda tens de pagar renda, transporte e electricidade. Conhecer a margem ajuda a definir preços realistas.",
        ],
        "questions": [
            _q("Porque se deve ter uma conta bancária só para o negócio?", ["Para pagar menos impostos", "Para saber se o negócio dá lucro", "Porque é obrigatório para todos", "Para ter mais cartões"], 1),
            _q("Um artigo custa 4 000 Kz e é vendido a 5 000 Kz. Qual é a margem bruta?", ["500 Kz", "1 000 Kz", "4 000 Kz", "9 000 Kz"], 1),
            _q("O que mostra o fluxo de caixa?", ["O número de clientes", "O dinheiro que entra e sai num período", "O valor das acções", "A lista de produtos"], 1),
        ],
    },
    "marketing": {
        "org": None, "creator": "paulo", "category": "negocios",
        "level": "Intermediário", "duration": "45 min",
        "tags": "marketing,redes sociais,vendas",
        "title": "Marketing digital para negócios locais",
        "description": "Usar as redes sociais e o WhatsApp para chegar a clientes no teu bairro e na tua cidade.",
        "paragraphs": [
            "Para um negócio local, o marketing digital começa por estar onde os clientes já estão. Em Angola, isso significa sobretudo redes sociais e aplicações de mensagens. Um perfil completo, com horário, localização e contacto, já transmite confiança.",
            "Publica com regularidade conteúdo útil: fotografias reais dos produtos, preços claros e respostas a perguntas frequentes. Os testemunhos de clientes satisfeitos convencem mais do que qualquer anúncio.",
            "Mede os resultados. Pergunta aos clientes como te conheceram e acompanha que publicações geram mais mensagens. Com poucos recursos, é melhor fazer bem duas coisas do que mal dez.",
        ],
        "questions": [
            _q("Por onde deve começar o marketing digital de um negócio local?", ["Por anúncios na televisão", "Pelos canais onde os clientes já estão", "Por um site complexo", "Por cartazes no estrangeiro"], 1),
            _q("Que tipo de conteúdo costuma gerar mais confiança?", ["Imagens genéricas da internet", "Testemunhos de clientes reais", "Publicações sem preços", "Mensagens automáticas"], 1),
            _q("Qual é uma forma simples de medir resultados?", ["Perguntar aos clientes como te conheceram", "Publicar mais vezes por dia", "Mudar o logótipo", "Copiar a concorrência"], 0),
        ],
    },
    "pagamentos": {
        "org": None, "creator": "paulo", "category": "negocios",
        "level": "Intermediário", "duration": "30 min",
        "tags": "pagamentos,comércio electrónico,digital",
        "title": "Pagamentos digitais e comércio electrónico",
        "description": "Como aceitar pagamentos digitais e vender online com segurança.",
        "paragraphs": [
            "Aceitar pagamentos digitais reduz o manuseamento de dinheiro físico e facilita vendas à distância. As transferências e as carteiras móveis tornaram-se comuns, e muitos clientes já preferem pagar pelo telemóvel.",
            "Antes de começar a vender online, define como vais confirmar cada pagamento antes de entregar o produto. Os comprovativos podem ser falsificados: confirma sempre a entrada do valor na tua conta.",
            "Uma loja online não precisa de começar com um site próprio. Um catálogo nas redes sociais, um número de contacto e um processo claro de pagamento e entrega já permitem testar a procura com pouco investimento.",
        ],
        "questions": None,
    },
    "plano_negocio": {
        "org": None, "creator": "paulo", "category": "negocios",
        "level": "Iniciante", "duration": "35 min",
        "tags": "plano de negócios,estratégia,empreendedorismo",
        "title": "Plano de negócios numa página",
        "description": "Organizar a ideia de negócio num documento curto e prático.",
        "paragraphs": [
            "Um plano de negócios não tem de ter cinquenta páginas. Para começar, uma página bem pensada responde ao essencial: que problema resolves, para quem, como ganhas dinheiro e quanto precisas para arrancar.",
            "Descreve o cliente com detalhe: onde vive, quanto pode pagar e como compra hoje. Depois, identifica os concorrentes e o que te diferencia deles, seja o preço, a qualidade, a localização ou o atendimento.",
            "Termina com números simples: custos iniciais, custos mensais, preço médio e quantas vendas precisas por mês para cobrir os custos. Este ponto de equilíbrio é a primeira meta do teu negócio.",
        ],
        "questions": [
            _q("Qual destas perguntas deve um plano de negócios responder?", ["Qual é a cor preferida do dono", "Que problema resolves e para quem", "Quantos seguidores tens", "Qual é o nome do contabilista"], 1),
            _q("O que é o ponto de equilíbrio?", ["O número de vendas que cobre os custos", "O lucro máximo possível", "O preço do concorrente", "O valor do empréstimo"], 0),
            _q("Que aspecto pode diferenciar o teu negócio da concorrência?", ["O atendimento", "Ter o mesmo preço", "Copiar o produto", "Não ter contacto"], 0),
        ],
    },
    "design_principios": {
        "org": None, "creator": "nadia", "category": "design",
        "level": "Iniciante", "duration": "40 min",
        "tags": "design gráfico,composição,tipografia",
        "title": "Princípios de design gráfico",
        "description": "Contraste, alinhamento, repetição e proximidade aplicados a cartazes e publicações.",
        "paragraphs": [
            "O bom design comunica com clareza. Quatro princípios ajudam a organizar qualquer peça: contraste, alinhamento, repetição e proximidade. Aplicá-los de forma consistente melhora logo o aspecto de um cartaz ou de uma publicação nas redes sociais.",
            "O contraste cria hierarquia: o título deve destacar-se do texto secundário pelo tamanho, peso ou cor. O alinhamento dá ordem visual, ligando os elementos entre si. A repetição de cores e tipos de letra cria identidade.",
            "A proximidade agrupa o que está relacionado. A data, a hora e o local de um evento, por exemplo, devem aparecer juntos. Deixar espaço em branco também é uma decisão de design: dá respiro e guia o olhar.",
        ],
        "questions": [
            _q("Que princípio cria hierarquia entre título e texto?", ["Contraste", "Repetição", "Proximidade", "Simetria"], 0),
            _q("Data, hora e local de um evento devem aparecer juntos. Que princípio é este?", ["Alinhamento", "Proximidade", "Contraste", "Ritmo"], 1),
            _q("O espaço em branco num design:", ["É sempre desperdício", "Dá respiro e guia o olhar", "Deve ser eliminado", "Só se usa em livros"], 1),
        ],
    },
    "cores": {
        "org": None, "creator": "nadia", "category": "design",
        "level": "Intermediário", "duration": "35 min",
        "tags": "cor,paletas,identidade visual",
        "title": "Teoria das cores aplicada",
        "description": "Escolher paletas que funcionam no ecrã e no papel.",
        "paragraphs": [
            "As cores transmitem emoções e significados, mas também têm de ser legíveis. Uma paleta típica tem uma cor principal, uma ou duas de apoio e tons neutros para o texto e os fundos.",
            "O círculo cromático ajuda a criar combinações: cores complementares (opostas) dão energia e contraste; cores análogas (vizinhas) criam harmonia. Para a identidade de uma marca, menos cores costuma resultar melhor.",
            "Verifica sempre o contraste entre o texto e o fundo, sobretudo em ecrãs de telemóvel ao sol. Ferramentas de verificação de contraste ajudam a garantir que todos conseguem ler, incluindo pessoas com dificuldades de visão.",
        ],
        "questions": None,
    },
    "ui_mobile": {
        "org": None, "creator": "nadia", "category": "design",
        "level": "Avançado", "duration": "60 min",
        "tags": "ui,ux,mobile",
        "title": "Design de interfaces para telemóveis",
        "description": "Padrões de navegação, áreas de toque e desempenho em redes móveis.",
        "paragraphs": [
            "Desenhar para telemóveis exige pensar no polegar. As acções principais devem ficar ao alcance da mão e os alvos de toque devem ter tamanho suficiente para evitar erros, à volta de 44 a 48 pixels.",
            "A navegação deve ser simples e previsível: uma barra inferior com três a cinco destinos funciona bem na maioria das aplicações. Esconder funções importantes em menus profundos reduz o seu uso.",
            "Em Angola, muitos utilizadores têm dados móveis limitados e redes instáveis. Imagens leves, carregamento progressivo e mensagens claras quando não há ligação fazem parte de um bom design, tanto quanto as cores ou os ícones.",
        ],
        "questions": [
            _q("Qual é um tamanho mínimo recomendado para alvos de toque?", ["Cerca de 10 px", "Cerca de 44 a 48 px", "Cerca de 200 px", "Não importa"], 1),
            _q("Quantos destinos costuma ter uma boa barra de navegação inferior?", ["1", "3 a 5", "8 a 10", "Mais de 12"], 1),
            _q("Porque é importante usar imagens leves?", ["Porque ficam mais bonitas", "Por causa dos dados móveis limitados e das redes instáveis", "Porque os ecrãs são grandes", "Não é importante"], 1),
        ],
    },
    # -------------------------------------------------------------------- UAN
    "requisitos": {
        "org": "uan", "creator": "esperanca", "category": "tecnologia",
        "level": "Intermediário", "duration": "50 min",
        "tags": "engenharia de software,requisitos",
        "title": "Engenharia de Requisitos",
        "description": "Levantar, documentar e validar requisitos de um sistema.",
        "paragraphs": [
            "Os requisitos descrevem o que um sistema deve fazer e em que condições. Distinguem-se requisitos funcionais (por exemplo, \"o estudante consulta as suas notas\") e não funcionais (por exemplo, \"a página carrega em menos de dois segundos\").",
            "O levantamento faz-se com entrevistas, observação do trabalho real, questionários e análise de documentos. Um erro frequente é ouvir só quem paga o sistema e esquecer quem o vai usar todos os dias.",
            "Requisitos bem escritos são claros, verificáveis e sem ambiguidade. Devem ser validados com os interessados antes do desenvolvimento, porque corrigir um requisito errado depois de o sistema estar feito custa muito mais.",
        ],
        "questions": [
            _q("\"A página carrega em menos de dois segundos\" é um requisito:", ["Funcional", "Não funcional", "De negócio", "Opcional"], 1),
            _q("Qual destas é uma técnica de levantamento de requisitos?", ["Compilação", "Entrevista", "Depuração", "Indexação"], 1),
            _q("Porque se validam requisitos antes do desenvolvimento?", ["Porque é mais barato corrigir cedo", "Para atrasar o projecto", "Por obrigação legal", "Não se validam"], 0),
        ],
    },
    "uml": {
        "org": "uan", "creator": "esperanca", "category": "tecnologia",
        "level": "Intermediário", "duration": "55 min",
        "tags": "uml,modelação,engenharia de software",
        "title": "Modelação com UML",
        "description": "Diagramas de casos de uso, de classes e de sequência.",
        "paragraphs": [
            "A UML (Unified Modeling Language) é uma notação para descrever sistemas de software através de diagramas. Não é uma metodologia: é uma linguagem comum para que equipas e clientes falem do mesmo sistema.",
            "O diagrama de casos de uso mostra os actores e o que cada um pode fazer no sistema. O diagrama de classes descreve as entidades, os seus atributos e as relações entre elas, como associações, agregações e heranças.",
            "O diagrama de sequência mostra a troca de mensagens entre objectos ao longo do tempo, para um cenário concreto. É especialmente útil para perceber fluxos complexos, como a inscrição de um estudante numa disciplina com pré-requisitos.",
        ],
        "questions": [
            _q("Que diagrama mostra actores e o que podem fazer?", ["Classes", "Casos de uso", "Sequência", "Implantação"], 1),
            _q("Que diagrama descreve entidades, atributos e relações?", ["Classes", "Actividades", "Sequência", "Estados"], 0),
            _q("A UML é:", ["Uma linguagem de programação", "Uma notação de modelação", "Uma base de dados", "Um sistema operativo"], 1),
        ],
    },
    "testes": {
        "org": "uan", "creator": "esperanca", "category": "tecnologia",
        "level": "Avançado", "duration": "60 min",
        "tags": "testes,qualidade,engenharia de software",
        "title": "Testes de Software",
        "description": "Testes unitários, de integração e de aceitação.",
        "paragraphs": [
            "Testar software é verificar que ele faz o que deve e não faz o que não deve. Os testes unitários verificam pequenas partes do código de forma isolada; os de integração verificam a colaboração entre componentes; os de aceitação confirmam que o sistema serve o utilizador.",
            "A pirâmide de testes sugere muitos testes unitários, rápidos e baratos, menos testes de integração e poucos testes de ponta a ponta, que são lentos e frágeis. Esta proporção mantém a confiança sem tornar a suite impossível de correr.",
            "Testes automatizados correm a cada alteração e apanham regressões cedo. Um bom teste tem um nome que descreve o comportamento esperado, prepara os dados, executa a acção e verifica o resultado.",
        ],
        "questions": [
            _q("Que tipo de teste verifica uma pequena parte do código isoladamente?", ["Aceitação", "Integração", "Unitário", "Carga"], 2),
            _q("Na pirâmide de testes, de que tipo deve haver mais?", ["Ponta a ponta", "Unitários", "Manuais", "Aceitação"], 1),
            _q("Qual é a principal vantagem dos testes automatizados?", ["Substituem o programador", "Apanham regressões cedo", "Tornam o código mais rápido", "Dispensam revisões"], 1),
        ],
    },
    "microeconomia": {
        "org": "uan", "creator": "mateus", "category": "negocios",
        "level": "Iniciante", "duration": "45 min",
        "tags": "economia,oferta,procura",
        "title": "Introdução à Microeconomia: oferta e procura",
        "description": "Como se formam os preços num mercado.",
        "paragraphs": [
            "A microeconomia estuda as decisões de famílias e empresas e a forma como interagem nos mercados. Um dos seus modelos centrais é o da oferta e da procura.",
            "A procura mostra quanto os consumidores querem comprar a cada preço: em regra, quando o preço sobe, a quantidade procurada desce. A oferta mostra quanto os produtores querem vender: quando o preço sobe, a quantidade oferecida tende a aumentar.",
            "O preço de equilíbrio é aquele em que a quantidade procurada iguala a oferecida. Quando a época das chuvas reduz a colheita de um produto agrícola, a oferta diminui e, mantendo-se a procura, o preço sobe nos mercados.",
        ],
        "questions": [
            _q("Em regra, quando o preço sobe, a quantidade procurada:", ["Sobe", "Desce", "Não muda", "Duplica"], 1),
            _q("O que é o preço de equilíbrio?", ["O preço fixado pelo Estado", "O preço em que procura e oferta se igualam", "O preço mais baixo do mercado", "O preço de custo"], 1),
            _q("Uma má colheita, mantendo-se a procura, tende a:", ["Baixar o preço", "Subir o preço", "Não afectar o preço", "Eliminar a procura"], 1),
        ],
    },
    "contabilidade": {
        "org": "uan", "creator": "mateus", "category": "negocios",
        "level": "Intermediário", "duration": "50 min",
        "tags": "contabilidade,balanço,finanças",
        "title": "Contabilidade Geral: o balanço",
        "description": "Activo, passivo e capital próprio, e a equação fundamental da contabilidade.",
        "paragraphs": [
            "O balanço é uma fotografia da situação patrimonial de uma entidade numa data. Do lado do activo estão os bens e direitos: dinheiro, equipamentos, mercadorias e valores a receber de clientes.",
            "Do outro lado estão o passivo, isto é, as obrigações para com terceiros, como empréstimos e dívidas a fornecedores, e o capital próprio, que representa o que pertence aos sócios.",
            "A equação fundamental é Activo = Passivo + Capital Próprio. Qualquer operação mantém este equilíbrio: comprar uma viatura a crédito aumenta o activo e o passivo no mesmo valor.",
        ],
        "questions": None,
    },
    "ergonomia": {
        "org": "uan", "creator": "teresa", "category": "design",
        "level": "Intermediário", "duration": "40 min",
        "tags": "ergonomia,design de produto",
        "title": "Ergonomia e Design de Produto",
        "description": "Adaptar objectos e espaços às pessoas que os usam.",
        "paragraphs": [
            "A ergonomia estuda a relação entre as pessoas e os objectos, ferramentas e espaços que utilizam. O objectivo é garantir conforto, segurança e eficiência, reduzindo o esforço e o risco de lesões.",
            "No design de produto, usam-se dados antropométricos, ou seja, medidas do corpo humano, para dimensionar cadeiras, mesas, pegas e ecrãs. Um produto pensado só para a média da população deixa de fora muitas pessoas.",
            "Testar protótipos com utilizadores reais revela problemas que não se vêem no papel. Uma carteira escolar, por exemplo, deve servir estudantes de alturas diferentes e resistir ao uso diário.",
        ],
        "questions": [
            _q("O que estuda a ergonomia?", ["A relação entre pessoas e objectos ou espaços", "A história da arte", "A produção em série", "O marketing de produtos"], 0),
            _q("O que são dados antropométricos?", ["Preços de materiais", "Medidas do corpo humano", "Estatísticas de vendas", "Normas de cor"], 1),
            _q("Porque se testam protótipos com utilizadores reais?", ["Para revelar problemas que não se vêem no papel", "Para poupar material", "Por tradição", "Não é necessário"], 0),
        ],
    },
    "redes": {
        "org": "uan", "creator": "esperanca", "category": "tecnologia",
        "level": "Intermediário", "duration": "50 min",
        "tags": "redes,tcp/ip,internet",
        "title": "Redes de Computadores: o modelo TCP/IP",
        "description": "As camadas que permitem a comunicação na internet.",
        "paragraphs": [
            "O modelo TCP/IP organiza a comunicação em rede em camadas, cada uma com uma responsabilidade. A camada de ligação trata da transmissão no meio físico, a de rede encaminha os pacotes entre redes, a de transporte garante a entrega e a de aplicação serve os programas.",
            "O protocolo IP atribui endereços e encaminha os pacotes. O TCP estabelece uma ligação fiável, garantindo que os dados chegam completos e pela ordem certa; o UDP é mais simples e rápido, mas não dá essas garantias.",
            "Protocolos de aplicação como HTTP, DNS e SMTP assentam nestas camadas. Quando abres um site, o DNS traduz o nome para um endereço IP e o navegador usa HTTP sobre TCP para pedir a página.",
        ],
        "questions": None,
    },
    # ------------------------------------------------------------------ Kiala
    "folhas_calculo": {
        "org": "kiala", "creator": "domingos", "category": "tecnologia",
        "level": "Iniciante", "duration": "45 min",
        "tags": "informática,folhas de cálculo,excel",
        "title": "Folhas de cálculo: fórmulas básicas",
        "description": "Células, referências e as fórmulas SOMA e MÉDIA.",
        "paragraphs": [
            "Uma folha de cálculo organiza dados em linhas e colunas. Cada célula tem um endereço, como B3, formado pela letra da coluna e pelo número da linha.",
            "As fórmulas começam sempre com o sinal de igual. =SOMA(B2:B10) soma os valores de B2 a B10 e =MÉDIA(B2:B10) calcula a média. Se um valor mudar, o resultado actualiza-se automaticamente.",
            "Neste módulo vais montar uma pauta da turma: colocar as notas de cada disciplina, calcular a média de cada aluno e usar formatação condicional para destacar quem precisa de apoio.",
        ],
        "questions": [
            _q("Com que sinal começam as fórmulas?", ["+", "=", "#", "@"], 1),
            _q("O que faz =SOMA(B2:B10)?", ["Multiplica os valores", "Soma os valores de B2 a B10", "Conta as células vazias", "Ordena os valores"], 1),
            _q("O endereço B3 refere-se a:", ["Coluna 3, linha B", "Coluna B, linha 3", "Folha B, página 3", "Nenhuma célula"], 1),
        ],
    },
    "algoritmos": {
        "org": "kiala", "creator": "domingos", "category": "tecnologia",
        "level": "Iniciante", "duration": "40 min",
        "tags": "algoritmos,lógica,fluxogramas",
        "title": "Introdução aos algoritmos",
        "description": "Descrever a solução de um problema passo a passo.",
        "paragraphs": [
            "Um algoritmo é uma sequência finita de passos bem definidos para resolver um problema. Uma receita de funge ou as instruções para chegar à escola são exemplos de algoritmos do dia-a-dia.",
            "Antes de escrever código, podemos representar algoritmos em pseudocódigo ou em fluxogramas. Os fluxogramas usam símbolos: rectângulos para acções, losangos para decisões e setas para o fluxo.",
            "Um bom algoritmo é correcto, termina sempre e é claro para quem o lê. Vamos praticar com problemas simples, como descobrir o maior de três números ou calcular a média de uma turma.",
        ],
        "questions": [
            _q("O que é um algoritmo?", ["Um tipo de computador", "Uma sequência finita de passos para resolver um problema", "Uma linguagem de programação", "Um vírus"], 1),
            _q("Num fluxograma, que símbolo representa uma decisão?", ["Rectângulo", "Círculo", "Losango", "Seta"], 2),
            _q("Qual é uma característica de um bom algoritmo?", ["Nunca termina", "É ambíguo", "Termina sempre", "Tem muitos passos"], 2),
        ],
    },
    "internet_segura": {
        "org": "kiala", "creator": "domingos", "category": "tecnologia",
        "level": "Iniciante", "duration": "30 min",
        "tags": "segurança,internet,cidadania digital",
        "title": "Internet segura para estudantes",
        "description": "Privacidade, partilha responsável e respeito online.",
        "paragraphs": [
            "Tudo o que publicamos na internet pode ficar disponível durante muito tempo e ser visto por pessoas que não conhecemos. Antes de partilhar uma fotografia ou um comentário, pergunta-te se ficarias à vontade se toda a escola o visse.",
            "Protege os teus dados pessoais: não partilhes a morada, o número de telefone nem a localização em tempo real com desconhecidos. Configura a privacidade das tuas contas para que só amigos vejam as tuas publicações.",
            "O respeito vale também online. Se fores vítima ou testemunha de ciberbullying, guarda as provas, bloqueia o agressor e fala com um professor ou com a família. Pedir ajuda não é fraqueza.",
        ],
        "questions": [
            _q("Que dado NÃO deves partilhar com desconhecidos online?", ["O teu filme preferido", "A tua morada", "A tua cor favorita", "O teu desporto preferido"], 1),
            _q("Se fores vítima de ciberbullying, o que deves fazer?", ["Responder com insultos", "Guardar provas e pedir ajuda", "Apagar a conta e não contar a ninguém", "Ignorar sempre"], 1),
            _q("Para que serve configurar a privacidade das contas?", ["Para ter mais seguidores", "Para controlar quem vê as tuas publicações", "Para gastar menos dados", "Não serve para nada"], 1),
        ],
    },
    "empreendedorismo": {
        "org": "kiala", "creator": "isabel", "category": "negocios",
        "level": "Iniciante", "duration": "40 min",
        "tags": "empreendedorismo,juventude,ideias",
        "title": "Empreendedorismo juvenil",
        "description": "Das ideias aos primeiros clientes, ainda na escola.",
        "paragraphs": [
            "Empreender é identificar uma necessidade e organizar recursos para lhe responder. Muitos negócios começam com um problema do dia-a-dia: explicações para colegas, venda de lanches, reparação de telemóveis ou criação de conteúdos digitais.",
            "Antes de investir, testa a ideia com pouco dinheiro. Pergunta a potenciais clientes se pagariam e quanto. Um protótipo simples ou uma primeira venda ensinam mais do que muitas horas de planeamento.",
            "O empreendedor também aprende com os erros. Regista o que correu bem e mal, ouve as críticas e ajusta. Persistência, responsabilidade e honestidade com os clientes são a base de qualquer negócio duradouro.",
        ],
        "questions": [
            _q("O que é empreender?", ["Gastar dinheiro sem plano", "Responder a uma necessidade organizando recursos", "Trabalhar só para o Estado", "Copiar ideias de outros"], 1),
            _q("Qual é a melhor forma de testar uma ideia de negócio?", ["Investir todas as poupanças", "Perguntar a potenciais clientes e fazer uma primeira venda", "Esperar ter a ideia perfeita", "Não falar com ninguém"], 1),
            _q("Que atitude ajuda a construir um negócio duradouro?", ["Esconder os erros", "Honestidade com os clientes", "Ignorar críticas", "Mudar de ideia todos os dias"], 1),
        ],
    },
    "educacao_financeira": {
        "org": "kiala", "creator": "isabel", "category": "negocios",
        "level": "Iniciante", "duration": "30 min",
        "tags": "finanças pessoais,poupança,orçamento",
        "title": "Educação financeira: poupar e orçamentar",
        "description": "Gerir a mesada, poupar com objectivos e evitar dívidas.",
        "paragraphs": [
            "Um orçamento pessoal é uma lista do dinheiro que recebes e do que gastas num mês. Escrever os gastos, mesmo os pequenos, mostra para onde vai o dinheiro e onde é possível poupar.",
            "Poupar é mais fácil com um objectivo concreto: um telemóvel novo, um curso ou uma viagem. Separa a poupança logo que recebes o dinheiro, em vez de esperar pelo que sobra no fim do mês.",
            "Distingue necessidades de desejos. Antes de comprar por impulso, espera um dia e pergunta-te se ainda queres aquilo. Pedir dinheiro emprestado para desejos é o caminho mais rápido para as dívidas.",
        ],
        "questions": None,
    },
    "comunicacao_visual": {
        "org": "kiala", "creator": "isabel", "category": "design",
        "level": "Iniciante", "duration": "35 min",
        "tags": "desenho,comunicação visual,cartazes",
        "title": "Desenho e comunicação visual",
        "description": "Criar cartazes que comunicam uma mensagem de forma clara.",
        "paragraphs": [
            "A comunicação visual transmite mensagens através de imagens, cores e texto. Um cartaz eficaz é compreendido em poucos segundos, mesmo por quem passa apressado.",
            "Começa por definir a mensagem principal e o público. Depois, faz esboços rápidos à mão antes de passar ao computador. Os esboços permitem testar várias composições sem perder tempo.",
            "Usa no máximo dois tipos de letra e uma paleta reduzida. A informação mais importante deve ser a maior, e os detalhes, como datas e contactos, devem estar agrupados e legíveis à distância.",
        ],
        "questions": [
            _q("Um cartaz eficaz deve ser compreendido em:", ["Poucos segundos", "Vários minutos", "Uma hora", "Um dia"], 0),
            _q("Porque se fazem esboços à mão antes do computador?", ["Para testar composições rapidamente", "Porque é obrigatório", "Para gastar papel", "Não se fazem"], 0),
            _q("Quantos tipos de letra se recomendam num cartaz?", ["No máximo dois", "Pelo menos cinco", "Um por palavra", "Não importa"], 0),
        ],
    },
}

# Trilhas: itens são ("conteudo"|"quiz"|"enquete", chave). Para "quiz", a chave
# é a do conteúdo a que o quiz pertence.
TRILHAS = [
    {
        "key": "trilha_programacao", "org": None, "creator": "nadia",
        "title": "Primeiros passos em programação",
        "headline": "Do primeiro print() aos ciclos, com exercícios práticos.",
        "subject": "Programação", "year": "", "semester": "", "is_sequential": True,
        "items": [
            ("conteudo", "py_intro"), ("quiz", "py_intro"),
            ("conteudo", "logica"), ("quiz", "logica"),
            ("conteudo", "ciclos"), ("quiz", "ciclos"),
        ],
    },
    {
        "key": "trilha_negocio", "org": None, "creator": "paulo",
        "title": "Empreender em Angola",
        "headline": "Da ideia ao primeiro cliente, ao teu ritmo.",
        "subject": "Empreendedorismo", "year": "", "semester": "", "is_sequential": False,
        "items": [
            ("conteudo", "plano_negocio"), ("quiz", "plano_negocio"),
            ("conteudo", "abrir_empresa"), ("conteudo", "financas_pme"),
            ("quiz", "financas_pme"), ("conteudo", "marketing"),
        ],
    },
    {
        "key": "trilha_eng_software", "org": "uan", "creator": "esperanca",
        "title": "Fundamentos de Engenharia de Software",
        "headline": "Requisitos, modelação e testes num só percurso.",
        "subject": "Engenharia de Software", "year": "2.º ano", "semester": "1.º semestre",
        "is_sequential": True,
        "items": [
            ("conteudo", "requisitos"), ("quiz", "requisitos"),
            ("conteudo", "uml"), ("quiz", "uml"),
            ("conteudo", "testes"), ("quiz", "testes"),
            ("enquete", "enq_uan_horario"),
        ],
    },
    {
        "key": "trilha_economia", "org": "uan", "creator": "mateus",
        "title": "Introdução à Economia e Gestão",
        "headline": "Mercados e contabilidade para o 1.º ano.",
        "subject": "Economia", "year": "1.º ano", "semester": "1.º semestre",
        "is_sequential": False,
        "items": [
            ("conteudo", "microeconomia"), ("quiz", "microeconomia"),
            ("conteudo", "contabilidade"),
        ],
    },
    {
        "key": "trilha_informatica_kiala", "org": "kiala", "creator": "domingos",
        "title": "Informática no ensino médio",
        "headline": "Algoritmos, folhas de cálculo e segurança online.",
        "subject": "Informática", "year": "10.ª classe", "semester": "",
        "is_sequential": True,
        "items": [
            ("conteudo", "algoritmos"), ("quiz", "algoritmos"),
            ("conteudo", "folhas_calculo"), ("quiz", "folhas_calculo"),
            ("conteudo", "internet_segura"), ("quiz", "internet_segura"),
        ],
    },
]

# Enquetes (só nas escolas: no marketplace não há difusão de notificações).
ENQUETES = [
    {
        "key": "enq_uan_horario", "org": "uan", "creator": "esperanca",
        "kind": "escolha",
        "question": "Que formato preferes para as aulas práticas de Engenharia de Software?",
        "decision": "Definir o formato das aulas práticas do próximo semestre.",
        "options": ["Presencial no laboratório", "Online", "Misto"],
        "faculty": "Engenharia", "subject": "Engenharia de Software",
        "trigger": "fim-modulo", "sample_target": 50, "segment_size": 120,
        "close": False,
    },
    {
        "key": "enq_uan_dificuldade", "org": "uan", "creator": "mateus",
        "kind": "escala",
        "question": "De 1 a 5, quão difícil foi o módulo de Microeconomia?",
        "decision": "Ajustar o ritmo e os exercícios do módulo.",
        "options": ["1", "2", "3", "4", "5"],
        "faculty": "Economia", "subject": "Microeconomia",
        "trigger": "fim-leitura", "sample_target": 40, "segment_size": 90,
        "close": True,
    },
    {
        "key": "enq_kiala_feira", "org": "kiala", "creator": "isabel",
        "kind": "binaria",
        "question": "Queres participar na feira de empreendedorismo do colégio?",
        "decision": "Decidir se a feira avança este trimestre.",
        "options": ["Sim", "Não"],
        "faculty": "", "subject": "Empreendedorismo",
        "trigger": "fim-modulo", "sample_target": 30, "segment_size": 60,
        "close": False,
    },
]
