import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { SectionCard } from "../components/SectionCard";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { formatEvidenceSignal, getJobsOverviewCardsPresentation, getMatchDecisionPresentation, getMatchNoticeTone } from "../lib/presentation";
import { formatRelativeDate, formatShortDate, getErrorMessage, titleize } from "../lib/utils";

const JOBS_PAGE_SIZE = 12;
const SCRAPE_SOURCES = ["Ashby", "Greenhouse", "Lever", "Remotive"];
const APPLICATION_STATUSES = ["saved", "applied", "interview", "rejected", "offer", "archived"];
const SEARCH_PROGRESS_MESSAGES = [
  "Consultando fontes confiáveis de vagas...",
  "Lendo oportunidades relevantes para o seu perfil...",
  "Organizando as melhores vagas para você...",
  "Refinando e removendo duplicatas...",
  "Quase pronto — salvando as oportunidades selecionadas...",
];
const STATUS_OPTIONS = [{ value: "all", label: "Todas as vagas" }, { value: "saved", label: "Salvas" }, { value: "applied", label: "Aplicadas" }];
const SORT_OPTIONS = [
  { value: "-created_at", label: "Salvas mais recentes" },
  { value: "-date_posted", label: "Publicadas mais recentemente" },
  { value: "company_name", label: "Empresa A-Z" },
  { value: "title", label: "Cargo A-Z" }
];

function ScrapeProgressBar({ loading }) {
  const [msgIndex, setMsgIndex] = useState(0);

  useEffect(() => {
    if (!loading) { setMsgIndex(0); return; }
    const interval = setInterval(() => setMsgIndex((prev) => (prev + 1) % SEARCH_PROGRESS_MESSAGES.length), 2200);
    return () => clearInterval(interval);
  }, [loading]);

  if (!loading) return null;
  return (
    <div className="loading-inline scrape-progress">
      <p className="scrape-progress__message">{SEARCH_PROGRESS_MESSAGES[msgIndex]}</p>
      <div className="scrape-progress__sources">
        {SCRAPE_SOURCES.map((source) => (
          <span key={source} className="status-badge tone-muted scrape-source-chip">
            <span className="scrape-pulse-dot" />
            {source}
          </span>
        ))}
      </div>
    </div>
  );
}

function getProviderSummary(payload) {
  if (!payload) return [];
  return [
    { label: "Fontes consultadas", value: payload.provider_status_summary?.total ?? payload.providers_run?.length ?? 0 },
    { label: "Vagas encontradas", value: payload.raw_scraped ?? 0 },
    { label: "Únicas selecionadas", value: payload.scraped ?? 0 },
    { label: "No workspace", value: payload.saved ?? 0 }
  ];
}

function getProviderBreakdown(payload) {
  if (Array.isArray(payload?.provider_health) && payload.provider_health.length) {
    return payload.provider_health
      .map((item) => ({
        provider: titleize(item.provider),
        jobsFound: item.jobs_found ?? 0,
        tone: item.tone ?? "muted",
        statusLabel: item.label ?? "Status atualizado"
      }))
      .sort((left, right) => right.jobsFound - left.jobsFound || left.provider.localeCompare(right.provider));
  }

  if (!payload?.provider_job_counts) return [];
  return Object.entries(payload.provider_job_counts)
    .map(([provider, jobsFound]) => {
      const name = provider.toLowerCase();
      const blocked = payload.providers_blocked?.includes(name);
      const failed = payload.providers_failed?.includes(name);
      return {
        provider: titleize(provider),
        jobsFound,
        tone: blocked ? "blocked" : failed ? "warning" : "good",
        statusLabel: blocked ? "Fonte bloqueada" : failed ? "Fonte instável" : "Disponível"
      };
    })
    .sort((left, right) => right.jobsFound - left.jobsFound || left.provider.localeCompare(right.provider));
}

function getScrapeFeedbackMessage(payload) {
  if (!payload) return "";
  const saved = payload.saved ?? 0;
  const rawScraped = payload.raw_scraped ?? 0;
  if (!rawScraped && !saved) return "Não encontramos vagas para este perfil agora. Experimente um cargo mais amplo ou remova a restrição de local.";
  if (saved > 0) return `${saved} ${saved === 1 ? "nova oportunidade adicionada" : "novas oportunidades adicionadas"} ao workspace.`;
  return "Busca concluída. O workspace já tinha estas oportunidades.";
}

function getSearchStatusLabel(payload) {
  if (!payload) return "";
  const status = payload.status;
  if (status === "partial_success" || status === "partial") return "Busca otimizada";
  if (status === "success") return "Concluída";
  if (status === "budget_exhausted") return "Resultado rápido";
  if (status === "error" || status === "failed") return "Indisponível";
  return payload.status_label ?? "Concluída";
}

function ScrapeResultHero({ payload }) {
  if (!payload) return null;
  const saved = payload.saved ?? 0;
  const rawScraped = payload.raw_scraped ?? 0;
  if (rawScraped === 0) return null;
  if (saved === 0) {
    return <p className="muted-copy">Workspace já estava atualizado com estas oportunidades. Sem novas vagas adicionadas nesta busca.</p>;
  }
  return (
    <div className="scrape-result-hero">
      <span className="scrape-result-hero__count">{saved}</span>
      <div>
        <strong>{saved === 1 ? "nova oportunidade reunida para você" : "novas oportunidades reunidas para você"}</strong>
        <p>Fontes mais úteis consultadas primeiro. Workspace atualizado.</p>
      </div>
    </div>
  );
}

function getScoreTone(score) {
  if (score >= 80) return "good";
  if (score >= 60) return "warning";
  return "blocked";
}

function getDescriptionPreview(description) {
  if (!description) return "Nenhuma descrição detalhada foi capturada para esta vaga ainda.";
  return description.length <= 190 ? description : `${description.slice(0, 190).trim()}...`;
}

function buildJobsOverviewCardsFallback({ jobsCount = 0, metaLoading = false, workspaceStats = {} } = {}) {
  const safeStats = workspaceStats ?? {};
  const savedCount = Number.isFinite(safeStats.savedCount) ? safeStats.savedCount : 0;
  const applicationCount = Number.isFinite(safeStats.applicationCount) ? safeStats.applicationCount : 0;
  const matchCount = Number.isFinite(safeStats.matchCount) ? safeStats.matchCount : 0;

  return [
    {
      label: "Vagas no workspace",
      value: Number.isFinite(jobsCount) ? jobsCount : 0,
      helper: jobsCount ? "Dentro dos filtros atuais" : "Busque vagas para montar sua shortlist inicial."
    },
    {
      label: "Vagas salvas",
      value: metaLoading ? "..." : savedCount,
      helper: savedCount ? "Prontas para revisão" : "Salve oportunidades para comparar com calma."
    },
    {
      label: "Candidaturas",
      value: metaLoading ? "..." : applicationCount,
      helper: applicationCount ? "Já em andamento" : "Marque vagas como aplicadas para acompanhar as etapas."
    },
    {
      label: "Matches gerados",
      value: metaLoading ? "..." : matchCount,
      helper: matchCount ? "Com visibilidade de aderência" : "Atualize a aderência para descobrir onde vale focar."
    }
  ];
}

function ExpandableDescription({ text, collapsedChars = 560 }) {
  const [expanded, setExpanded] = useState(false);
  const content = (text || "").trim();

  if (!content) {
    return <p className="job-description">Nenhuma descrição detalhada foi capturada para esta vaga ainda.</p>;
  }

  const canCollapse = content.length > collapsedChars;
  const visibleText = expanded || !canCollapse ? content : `${content.slice(0, collapsedChars).trim()}...`;

  return (
    <div className="job-description-block">
      <p className={expanded ? "job-description is-expanded" : "job-description"}>{visibleText}</p>
      {canCollapse ? (
        <button className="button button--ghost button--inline" type="button" onClick={() => setExpanded((value) => !value)}>
          {expanded ? "Ler menos" : "Ler mais"}
        </button>
      ) : null}
    </div>
  );
}

function getJobRecencyLabel(job) {
  const value = job.date_posted || job.created_at;
  return `${job.date_posted ? "Publicada em" : "Adicionada em"} ${formatShortDate(value)} | ${formatRelativeDate(value)}`;
}

function getJobWorkflowNextAction(job) {
  if (job.application_status) {
    return {
      title: `Acompanhar candidatura ${titleize(job.application_status).toLowerCase()}`,
      detail: "Esta vaga já está no pipeline. Use Candidaturas para atualizar etapa, notas e contexto.",
      tone: "medium"
    };
  }

  if (job.is_saved && job.current_match) {
    return {
      title: "Decidir se vira candidatura",
      detail: `Match atual de ${job.current_match.match_score}/100. Revise a recomendação e marque como aplicada se fizer sentido.`,
      tone: "medium"
    };
  }

  if (job.is_saved) {
    return {
      title: "Completar contexto antes de aplicar",
      detail: "A vaga está salva. Atualize o match ou registre por que ela merece entrar no pipeline.",
      tone: "warning"
    };
  }

  return {
    title: "Salvar para revisar com calma",
    detail: "Salve a vaga para manter no radar, comparar aderência e decidir a candidatura sem perder contexto.",
    tone: "muted"
  };
}

function buildSearchSummary(count, shown, filters) {
  const parts = [];
  if (filters.search) parts.push(`termo "${filters.search}"`);
  if (filters.company_name) parts.push(`empresa "${filters.company_name}"`);
  if (filters.location) parts.push(`local "${filters.location}"`);
  if (filters.status && filters.status !== "all") parts.push(`vagas ${titleize(filters.status).toLowerCase()}`);
  return parts.length
    ? `Mostrando ${shown} vagas carregadas de ${count} no total para ${parts.join(", ")}.`
    : `Mostrando ${shown} vagas carregadas de ${count} no seu workspace.`;
}

function getJobsEmptyStateContent({ hasResume, jobsCount, savedCount, applicationCount, hasActiveFilters }) {
  if (hasActiveFilters) {
    return {
      eyebrow: "Nenhum resultado para os filtros",
      title: "Nenhuma vaga apareceu com este recorte",
      description: "Seu workspace pode ter vagas salvas, mas os filtros atuais esconderam todas as opções neste momento.",
      nextStep: "Limpe os filtros ou rode uma nova busca para ampliar a shortlist.",
      actionType: "search"
    };
  }

  if (!hasResume) {
    return {
      eyebrow: "Base do fluxo ainda ausente",
      title: "Envie um currículo antes de buscar em volume",
      description: "O currículo ajuda a transformar busca em aderência, prioridade e próximos passos mais confiáveis.",
      nextStep: "Abra Currículos, envie sua versão principal e depois volte para buscar vagas com mais contexto.",
      actionType: "resume"
    };
  }

  if (jobsCount === 0) {
    return {
      eyebrow: "Shortlist vazia",
      title: "Sua busca inicial de vagas ainda não aconteceu",
      description: "Sem vagas no workspace, você ainda não consegue comparar oportunidades nem decidir onde agir primeiro.",
      nextStep: "Use a busca desta página para trazer as primeiras vagas e montar sua shortlist inicial.",
      actionType: "search"
    };
  }

  if (savedCount === 0 && applicationCount === 0) {
    return {
      eyebrow: "Falta a primeira ação",
      title: "Você já encontrou vagas, mas ainda não tomou a primeira ação",
      description: "Salvar uma vaga ou iniciar uma candidatura é o passo que transforma pesquisa em progresso visível.",
      nextStep: "Escolha uma vaga da lista, salve as mais promissoras ou marque a primeira candidatura como iniciada.",
      actionType: "select"
    };
  }

  return {
    eyebrow: "Sem resultados para estes filtros",
    title: "Nenhuma vaga encontrada",
    description: "Seu workspace existe, mas os filtros atuais não retornaram oportunidades para revisar agora.",
    nextStep: "Limpe os filtros ou rode uma nova busca para trazer mais vagas para o workspace.",
    actionType: "search"
  };
}

export function JobsPage() {
  const { request } = useAuth();
  const [jobsState, setJobsState] = useState({ items: [], count: 0, page: 1, hasMore: false });
  const [workspaceStats, setWorkspaceStats] = useState({ savedCount: 0, applicationCount: 0, matchCount: 0 });
  const [resumes, setResumes] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [selectedResumeId, setSelectedResumeId] = useState(null);
  const [filters, setFilters] = useState({ search: "", company_name: "", location: "", status: "all", ordering: "-created_at" });
  const [appliedFilters, setAppliedFilters] = useState({ search: "", company_name: "", location: "", status: "all", ordering: "-created_at" });
  const [scrapeForm, setScrapeForm] = useState({ query: "Backend Engineer", location: "Remote" });
  const [scrapeSummary, setScrapeSummary] = useState(null);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [metaLoading, setMetaLoading] = useState(true);
  const [scrapeLoading, setScrapeLoading] = useState(false);
  const [showProviderDetails, setShowProviderDetails] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [busyAction, setBusyAction] = useState("");

  const selectedJob = useMemo(() => jobsState.items.find((job) => job.id === selectedJobId) ?? null, [jobsState.items, selectedJobId]);
  const selectedResume = useMemo(() => resumes.find((resume) => resume.id === selectedResumeId) ?? null, [resumes, selectedResumeId]);
  const selectedDecision = useMemo(
    () => getMatchDecisionPresentation(selectedJob?.current_match ?? {}),
    [selectedJob],
  );
  const selectedJobWorkflowAction = useMemo(() => getJobWorkflowNextAction(selectedJob ?? {}), [selectedJob]);
  const providerSummary = useMemo(() => getProviderSummary(scrapeSummary), [scrapeSummary]);
  const providerBreakdown = useMemo(() => getProviderBreakdown(scrapeSummary), [scrapeSummary]);
  const searchSummary = useMemo(() => buildSearchSummary(jobsState.count, jobsState.items.length, appliedFilters), [appliedFilters, jobsState.count, jobsState.items.length]);
  const jobsEmptyState = useMemo(
    () =>
      getJobsEmptyStateContent({
        hasResume: resumes.length > 0,
        jobsCount: jobsState.count,
        savedCount: workspaceStats.savedCount,
        applicationCount: workspaceStats.applicationCount,
        hasActiveFilters:
          Boolean(appliedFilters.search.trim())
          || Boolean(appliedFilters.company_name.trim())
          || Boolean(appliedFilters.location.trim())
          || appliedFilters.status !== "all"
      }),
    [
      appliedFilters.company_name,
      appliedFilters.location,
      appliedFilters.search,
      appliedFilters.status,
      jobsState.count,
      resumes.length,
      workspaceStats.applicationCount,
      workspaceStats.savedCount
    ],
  );
  const overviewCardsPresentation = useMemo(() => {
    const input = { jobsCount: jobsState.count, metaLoading, workspaceStats };

    try {
      const cards = getJobsOverviewCardsPresentation?.(input);
      return Array.isArray(cards) && cards.length ? cards : buildJobsOverviewCardsFallback(input);
    } catch {
      return buildJobsOverviewCardsFallback(input);
    }
  }, [jobsState.count, metaLoading, workspaceStats]);

  async function loadWorkspaceMeta() {
    setMetaLoading(true);
    try {
      const [savedPayload, applicationsPayload, matchesPayload, resumesPayload] = await Promise.all([
        request("/hunter/api/saved-jobs/?page_size=1"),
        request("/hunter/api/applications/?page_size=1"),
        request("/hunter/api/matches/?page_size=1"),
        request("/hunter/api/resumes/?page_size=100")
      ]);
      setWorkspaceStats({
        savedCount: savedPayload.count ?? 0,
        applicationCount: applicationsPayload.count ?? 0,
        matchCount: matchesPayload.count ?? 0
      });
      const resumeItems = resumesPayload.results ?? [];
      setResumes(resumeItems);
      setSelectedResumeId((current) =>
        resumeItems.some((resume) => resume.id === current)
          ? current
          : resumeItems.find((resume) => resume.is_active)?.id ?? resumeItems[0]?.id ?? null
      );
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Não foi possível carregar os detalhes do seu workspace de vagas."));
    } finally {
      setMetaLoading(false);
    }
  }

  async function loadJobs({ page = 1, append = false, nextFilters = appliedFilters, pageSize = JOBS_PAGE_SIZE } = {}) {
    setJobsLoading(true);
    setError("");
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize), ordering: nextFilters.ordering });
    if (nextFilters.search.trim()) params.set("search", nextFilters.search.trim());
    if (nextFilters.company_name.trim()) params.set("company_name", nextFilters.company_name.trim());
    if (nextFilters.location.trim()) params.set("location", nextFilters.location.trim());
    if (nextFilters.status !== "all") params.set("status", nextFilters.status);
    try {
      const payload = await request(`/hunter/api/jobs/?${params.toString()}`);
      const incomingItems = payload.results ?? [];
      const combinedItems = append ? [...jobsState.items, ...incomingItems] : incomingItems;
      setJobsState({
        items: combinedItems,
        count: payload.count ?? combinedItems.length,
        page: append ? page : Math.max(1, Math.ceil(combinedItems.length / JOBS_PAGE_SIZE)),
        hasMore: Boolean(payload.next)
      });
      setSelectedJobId((current) => combinedItems.some((job) => job.id === current) ? current : combinedItems[0]?.id ?? null);
    } catch (requestError) {
      if (!append) {
        setJobsState({ items: [], count: 0, page: 1, hasMore: false });
        setSelectedJobId(null);
      }
      setError(getErrorMessage(requestError, "Não foi possível carregar suas vagas agora."));
    } finally {
      setJobsLoading(false);
    }
  }

  async function refreshJobs(preserveLoaded = true) {
    const pageSize = preserveLoaded ? Math.max(JOBS_PAGE_SIZE, jobsState.page * JOBS_PAGE_SIZE) : JOBS_PAGE_SIZE;
    await loadJobs({ page: 1, append: false, nextFilters: appliedFilters, pageSize });
  }

  useEffect(() => { loadWorkspaceMeta(); }, []);
  useEffect(() => { loadJobs({ page: 1, append: false, nextFilters: appliedFilters, pageSize: JOBS_PAGE_SIZE }); }, [appliedFilters]);

  async function runAction(actionKey, callback) {
    setBusyAction(actionKey);
    setError("");
    setFeedback("");
    try {
      await callback();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Não foi possível concluir essa ação."));
    } finally {
      setBusyAction("");
    }
  }

  async function submitScrapeSearch() {
    setScrapeLoading(true);
    setError("");
    setFeedback("");
    setScrapeSummary(null);
    setShowProviderDetails(false);
    try {
      const payload = await request("/hunter/api/scrape/", {
        method: "POST",
        body: JSON.stringify({ query: scrapeForm.query, location: scrapeForm.location })
      });
      setScrapeSummary(payload);
      setFeedback(getScrapeFeedbackMessage(payload));
      await Promise.all([refreshJobs(false), loadWorkspaceMeta()]);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Não foi possível atualizar vagas da web agora."));
    } finally {
      setScrapeLoading(false);
    }
  }

  async function handleScrape(event) {
    event.preventDefault();
    await submitScrapeSearch();
  }

  return (
    <AppShell
      title="Vagas"
      subtitle="Transforme vagas coletadas em uma shortlist prática, com filtros claros, sinais de aderência e próximos passos."
      actions={<button className="button button--ghost" type="button" onClick={() => { refreshJobs(false); loadWorkspaceMeta(); }}>Atualizar workspace</button>}
    >
      {error ? <div className="notice notice--blocked">{error}</div> : null}
      {feedback ? <div className="notice notice--success">{feedback}</div> : null}
      <section className="stats-grid">{overviewCardsPresentation.map((card) => <StatCard key={card.label} label={card.label} value={card.value} helper={card.helper} />)}</section>

      <section className="two-column-grid">
        <SectionCard title="Filtrar workspace" subtitle="Encontre a vaga certa com mais rapidez usando filtros operacionais e ordenação por recência.">
          <form className="stack" onSubmit={(event) => { event.preventDefault(); setAppliedFilters({ ...filters }); }}>
            <div className="jobs-filter-grid">
              <label className="field"><span>Palavra-chave</span><input value={filters.search} onChange={(event) => setFilters((previous) => ({ ...previous, search: event.target.value }))} placeholder="Backend, Python, plataforma..." /></label>
              <label className="field"><span>Empresa</span><input value={filters.company_name} onChange={(event) => setFilters((previous) => ({ ...previous, company_name: event.target.value }))} placeholder="Acme" /></label>
              <label className="field"><span>Local</span><input value={filters.location} onChange={(event) => setFilters((previous) => ({ ...previous, location: event.target.value }))} placeholder="Remoto, Brasil, São Paulo..." /></label>
              <label className="field"><span>Status</span><select value={filters.status} onChange={(event) => setFilters((previous) => ({ ...previous, status: event.target.value }))}>{STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
              <label className="field"><span>Ordenar por</span><select value={filters.ordering} onChange={(event) => setFilters((previous) => ({ ...previous, ordering: event.target.value }))}>{SORT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
            </div>
            <div className="action-row action-row--wrap">
              <button className="button button--primary" type="submit">Aplicar filtros</button>
              <button className="button button--ghost" type="button" onClick={() => {
                const cleared = { search: "", company_name: "", location: "", status: "all", ordering: "-created_at" };
                setFilters(cleared);
                setAppliedFilters(cleared);
              }}>Limpar filtros</button>
            </div>
            <p className="muted-copy">{searchSummary}</p>
          </form>
        </SectionCard>

        <SectionCard title="Buscar vagas" subtitle="Consultamos fontes confiáveis e reunimos as melhores oportunidades disponíveis para o seu perfil.">
          <form className="stack" onSubmit={handleScrape}>
            <div className="jobs-filter-grid">
              <label className="field"><span>Cargo</span><input value={scrapeForm.query} onChange={(event) => setScrapeForm((previous) => ({ ...previous, query: event.target.value }))} /></label>
              <label className="field"><span>Local</span><input value={scrapeForm.location} onChange={(event) => setScrapeForm((previous) => ({ ...previous, location: event.target.value }))} /></label>
            </div>
            <button className="button button--secondary" type="submit" disabled={scrapeLoading}>{scrapeLoading ? "Buscando oportunidades..." : "Buscar vagas"}</button>
          </form>
          <ScrapeProgressBar loading={scrapeLoading} />
          {scrapeSummary ? (
            <div className="detail-stack">
              <ScrapeResultHero payload={scrapeSummary} />
              <div className="insight-list insight-list--four">{providerSummary.map((item) => <div key={item.label}><span>{item.label}</span><strong>{item.value}</strong></div>)}</div>
              {(scrapeSummary.scraped ?? scrapeSummary.raw_scraped ?? 0) === 0 ? <div className="notice notice--info">Não encontramos vagas para este perfil. Tente "Software Engineer", "Backend Developer" ou "Data Scientist", ou remova a restrição de local.</div> : null}
              {providerBreakdown.length ? (
                <div className="provider-details-section">
                  <button type="button" className="button button--ghost button--inline" onClick={() => setShowProviderDetails((prev) => !prev)}>
                    {showProviderDetails ? "Ocultar detalhes das fontes" : "Ver detalhes das fontes"}
                  </button>
                  {showProviderDetails ? (
                    <div className="provider-details-content">
                      <div className="inline-meta"><strong>Status da busca</strong><StatusBadge value={scrapeSummary.status} label={getSearchStatusLabel(scrapeSummary)} tone={scrapeSummary.status_tone ?? "medium"} /></div>
                      <div className="provider-breakdown">{providerBreakdown.map((item) => <article className="provider-breakdown__card" key={item.provider}><div className="inline-meta"><strong>{item.provider}</strong><StatusBadge value={item.statusLabel} label={item.statusLabel} tone={item.tone} /></div><p className="muted-copy">{item.jobsFound} vagas desta fonte</p></article>)}</div>
                      {(scrapeSummary.duplicates_removed ?? 0) > 0 ? <p className="muted-copy">{scrapeSummary.duplicates_removed} duplicatas removidas antes de salvar.</p> : null}
                      {(scrapeSummary.quality_filtered ?? 0) > 0 ? <p className="muted-copy">{scrapeSummary.quality_filtered} itens incompletos filtrados.</p> : null}
                      {(scrapeSummary.persistence_skipped ?? 0) > 0 ? <p className="muted-copy">{scrapeSummary.persistence_skipped} itens ignorados no salvamento.</p> : null}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
        </SectionCard>
      </section>

      <section className="two-column-grid two-column-grid--wide-left">
        <SectionCard title="Workspace de vagas" subtitle="Revise a shortlist, tome ação rapidamente e mantenha listas maiores organizadas com carregamento incremental.">
          {jobsLoading && !jobsState.items.length ? <div className="loading-panel">Carregando seu workspace de vagas...</div> : null}
          {!jobsLoading && !jobsState.items.length ? (
            <EmptyState
              eyebrow={jobsEmptyState.eyebrow}
              title={jobsEmptyState.title}
              description={jobsEmptyState.description}
              nextStep={jobsEmptyState.nextStep}
              action={
                jobsEmptyState.actionType === "resume" ? (
                  <Link className="button button--secondary" to="/resumes">Enviar currículo</Link>
                ) : jobsEmptyState.actionType === "search" ? (
                  <button className="button button--secondary" type="button" disabled={scrapeLoading} onClick={submitScrapeSearch}>
                    {scrapeLoading ? "Buscando vagas..." : "Buscar vagas agora"}
                  </button>
                ) : null
              }
              secondaryAction={
                jobsEmptyState.actionType === "select" ? (
                  <button className="button button--ghost" type="button" onClick={() => refreshJobs(false)}>
                    Revisar vagas
                  </button>
                ) : jobsEmptyState.actionType === "search" ? (
                  <button className="button button--ghost" type="button" onClick={() => {
                    const cleared = { search: "", company_name: "", location: "", status: "all", ordering: "-created_at" };
                    setFilters(cleared);
                    setAppliedFilters(cleared);
                  }}>
                    Limpar filtros
                  </button>
                ) : null
              }
            />
          ) : null}
          {jobsState.items.length ? <div className="list-stack">{jobsState.items.map((job) => {
            const workflowNextAction = getJobWorkflowNextAction(job);
            return <article className={job.id === selectedJobId ? "list-item job-list-item is-selected" : "list-item job-list-item"} key={job.id}>
            <div className="job-list-item__main">
              <div className="inline-meta">
                <button className="list-item__title-button" type="button" onClick={() => setSelectedJobId(job.id)}>{job.title}</button>
                {job.application_status ? <StatusBadge value={job.application_status} /> : null}
                {!job.application_status && job.is_saved ? <StatusBadge value="saved" /> : null}
                {job.current_match ? <span className={`status-badge tone-${getScoreTone(job.current_match.match_score)}`}>{job.current_match.match_score}% aderência</span> : null}
                {job.current_match?.decision_label ? <span className={`status-badge tone-${getMatchDecisionPresentation(job.current_match).tone}`}>{job.current_match.decision_label}</span> : null}
              </div>
              <p>{job.company_name || "Empresa não informada"} | {job.location || "Local não informado"}</p>
              <p className="muted-copy">{job.source ? `${job.source} | ` : ""}{getJobRecencyLabel(job)}</p>
              <p>{getDescriptionPreview(job.description)}</p>
              <div className={`next-action-card next-action-card--compact tone-${workflowNextAction.tone}`}>
                <span>Próximo passo</span>
                <strong>{workflowNextAction.title}</strong>
                <p>{workflowNextAction.detail}</p>
              </div>
            </div>
            <div className="action-row action-row--wrap">
              <button className="button button--ghost" type="button" onClick={() => setSelectedJobId(job.id)}>Ver detalhes</button>
              <button className="button button--ghost" type="button" disabled={busyAction === `save-${job.id}`} onClick={() => runAction(`save-${job.id}`, async () => {
                await request(`/hunter/api/jobs/${job.id}/save/`, { method: job.is_saved ? "DELETE" : "POST" });
                await Promise.all([refreshJobs(), loadWorkspaceMeta()]);
                setFeedback(job.is_saved ? "Vaga removida das salvas." : "Vaga salva no seu workspace.");
              })}>{job.is_saved ? "Remover salva" : "Salvar vaga"}</button>
              <button className="button button--secondary" type="button" disabled={busyAction === `apply-${job.id}`} onClick={() => runAction(`apply-${job.id}`, async () => {
                if (job.application_id) {
                  await request(`/hunter/api/applications/${job.application_id}/`, { method: "PATCH", body: JSON.stringify({ status: "applied" }) });
                } else {
                  await request(`/hunter/api/jobs/${job.id}/apply/`, { method: "POST", body: JSON.stringify({ notes: "Rastreada a partir do workspace de vagas." }) });
                }
                await Promise.all([refreshJobs(), loadWorkspaceMeta()]);
                setFeedback("Vaga movida para o fluxo de candidaturas.");
              })}>{job.application_status === "applied" ? "Aplicada" : job.application_id ? "Mover para aplicada" : "Iniciar candidatura"}</button>
              {job.application_id ? <Link className="button button--ghost" to="/applications">Abrir pipeline</Link> : null}
              {job.url ? <a className="button button--ghost" href={job.url} target="_blank" rel="noreferrer">Abrir vaga original</a> : null}
            </div>
          </article>;
          })}</div> : null}
          {jobsState.hasMore ? <div className="jobs-load-more"><button className="button button--ghost" type="button" disabled={jobsLoading} onClick={() => loadJobs({ page: jobsState.page + 1, append: true, nextFilters: appliedFilters, pageSize: JOBS_PAGE_SIZE })}>{jobsLoading ? "Carregando mais vagas..." : "Carregar mais vagas"}</button></div> : null}
        </SectionCard>

        <SectionCard title="Detalhes da vaga" subtitle="Deixe o próximo passo óbvio com acesso ao anúncio original, controle de status e visibilidade de aderência.">
          {!selectedJob ? <EmptyState eyebrow="Falta abrir uma oportunidade" title="Selecione uma vaga" description="Os detalhes da oportunidade mostram por que ela importa, como agir agora e qual é a aderência com seu currículo." nextStep="Escolha uma vaga da lista ao lado para salvar, iniciar candidatura ou atualizar o match." /> : (
            <div className="detail-stack">
              <div className="inline-meta"><strong>{selectedJob.title}</strong>{selectedJob.application_status ? <StatusBadge value={selectedJob.application_status} /> : null}{!selectedJob.application_status && selectedJob.is_saved ? <StatusBadge value="saved" /> : null}</div>
              <p className="job-detail-company">{selectedJob.company_name || "Empresa não informada"} | {selectedJob.location || "Local não informado"}</p>
              <div className="insight-list insight-list--two"><div><span>Fonte</span><strong>{selectedJob.source || "Indisponível"}</strong></div><div><span>Recência</span><strong>{getJobRecencyLabel(selectedJob)}</strong></div></div>
              <div className={`next-action-card tone-${selectedJobWorkflowAction.tone}`}>
                <span>Próximo passo</span>
                <strong>{selectedJobWorkflowAction.title}</strong>
                <p>{selectedJobWorkflowAction.detail}</p>
              </div>
              <div className="action-row action-row--wrap">
                <button className="button button--ghost" type="button" disabled={busyAction === `save-detail-${selectedJob.id}`} onClick={() => runAction(`save-detail-${selectedJob.id}`, async () => {
                  await request(`/hunter/api/jobs/${selectedJob.id}/save/`, { method: selectedJob.is_saved ? "DELETE" : "POST" });
                  await Promise.all([refreshJobs(), loadWorkspaceMeta()]);
                  setFeedback(selectedJob.is_saved ? "Vaga removida das salvas." : "Vaga salva no seu workspace.");
                })}>{selectedJob.is_saved ? "Remover salva" : "Salvar vaga"}</button>
                <button className="button button--secondary" type="button" disabled={busyAction === `apply-detail-${selectedJob.id}`} onClick={() => runAction(`apply-detail-${selectedJob.id}`, async () => {
                  if (selectedJob.application_id) {
                    await request(`/hunter/api/applications/${selectedJob.application_id}/`, { method: "PATCH", body: JSON.stringify({ status: "applied" }) });
                  } else {
                    await request(`/hunter/api/jobs/${selectedJob.id}/apply/`, { method: "POST", body: JSON.stringify({ notes: "Rastreada a partir do workspace de vagas." }) });
                  }
                  await Promise.all([refreshJobs(), loadWorkspaceMeta()]);
                  setFeedback("Vaga movida para o fluxo de candidaturas.");
                })}>{selectedJob.application_id ? "Mover para aplicada" : "Iniciar candidatura"}</button>
                {selectedJob.application_id ? <Link className="button button--ghost" to="/applications">Abrir pipeline</Link> : null}
                {selectedJob.url ? <a className="button button--ghost" href={selectedJob.url} target="_blank" rel="noreferrer">Abrir anúncio original</a> : null}
              </div>
              {selectedJob.application_id ? <label className="field"><span>Etapa da candidatura</span><select value={selectedJob.application_status ?? "saved"} disabled={busyAction === `stage-${selectedJob.id}`} onChange={(event) => runAction(`stage-${selectedJob.id}`, async () => {
                await request(`/hunter/api/applications/${selectedJob.application_id}/`, { method: "PATCH", body: JSON.stringify({ status: event.target.value }) });
                await Promise.all([refreshJobs(), loadWorkspaceMeta()]);
                setFeedback(`Vaga movida para ${titleize(event.target.value).toLowerCase()}.`);
              })}>{APPLICATION_STATUSES.map((status) => <option key={status} value={status}>{titleize(status)}</option>)}</select></label> : <div className="notice notice--info">Esta vaga ainda não entrou no pipeline de candidaturas. Use a ação de aplicar quando quiser começar a acompanhar as etapas.</div>}
              <SectionCard className="job-detail-subcard" title="Match com currículo" subtitle={selectedResume ? `Atualize a aderência usando ${selectedResume.label || selectedResume.original_filename}.` : "Envie ou ative um currículo para gerar score de aderência."} actions={<button className="button button--secondary" type="button" disabled={!selectedResumeId || busyAction === `match-${selectedJob.id}`} onClick={() => runAction(`match-${selectedJob.id}`, async () => {
                const payload = await request(`/hunter/api/jobs/${selectedJob.id}/match/`, { method: "POST", body: JSON.stringify(selectedResumeId ? { resume_id: selectedResumeId } : {}) });
                await Promise.all([refreshJobs(), loadWorkspaceMeta()]);
                setFeedback(`A aderência foi atualizada para ${payload.match_score}/100.`);
              })}>{busyAction === `match-${selectedJob.id}` ? "Atualizando aderência..." : "Atualizar aderência"}</button>}>
                {resumes.length ? <label className="field"><span>Currículo usado no match</span><select value={selectedResumeId ?? ""} onChange={(event) => setSelectedResumeId(Number(event.target.value))}>{resumes.map((resume) => <option key={resume.id} value={resume.id}>{resume.label || resume.original_filename}{resume.is_active ? " (Principal)" : ""}</option>)}</select></label> : <div className="notice notice--error">Nenhum currículo está disponível para match ainda. Envie um currículo primeiro para liberar o score de aderência.</div>}
                {selectedJob.current_match ? <div className="detail-stack">
                  <div className="insight-list insight-list--three"><div><span>Score de aderência</span><strong>{selectedJob.current_match.match_score}/100</strong></div><div><span>Currículo usado</span><strong>{selectedJob.current_match.resume_label}</strong></div><div><span>Atualizado</span><strong>{formatRelativeDate(selectedJob.current_match.updated_at)}</strong></div></div>
                  <div className={`notice notice--${selectedDecision.tone || getMatchNoticeTone(selectedJob.current_match.match_score)}`}>
                    <div className="inline-meta">
                      <strong>{selectedDecision.title}</strong>
                      {selectedJob.current_match.decision_label ? <StatusBadge value={selectedJob.current_match.decision_class || selectedJob.current_match.decision_label} label={selectedJob.current_match.decision_label} tone={selectedDecision.tone} /> : null}
                    </div>
                    <p>{selectedJob.current_match.recommendation}</p>
                  </div>
                  <div className="signal-list">
                    {selectedJob.current_match.strengths?.length ? <article className="signal-card signal-card--positive"><strong>Forças detectadas</strong><ul className="plain-list">{selectedJob.current_match.strengths.slice(0, 3).map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul></article> : null}
                    {selectedJob.current_match.gaps?.length ? <article className="signal-card signal-card--warning"><strong>Principais gaps</strong><ul className="plain-list">{selectedJob.current_match.gaps.slice(0, 3).map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul></article> : null}
                  </div>
                  {selectedJob.current_match.evidence_signals?.length ? <div><strong>Sinais usados na decisão</strong><ul className="plain-list">{selectedJob.current_match.evidence_signals.slice(0, 4).map((item, index) => {
                    const signalLabel = formatEvidenceSignal(item);
                    return <li key={`${signalLabel}-${index}`}>{signalLabel}</li>;
                  })}</ul></div> : null}
                </div> : <p className="muted-copy">Ainda não existe match para esta vaga. Rode a análise de aderência para ver score, lacunas e recomendação.</p>}
              </SectionCard>
              <div className="detail-stack"><strong>Descrição da vaga</strong><p>{selectedJob.description || "Nenhuma descrição detalhada foi capturada para esta vaga ainda."}</p></div>
            </div>
          )}
        </SectionCard>
      </section>
    </AppShell>
  );
}
