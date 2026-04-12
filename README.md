# 🏹 Hunter-IA | Automated Lead & Job Tracker

**Link do Projeto:** [Acessar API no Render](https://hunter-ia-automated-lead-job-tracker.onrender.com/hunter/api/jobs/)

[![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-%23092e20.svg?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DjangoREST](https://img.shields.io/badge/DJANGO-REST-ff1709?style=for-the-badge&logo=django&logoColor=white&color=ff1709)](https://www.django-rest-framework.org/)
[![JWT](https://img.shields.io/badge/JWT-black?style=for-the-badge&logo=JSON%20web%20tokens)](https://jwt.io/)

O **Hunter-IA** é uma solução de backend robusta projetada para centralizar e inteligenciar a busca por oportunidades no mercado de tecnologia. Com uma arquitetura focada em segurança e performance, o sistema permite o gerenciamento completo de vagas, contatos estratégicos (Leads) e tecnologias (Tags).

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia |
| :--- | :--- |
| **Linguagem** | Python 3.x |
| **Framework Web** | Django 5.x |
| **API Engine** | Django REST Framework |
| **Segurança** | Simple JWT (OAuth2 Flow) |
| **Banco de Dados** | SQLite (Desenvolvimento) |
| **Configuração** | Python-environ (12-Factor App) |

---
## 🌍 Deploy
O projeto está hospedado e rodando no Render:
👉 [https://hunter-ia-automated-lead-job-tracker.onrender.com/hunter/api/jobs/](https://hunter-ia-automated-lead-job-tracker.onrender.com/hunter/api/jobs/)
---

## 🚀 Como Configurar o Projeto

### 1. Preparando o Ambiente
```bash
# Clone o repositório
git clone [https://github.com/erikvianadev/Hunter-IA-Automated-Lead-Job-Tracker.git](https://github.com/erikvianadev/Hunter-IA-Automated-Lead-Job-Tracker.git)
cd Hunter-IA-Automated-Lead-Job-Tracker

# Crie e ative o ambiente virtual
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
2. Instalação e Variáveis
Bash
# Instale as dependências
pip install -r requirements.txt

# Crie o arquivo de configuração
touch .env
Nota: Adicione as seguintes chaves no seu .env:
DJANGO_DEBUG=True, DJANGO_SECRET_KEY=sua_chave, ALLOWED_HOSTS=127.0.0.1,localhost

3. Execução
Bash
python manage.py migrate
python manage.py runserver

## Frontend React MVP

O repositório agora inclui um frontend React incremental em [frontend](C:\Users\Pichau\Desktop\PROJETO_IA_HUNTER\frontend) que consome a API existente sem alterar os contratos.

### Rodando o frontend

```bash
cd frontend
npm install
npm run dev
```

O Vite sobe em `http://localhost:3000` e faz proxy local para o Django em `http://127.0.0.1:8000`.

### Fluxos entregues no MVP

- login com JWT via `/api/token/`
- dashboard consolidado via `/hunter/api/resumes/dashboard/`
- gestão de currículos com upload, ativação, análise, senioridade, compare e report
- vagas com filtro, scrape, save, apply e match
- pipeline de candidaturas com atualização de status e notas
- billing com visão de planos, assinatura atual, subscribe e cancel
🔑 Guia de Autenticação
A API utiliza o fluxo de Bearer Token. Siga os passos abaixo para testar no Insomnia/Postman:

Obter Acesso: Realize um POST em /api/token/ com username e password.

Autorizar: Copie o access_token retornado.

Header: Em suas requisições, adicione o campo:
Authorization: Bearer <seu_token_aqui>

📌 Endpoints Estratégicos
🔐 Autenticação
POST /api/token/ - Gera tokens de acesso e refresh.

POST /api/token/refresh/ - Renova o token de acesso.

🏹 Hunter Core
GET /hunter/api/jobs/ - Lista vagas com suporte a filtros e paginação.

POST /hunter/api/leads/ - Registra contatos estratégicos (Recrutadores/Managers).

GET /hunter/api/tags/ - Gerencia stack de tecnologias associadas.

👤 Autor
Desenvolvido com ☕ e 🐍 por Erik Viana.
