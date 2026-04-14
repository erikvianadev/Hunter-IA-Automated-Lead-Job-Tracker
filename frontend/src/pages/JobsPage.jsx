import { useEffect, useMemo, useState } from "react";

import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { SectionCard } from "../components/SectionCard";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { getJobsOverviewCardsPresentation, getMatchNoticeTone } from "../lib/presentation";
import { formatRelativeDate, formatShortDate, getErrorMessage, titleize } from "../lib/utils";

const JOBS_PAGE_SIZE = 12;
const APPLICATION_STATUSES = ["saved", "applied", "interview", "rejected", "offer", "archived"];
const STATUS_OPTIONS = [{ value: "all", label: "Todas as vagas" }, { value: "saved", label: "Salvas" }, { value: "applied", label: "Aplicadas" }];
const SORT_OPTIONS = [
  { value: "-created_at", label: "Salvas mais recentes" },
  { value: "-date_posted", label: "Publicadas mais recentemente" },
  { value: "company_name", label: "Empresa A-Z" },
  { value: "title", label: "Cargo A-Z" }
];

function buildScrapeFeedback(payload) {
  if (!payload) return "";
  const rawScraped = payload.raw_scraped ?? 0;
  if (!rawScraped) return "A busca terminou, mas nenhum provider retornou vagas compatíveis. Tente um cargo mais amplo ou uma localização menos restrita.";
  return `Busca concluída. ${rawScraped} vagas foram coletadas, ${payload.scraped ?? 0} ficaram após a deduplicação e ${payload.saved ?? 0} foram salvas.`;
}

function getProviderSummary(payload) {
  if (!payload) return [];
  return [
    { label: "Providers verificados", value: payload.providers_run?.length ?? 0 },
    { label: "Coletadas", value: payload.raw_scraped ?? 0 },
    { label: "Únicas", value: payload.scraped ?? 0 },
    { label: "Salvas", value: payload.saved ?? 0 }
  ];
}

function getProviderBreakdown(payload) {
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
        statusLabel: blocked ? "blocked" : failed ? "issue" : "healthy"
      };
    })
    .sort((left, right) => right.jobsFound - left.jobsFound || left.provider.localeCompare(right.provider));
}

function getScrapeFeedbackMessage(payload) {
  if (!payload) return "";
  const rawScraped = payload.raw_scraped ?? 0;
  if (!rawScraped) return "A coleta terminou sem vagas aproveitaveis desta vez. Tente um cargo mais amplo ou alivie o filtro de local.";
  return `Coleta concluida. Encontramos ${rawScraped} vagas, mantivemos ${payload.scraped ?? 0} unicas e salvamos ${payload.saved ?? 0} no workspace.`;
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
      helper: savedCount ? "Prontas para revisao" : "Salve oportunidades para comparar com calma."
    },
    {
      label: "Candidaturas",
      value: metaLoading ? "..." : applicationCount,
      helper: applicationCount ? "Ja em andamento" : "Marque vagas como aplicadas para acompanhar as etapas."
    },
    {
      label: "Matches gerados",
      value: metaLoading ? "..." : matchCount,
      helper: matchCount ? "Com visibilidade de aderencia" : "Atualize a aderencia para descobrir onde vale focar."
    }
  ];
}

function ExpandableDescription({ text, collapsedChars = 560 }) {
  const [expanded, setExpanded] = useState(false);
  const content = (text || "").trim();

  if (!content) {
    return <p className="job-description">Nenhuma descricao detalhada foi capturada para esta vaga ainda.</p>;
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
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [busyAction, setBusyAction] = useState("");

  const selectedJob = useMemo(() => jobsState.items.find((job) => job.id === selectedJobId) ?? null, [jobsState.items, selectedJobId]);
  const selectedResume = useMemo(() => resumes.find((resume) => resume.id === selectedResumeId) ?? null, [resumes, selectedResumeId]);
  const providerSummary = useMemo(() => getProviderSummary(scrapeSummary), [scrapeSummary]);
  const providerBreakdown = useMemo(() => getProviderBreakdown(scrapeSummary), [scrapeSummary]);
  const searchSummary = useMemo(() => buildSearchSummary(jobsState.count, jobsState.items.length, appliedFilters), [appliedFilters, jobsState.count, jobsState.items.length]);
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

  async function handleScrape(event) {
    event.preventDefault();
    setScrapeLoading(true);
    setError("");
    setFeedback("");
    setScrapeSummary(null);
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

        <SectionCard title="Buscar vagas novas" subtitle="Rode o scraping dos providers ativos, veja o resumo da coleta e acompanhe quais fontes estão contribuindo.">
          <form className="stack" onSubmit={handleScrape}>
            <div className="jobs-filter-grid">
              <label className="field"><span>Cargo</span><input value={scrapeForm.query} onChange={(event) => setScrapeForm((previous) => ({ ...previous, query: event.target.value }))} /></label>
              <label className="field"><span>Local</span><input value={scrapeForm.location} onChange={(event) => setScrapeForm((previous) => ({ ...previous, location: event.target.value }))} /></label>
            </div>
            <button className="button button--secondary" type="submit" disabled={scrapeLoading}>{scrapeLoading ? "Consultando providers..." : "Buscar vagas"}</button>
          </form>
          {scrapeLoading ? <div className="loading-inline">Verificando providers, removendo duplicadas e salvando novas vagas...</div> : null}
          {scrapeSummary ? (
            <div className="detail-stack">
              <div className="inline-meta"><strong>Última coleta</strong><StatusBadge value={scrapeSummary.status} tone="medium" /></div>
              <div className="insight-list insight-list--four">{providerSummary.map((item) => <div key={item.label}><span>{item.label}</span><strong>{item.value}</strong></div>)}</div>
              {providerBreakdown.length ? <div className="provider-breakdown">{providerBreakdown.map((item) => <article className="provider-breakdown__card" key={item.provider}><div className="inline-meta"><strong>{item.provider}</strong><StatusBadge value={item.statusLabel} tone={item.tone} /></div><p className="muted-copy">{item.jobsFound} vagas contribuíram para o resultado</p></article>)}</div> : null}
              {(scrapeSummary.raw_scraped ?? 0) === 0 ? <div className="notice notice--info">Nenhuma vaga compatível foi encontrada desta vez. Tente termos mais amplos, como "Software Engineer", ou remova restrições de local.</div> : null}
              {(scrapeSummary.duplicates_removed ?? 0) > 0 ? <p className="muted-copy">{scrapeSummary.duplicates_removed} vagas sobrepostas foram removidas antes de salvar.</p> : null}
            </div>
          ) : null}
        </SectionCard>
      </section>

      <section className="two-column-grid two-column-grid--wide-left">
        <SectionCard title="Workspace de vagas" subtitle="Revise a shortlist, tome ação rapidamente e mantenha listas maiores organizadas com carregamento incremental.">
          {jobsLoading && !jobsState.items.length ? <div className="loading-panel">Carregando seu workspace de vagas...</div> : null}
          {!jobsLoading && !jobsState.items.length ? <EmptyState title="Nenhuma vaga encontrada" description="Tente filtros mais amplos ou rode uma nova coleta para trazer oportunidades para o workspace." /> : null}
          {jobsState.items.length ? <div className="list-stack">{jobsState.items.map((job) => <article className={job.id === selectedJobId ? "list-item job-list-item is-selected" : "list-item job-list-item"} key={job.id}>
            <div className="job-list-item__main">
              <div className="inline-meta">
                <button className="list-item__title-button" type="button" onClick={() => setSelectedJobId(job.id)}>{job.title}</button>
                {job.application_status ? <StatusBadge value={job.application_status} /> : null}
                {!job.application_status && job.is_saved ? <StatusBadge value="saved" /> : null}
                {job.current_match ? <span className={`status-badge tone-${getScoreTone(job.current_match.match_score)}`}>{job.current_match.match_score}% aderência</span> : null}
              </div>
              <p>{job.company_name || "Empresa não informada"} | {job.location || "Local não informado"}</p>
              <p className="muted-copy">{job.source ? `${job.source} | ` : ""}{getJobRecencyLabel(job)}</p>
              <p>{getDescriptionPreview(job.description)}</p>
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
              })}>{job.application_status === "applied" ? "Aplicada" : "Marcar como aplicada"}</button>
              {job.url ? <a className="button button--ghost" href={job.url} target="_blank" rel="noreferrer">Abrir vaga original</a> : null}
            </div>
          </article>)}</div> : null}
          {jobsState.hasMore ? <div className="jobs-load-more"><button className="button button--ghost" type="button" disabled={jobsLoading} onClick={() => loadJobs({ page: jobsState.page + 1, append: true, nextFilters: appliedFilters, pageSize: JOBS_PAGE_SIZE })}>{jobsLoading ? "Carregando mais vagas..." : "Carregar mais vagas"}</button></div> : null}
        </SectionCard>

        <SectionCard title="Detalhes da vaga" subtitle="Deixe o próximo passo óbvio com acesso ao anúncio original, controle de status e visibilidade de aderência.">
          {!selectedJob ? <EmptyState title="Selecione uma vaga" description="Escolha uma vaga da lista para ver detalhes, ajustar o status e revisar a aderência com o currículo." /> : (
            <div className="detail-stack">
              <div className="inline-meta"><strong>{selectedJob.title}</strong>{selectedJob.application_status ? <StatusBadge value={selectedJob.application_status} /> : null}{!selectedJob.application_status && selectedJob.is_saved ? <StatusBadge value="saved" /> : null}</div>
              <p className="job-detail-company">{selectedJob.company_name || "Empresa não informada"} | {selectedJob.location || "Local não informado"}</p>
              <div className="insight-list insight-list--two"><div><span>Fonte</span><strong>{selectedJob.source || "Indisponível"}</strong></div><div><span>Recência</span><strong>{getJobRecencyLabel(selectedJob)}</strong></div></div>
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
                })}>Marcar como aplicada</button>
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
                  <div className={`notice notice--${getMatchNoticeTone(selectedJob.current_match.match_score)}`}><strong>{selectedJob.current_match.match_score >= 80 ? "Boa aderencia para priorizar" : selectedJob.current_match.match_score >= 60 ? "Aderencia promissora, com ajustes" : "Aderencia baixa neste momento"}</strong><p>{selectedJob.current_match.recommendation}</p></div>
                  {selectedJob.current_match.gaps?.length ? <div><strong>Principais lacunas</strong><ul className="plain-list">{selectedJob.current_match.gaps.slice(0, 3).map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul></div> : null}
                  {selectedJob.current_match.strengths?.length ? <div><strong>Pontos fortes</strong><ul className="plain-list">{selectedJob.current_match.strengths.slice(0, 2).map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul></div> : null}
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
