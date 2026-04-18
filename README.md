# Hunter IA

Produto full-stack para busca de vagas, gestão de currículos, candidaturas, matching e cobrança, com backend Django/DRF/JWT e frontend React/Vite.

## Stack atual

- Backend: Django, Django REST Framework, JWT, WhiteNoise
- Frontend: React 18, React Router, Vite
- Banco local: SQLite
- Billing: Stripe

## Estrutura

- `project/`: configuração Django, health/readiness, serving da SPA
- `hunter/`: domínio, APIs, serviços, scraping e billing
- `frontend/`: app React usada no dia a dia de desenvolvimento
- `frontend_build/`: artefato gerado no build de produção do frontend

## Desenvolvimento local

### Backend

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py runserver
```

O backend sobe em `http://127.0.0.1:8000`.

### Frontend

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

O frontend sobe em `http://127.0.0.1:3000` e faz proxy para o Django local.

## Build de produção

O fluxo recomendado desta sprint é manter deploy same-origin: Django servindo API, SPA buildada e assets estáticos.

```bash
cd frontend
npm install
npm run build
cd ..
python manage.py collectstatic --noinput
python manage.py check --deploy
```

O `vite build` gera `frontend_build/` com:

- `frontend_build/index.html`: shell da SPA
- `frontend_build/assets/*`: JS/CSS versionados para produção

O Django passa a:

- servir `/` e rotas da SPA como `/dashboard`, `/jobs`, `/billing/success`
- continuar atendendo `/api/token/`, `/hunter/...`, `/admin/`, `/health/` e `/ready/`
- servir assets versionados via `/static/`

## Variáveis de ambiente importantes

Use `.env.example` como base no backend e `frontend/.env.example` no frontend.

### Backend

- `DJANGO_DEBUG`: desligue em produção
- `DJANGO_SECRET_KEY`: obrigatório em produção
- `ALLOWED_HOSTS`: hosts reais do deploy
- `CSRF_TRUSTED_ORIGINS`: origens HTTPS reais do app
- `APP_BASE_URL`: URL pública do backend/Django
- `FRONTEND_PUBLIC_URL`: URL pública usada pelo Stripe para success/cancel/return
- `DJANGO_SERVE_FRONTEND`: mantém o Django servindo a SPA buildada
- `DJANGO_SERVE_MEDIA_FILES`: útil em deploy simples com uma única app; em infra separada, delegue media ao proxy/storage
- `DATABASE_URL`: aceita banco externo sem mudar a arquitetura do projeto
- `CORS_ALLOWED_ORIGINS`: só preencha se frontend e backend ficarem em origens diferentes
- `USE_X_FORWARDED_PROTO` e `USE_X_FORWARDED_HOST`: ative atrás de proxy/load balancer
- `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `DJANGO_SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`: habilite em produção HTTPS

### Frontend

- `VITE_API_BASE_URL`: deixe vazio para same-origin; defina a URL da API se o frontend rodar separado
- `VITE_ASSET_BASE`: padrão `/static/`
- `VITE_BUILD_OUT_DIR`: padrão `../frontend_build`
- `VITE_DEV_API_PROXY_TARGET`: alvo do proxy local do Vite

### Stripe

- `STRIPE_SECRET_KEY`
- `STRIPE_PUBLISHABLE_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_PRO_TRIAL_15`
- `STRIPE_PRICE_PRO_TRIAL_30`
- `STRIPE_PRICE_PRO_TRIAL_90`

Se `STRIPE_SUCCESS_URL`, `STRIPE_CANCEL_URL` e `STRIPE_PORTAL_RETURN_URL` não forem definidos, o backend monta defaults a partir de `FRONTEND_PUBLIC_URL`.

## Health e readiness

- `GET /health/`: confirma que o Django e o banco estão respondendo
- `GET /ready/`: confirma banco e, quando `DJANGO_SERVE_FRONTEND=True`, também a presença do build do frontend

Isso é útil para deploys simples com uma checagem de liveness/readiness sem adicionar infraestrutura extra.

## Rotas SPA em produção

Com o frontend buildado, refresh direto em rotas como:

- `/dashboard`
- `/resumes`
- `/jobs`
- `/applications`
- `/billing`
- `/billing/success`
- `/billing/cancel`

continua funcionando porque o Django devolve o `index.html` da SPA para rotas não-API.

## Static e media

- Assets do React são gerados no build e entram no pipeline de `collectstatic`
- `ResumeSerializer.file_url` continua sendo absoluto e estável
- Para deploy simples, `DJANGO_SERVE_MEDIA_FILES=True` permite servir uploads pelo próprio Django

## Deploy sugerido

Ordem mínima para um deploy estável:

1. Configurar variáveis do `.env`
2. Instalar dependências Python e Node
3. Rodar `npm run build` dentro de `frontend/`
4. Rodar `python manage.py collectstatic --noinput`
5. Rodar `python manage.py migrate`
6. Publicar o serviço WSGI com `gunicorn project.wsgi:application`

O `Procfile` já está preparado para esse último passo.
