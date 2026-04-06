# 🏹 Hunter-IA: Automated Lead & Job Tracker

O **Hunter-IA** é uma API robusta desenvolvida para desenvolvedores e profissionais que desejam organizar sua busca por oportunidades de forma inteligente. O sistema permite o rastreio de vagas (Jobs), gerenciamento de contatos estratégicos (Leads) e organização por tags, tudo protegido por autenticação moderna.

---

## 🚀 Tecnologias Utilizadas

* **Python 3.x**
* **Django & Django REST Framework** (Core do projeto)
* **Simple JWT** (Autenticação segura via Tokens)
* **Django Filter** (Busca e filtragem avançada)
* **SQLite** (Banco de dados leve e eficiente)
* **Python-environ** (Segurança de variáveis de ambiente)

---

## 🛠️ Como Configurar o Projeto

1. **Clone o repositório:**
   ```bash
   git clone [https://github.com/erikvianadev/Hunter-IA-Automated-Lead-Job-Tracker.git](https://github.com/erikvianadev/Hunter-IA-Automated-Lead-Job-Tracker.git)
   cd Hunter-IA-Automated-Lead-Job-Tracker
Crie e ative seu ambiente virtual:

Bash
python -m venv venv
# No Windows:
.\venv\Scripts\activate
Instale as dependências:

Bash
pip install -r requirements.txt
Configure as variáveis de ambiente:
Crie um arquivo .env na raiz do projeto e adicione:

Snippet de código
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=sua_chave_secreta
ALLOWED_HOSTS=127.0.0.1,localhost
Rode as migrações e inicie o servidor:

Bash
python manage.py migrate
python manage.py runserver
🔑 Autenticação
A API utiliza JWT (JSON Web Token). Para acessar os endpoints:

Obtenha o token em /api/token/ enviando seu usuário e senha.

Use o access_token no Header das requisições:
Authorization: Bearer <seu_token>

📌 Endpoints Principais
POST /api/token/: Geração de Token.

GET /hunter/api/jobs/: Listagem de vagas (Requer autenticação).

POST /hunter/api/leads/: Cadastro de novos contatos/recrutadores.

GET /hunter/api/tags/: Gerenciamento de tecnologias.

Desenvolvido por Erik Viana 🚀


---

### 💡 Como salvar e subir:
1.  Crie o arquivo chamado `README.md` na pasta principal do projeto.
2.  Cole o texto acima.
3.  No terminal:
    ```bash
    git add README.md
    git commit -m "docs: add comprehensive README"
    git push origin main
    ```

**Dica:** Depois de dar o push, abra seu GitHub no navegador. Você vai ver como a cara do projeto mudou completamente! 

**Tudo pronto para o commit final do README?** Se quiser mudar algum detalhe na descrição, é só falar! 🐍🏹🔥