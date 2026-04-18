# Hunter IA

Hunter IA é uma plataforma para ajudar pessoas em busca de trabalho a transformar currículo, vagas e candidaturas em uma jornada mais clara, organizada e orientada a decisão.

O produto combina análise de currículo, leitura de senioridade, matching com vagas, organização de candidaturas e acesso premium por período definido. A proposta é reduzir a incerteza de quem está procurando uma oportunidade: o usuário entende melhor onde está, quais vagas fazem sentido agora e qual próximo passo pode aumentar suas chances.

## Visão geral

O Hunter IA nasceu para apoiar quem precisa sair do modo improviso na busca por emprego. Em vez de espalhar currículo, links de vagas e status de candidatura em ferramentas desconectadas, o produto centraliza o workspace da busca e entrega sinais práticos para priorizar melhor.

Hoje o projeto já conta com:

- autenticação real com cadastro, login e renovação de sessão via JWT;
- dashboard operacional para acompanhar prioridades, currículo ativo e próximos passos;
- upload, validação e gestão de versões de currículo em PDF ou DOCX;
- análise de currículo, leitura de senioridade e diagnóstico premium;
- comparação entre versões de currículo;
- busca, coleta, salvamento e organização de vagas;
- matching entre currículo e vaga com indicação de aderência e decisão sugerida;
- acompanhamento de candidaturas;
- billing com Stripe e planos premium de 15, 30 e 90 dias;
- health/readiness para operação e deploy;
- SPA React servida pelo Django em deploy same-origin.

## Problema que resolve

Buscar emprego costuma virar um processo fragmentado: o currículo fica sem critério claro, as vagas se acumulam sem prioridade, candidaturas se perdem e o usuário recebe pouca orientação objetiva sobre o que ajustar.

O Hunter IA ataca esse problema em quatro frentes:

- clareza: mostra se o currículo tem sinais suficientes, qual senioridade comunica e onde precisa melhorar;
- foco: ajuda a comparar vagas e decidir onde vale investir energia;
- organização: reúne currículos, vagas salvas e candidaturas no mesmo fluxo;
- confiança: evita expor estados técnicos crus e traduz bloqueios, validações e próximos passos em linguagem útil.

## Principais funcionalidades

### Currículos

- Envio de currículos em PDF ou DOCX.
- Validação de arquivo, tipo, estrutura, texto extraível e sinais mínimos de currículo.
- Versionamento para testar variações por cargo, senioridade ou estratégia.
- Análise do currículo com leitura de estrutura, clareza e aderência.
- Leitura de senioridade para apoiar posicionamento.
- Comparação entre versões e diagnóstico premium quando o acesso está ativo.

### Vagas e candidaturas

- Busca e coleta de vagas a partir dos provedores suportados pelo projeto.
- Normalização, persistência e deduplicação de oportunidades.
- Salvamento de vagas para revisão posterior.
- Registro de candidaturas e acompanhamento do funil pessoal.
- Visão de status do workspace com vagas salvas, candidaturas e matches gerados.

### Matching e decisão

- Cálculo de aderência entre currículo e vaga.
- Classificação prática da decisão: aplicar agora, aplicar após ajustes ou fortalecer currículo antes.
- Priorização para transformar uma lista grande de vagas em um plano de ação.

### Acesso premium

- Planos de acesso premium por 15, 30 ou 90 dias.
- Checkout e webhooks via Stripe.
- Liberação de recursos premium como diagnósticos mais profundos e comparação de versões.
- Fluxo de sucesso/cancelamento integrado à SPA.

## Stack utilizada

- Backend: Django, Django REST Framework, JWT e WhiteNoise.
- Frontend: React 18, React Router e Vite.
- Banco local: SQLite.
- Billing: Stripe.
- Deploy: Django servindo API, SPA buildada e arquivos estáticos em modelo same-origin.

## Estrutura do projeto

- `project/`: configuração Django, autenticação, health/readiness e serving da SPA.
- `hunter/`: domínio principal, APIs, serviços, scraping, currículos, matching, candidaturas e billing.
- `frontend/`: aplicação React usada no desenvolvimento do produto.
- `frontend_build/`: artefato gerado pelo build de produção do frontend.
- `docs/sprints/`: contexto de produto, pipeline e critérios das sprints.

## Fluxo principal do produto

1. O usuário cria uma conta ou entra com login existente.
2. Envia um currículo em PDF ou DOCX.
3. O sistema valida o arquivo e extrai texto quando a estrutura é confiável.
4. O usuário consulta análise, senioridade e próximos passos do currículo.
5. Busca ou revisa vagas dentro do workspace.
6. Salva oportunidades relevantes e gera matches com o currículo.
7. Decide onde aplicar agora, onde ajustar antes e onde não gastar energia.
8. Registra candidaturas e acompanha a evolução da busca.
9. Quando fizer sentido, ativa um período premium para diagnósticos e comparações mais profundas.

## Como rodar localmente

Use `.env.example` como base no backend e `frontend/.env.example` no frontend.

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

O fluxo recomendado é manter deploy same-origin: Django serve a API, a SPA buildada e os assets estáticos.

```bash
cd frontend
npm install
npm run build
cd ..
python manage.py collectstatic --noinput
python manage.py check --deploy
```

O `vite build` gera `frontend_build/` com:

- `frontend_build/index.html`: shell da SPA;
- `frontend_build/assets/*`: JS/CSS versionados para produção.

Com esse modelo, o Django:

- serve `/` e rotas da SPA como `/dashboard`, `/jobs`, `/billing/success` e `/billing/cancel`;
- continua atendendo `/api/token/`, `/hunter/...`, `/admin/`, `/health/` e `/ready/`;
- serve assets versionados via `/static/`.

## Variáveis de ambiente importantes

### Backend

- `DJANGO_DEBUG`: desligue em produção.
- `DJANGO_SECRET_KEY`: obrigatório em produção.
- `ALLOWED_HOSTS`: hosts reais do deploy.
- `CSRF_TRUSTED_ORIGINS`: origens HTTPS reais do app.
- `APP_BASE_URL`: URL pública do backend/Django.
- `FRONTEND_PUBLIC_URL`: URL pública usada pelo Stripe para success/cancel/return.
- `DJANGO_SERVE_FRONTEND`: mantém o Django servindo a SPA buildada.
- `DJANGO_SERVE_MEDIA_FILES`: útil em deploy simples com uma única app; em infra separada, delegue media ao proxy/storage.
- `DATABASE_URL`: permite usar banco externo sem mudar a arquitetura do projeto.
- `CORS_ALLOWED_ORIGINS`: só preencha se frontend e backend ficarem em origens diferentes.
- `USE_X_FORWARDED_PROTO` e `USE_X_FORWARDED_HOST`: ative atrás de proxy/load balancer.
- `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `DJANGO_SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`: habilite em produção HTTPS.

### Frontend

- `VITE_API_BASE_URL`: deixe vazio para same-origin; defina a URL da API se o frontend rodar separado.
- `VITE_ASSET_BASE`: padrão `/static/`.
- `VITE_BUILD_OUT_DIR`: padrão `../frontend_build`.
- `VITE_DEV_API_PROXY_TARGET`: alvo do proxy local do Vite.

### Stripe

- `STRIPE_SECRET_KEY`
- `STRIPE_PUBLISHABLE_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_PRO_TRIAL_15`
- `STRIPE_PRICE_PRO_TRIAL_30`
- `STRIPE_PRICE_PRO_TRIAL_90`

Se `STRIPE_SUCCESS_URL`, `STRIPE_CANCEL_URL` e `STRIPE_PORTAL_RETURN_URL` não forem definidos, o backend monta defaults a partir de `FRONTEND_PUBLIC_URL`.

## Health, readiness e rotas

- `GET /health/`: confirma que o Django e o banco estão respondendo.
- `GET /ready/`: confirma banco e, quando `DJANGO_SERVE_FRONTEND=True`, também a presença do build do frontend.

Com o frontend buildado, refresh direto em rotas como `/dashboard`, `/resumes`, `/jobs`, `/applications`, `/billing`, `/billing/success` e `/billing/cancel` continua funcionando porque o Django devolve o `index.html` da SPA para rotas não-API.

## Static e media

- Assets do React são gerados no build e entram no pipeline de `collectstatic`.
- `ResumeSerializer.file_url` continua sendo absoluto e estável.
- Para deploy simples, `DJANGO_SERVE_MEDIA_FILES=True` permite servir uploads pelo próprio Django.

## Deploy sugerido

Ordem mínima para um deploy estável:

1. Configurar variáveis do `.env`.
2. Instalar dependências Python e Node.
3. Rodar `npm run build` dentro de `frontend/`.
4. Rodar `python manage.py collectstatic --noinput`.
5. Rodar `python manage.py migrate`.
6. Publicar o serviço WSGI com `gunicorn project.wsgi:application`.

O `Procfile` já está preparado para esse último passo.

## Status atual

O Hunter IA está em preparação para beta pública. O foco atual do projeto é deixar o produto mais estável, claro e confiável para usuários reais, preservando segurança operacional em upload de currículos, autenticação, billing, scraping e deploy.

## Roadmap

Próximas frentes previstas:

- ajustes finais de release readiness e checklist de beta pública;
- refinamento de onboarding e responsividade;
- smoke tests e QA manual dos fluxos principais;
- evolução futura da admissão semântica de currículos e de casos ambíguos;
- possível camada LLM para classificações mais avançadas, sem substituir as validações determinísticas já existentes.
