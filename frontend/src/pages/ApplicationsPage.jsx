import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { SectionCard } from "../components/SectionCard";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { getMatchDecisionPresentation, getMatchNoticeTone } from "../lib/presentation";
import { formatDate, formatRelativeDate, formatShortDate, getErrorMessage, titleize } from "../lib/utils";

const APPLICATION_STATUSES = ["saved", "applied", "interview", "rejected", "offer", "archived"];
const APPLICATION_STAGE_FALLBACKS = {
  saved: {
    label: "Salva",
    tone: "muted",
    title: "No radar",
    summary: "Vaga separada para decidir se vale entrar no pipeline."
  },
  applied: {
    label: "Aplicada",
    tone: "good",
    title: "Aplicação enviada",
    summary: "Agora o foco é acompanhar retorno e registrar atualizações."
  },
  interview: {
    label: "Entrevista",
    tone: "medium",
    title: "Conversa ativa",
    summary: "Use este espaço para preparar a conversa e guardar observações."
  },
  rejected: {
    label: "Rejeitada",
    tone: "low",
    title: "Processo encerrado",
    summary: "Registre aprendizados úteis antes de arquivar ou seguir adiante."
  },
  offer: {
    label: "Oferta",
    tone: "good",
    title: "Decisão em aberto",
    summary: "Compare proposta, contexto e sinais antes de decidir."
  },
  archived: {
    label: "Arquivada",
    tone: "muted",
    title: "Fora do foco atual",
    summary: "Mantida no histórico para consulta, sem exigir ação agora."
  }
};
const APPLICATION_STAGE_OPTIONS = APPLICATION_STATUSES.map((status) => ({
  value: status,
  ...APPLICATION_STAGE_FALLBACKS[status]
}));
const ORDER_OPTIONS = [
  { value: "-updated_at", label: "Atualizadas recentemente" },
  { value: "-applied_at", label: "Aplicadas recentemente" },
  { value: "updated_at", label: "Atualizações mais antigas" },
  { value: "applied_at", label: "Aplicações mais antigas" }
];

const QUICK_ACTIONS = {
  saved: [
    { status: "applied", label: "Marcar como aplicada", variant: "secondary" },
    { status: "archived", label: "Arquivar", variant: "ghost" }
  ],
  applied: [
    { status: "interview", label: "Mover para entrevista", variant: "secondary" },
    { status: "rejected", label: "Marcar como rejeitada", variant: "ghost" },
    { status: "archived", label: "Arquivar", variant: "ghost" }
  ],
  interview: [
    { status: "offer", label: "Marcar oferta", variant: "secondary" },
    { status: "rejected", label: "Marcar como rejeitada", variant: "ghost" },
    { status: "archived", label: "Arquivar", variant: "ghost" }
  ],
  rejected: [
    { status: "archived", label: "Arquivar", variant: "ghost" },
    { status: "saved", label: "Voltar para salvas", variant: "ghost" }
  ],
  offer: [
    { status: "archived", label: "Arquivar", variant: "ghost" },
    { status: "interview", label: "Voltar para entrevista", variant: "ghost" }
  ],
  archived: [
    { status: "saved", label: "Restaurar para salvas", variant: "secondary" },
    { status: "applied", label: "Restaurar para aplicadas", variant: "ghost" }
  ]
};
const NOTE_TEMPLATES = [
  {
    label: "Entrevista",
    value: "Entrevista:\n- Participantes:\n- Pontos a validar:\n- Próximo combinado:"
  },
  {
    label: "Prazo",
    value: "Prazo / follow-up:\n- Data combinada:\n- Quem acionar:\n- O que enviar:"
  },
  {
    label: "Continuar ou parar",
    value: "Decisão:\n- Motivos para continuar:\n- Riscos ou requisitos faltantes:\n- Sinal para parar:"
  },
  {
    label: "Retorno recebido",
    value: "Atualização recebida:\n- O que mudou:\n- Próxima etapa:\n- Observação importante:"
  }
];

function getScoreTone(score) {
  if (score >= 80) return "good";
  if (score >= 60) return "warning";
  return "blocked";
}

function getApplicationStage(application) {
  return application?.stage_presentation ?? APPLICATION_STAGE_FALLBACKS[application?.status] ?? {
    label: titleize(application?.status),
    tone: "muted",
    title: "Etapa registrada",
    summary: "Acompanhe esta candidatura pelo status atual."
  };
}

function getApplicationNextAction(application) {
  if (application?.next_action) {
    return application.next_action;
  }

  if (application?.status === "applied") {
    return {
      title: application.notes?.trim() ? "Aguardar retorno e registrar atualização" : "Registrar contexto do envio",
      detail: application.notes?.trim()
        ? "Mantenha notas de retorno, follow-up ou mudança de etapa."
        : "Salve canal, contato, data combinada ou qualquer sinal útil para o próximo follow-up.",
      cta_label: application.notes?.trim() ? "Atualizar notas" : "Salvar notas",
      tone: application.notes?.trim() ? "medium" : "warning"
    };
  }

  if (application?.status === "interview") {
    return {
      title: "Preparar conversa e registrar observações",
      detail: "Anote pauta, perguntas abertas, feedback e próximos combinados.",
      cta_label: "Atualizar observações",
      tone: "medium"
    };
  }

  return {
    title: "Revisar candidatura",
    detail: "Confira etapa, contexto e notas para definir a próxima ação.",
    cta_label: "Atualizar contexto",
    tone: "medium"
  };
}

function getRecordedContext(application) {
  if (application?.recorded_context?.length) {
    return application.recorded_context;
  }

  const context = [`Etapa atual: ${getApplicationStage(application).label}`];
  if (application?.applied_at) context.push("Data de aplicação registrada");
  if (application?.job_source) context.push(`Fonte da vaga: ${application.job_source}`);
  if (application?.current_match) {
    context.push(`Match: ${application.current_match.match_score}/100 com ${application.current_match.resume_label}`);
  }
  if (application?.notes?.trim()) context.push("Notas de acompanhamento registradas");
  return context;
}

function getMissingContext(application) {
  if (application?.missing_context?.length) {
    return application.missing_context;
  }

  const missing = [];
  if (!application?.current_match) missing.push("Match com currículo");
  if (!application?.notes?.trim()) missing.push("Notas de acompanhamento");
  if (!application?.job_url) missing.push("Link original da vaga");
  return missing;
}

function getSummaryPreview(text, fallback) {
  if (!text?.trim()) {
    return fallback;
  }

  const clean = text.trim();
  return clean.length <= 180 ? clean : `${clean.slice(0, 180).trim()}...`;
}

function getApplicationListPreview(application) {
  if (application.notes?.trim()) {
    return getSummaryPreview(application.notes, "");
  }

  if (application.current_match?.recommendation) {
    return getSummaryPreview(application.current_match.recommendation, "");
  }

  return getSummaryPreview(
    application.job_description,
    "Abra o detalhe da candidatura para registrar notas, mudanças de etapa e próximos passos.",
  );
}

function buildTrackerSummary(count, shown, filters) {
  const parts = [];
  if (filters.search) parts.push(`termo "${filters.search}"`);
  if (filters.company_name) parts.push(`empresa "${filters.company_name}"`);
  if (filters.status) parts.push(`etapa ${titleize(filters.status).toLowerCase()}`);

  return parts.length
    ? `Mostrando ${shown} candidaturas rastreadas de ${count} para ${parts.join(", ")}.`
    : `Mostrando ${shown} candidaturas rastreadas de ${count} no seu pipeline.`;
}

function getStatusCounts(applications) {
  return applications.reduce(
    (accumulator, application) => ({
      ...accumulator,
      [application.status]: (accumulator[application.status] ?? 0) + 1
    }),
    {},
  );
}

function getApplicationsEmptyStateContent({ resumeCount, jobCount, savedCount, hasActiveFilters }) {
  if (hasActiveFilters) {
    return {
      eyebrow: "Nenhum item para este filtro",
      title: "Nenhuma candidatura apareceu com este recorte",
      description: "Seu pipeline pode ter itens, mas este recorte não mostra nenhuma etapa para acompanhar agora.",
      nextStep: "Limpe os filtros ou ajuste a etapa buscada para reencontrar a candidatura que precisa de atualização.",
      actionType: "filters"
    };
  }

  if (resumeCount === 0) {
    return {
      eyebrow: "Fluxo ainda no início",
      title: "Falta o currículo que conecta vaga, match e candidatura",
      description: "Sem currículo, a candidatura perde contexto de aderência e fica mais difícil decidir o próximo passo.",
      nextStep: "Abra Currículos, envie sua versão principal e depois volte para salvar vagas ou iniciar candidaturas com match.",
      actionType: "resume"
    };
  }

  if (jobCount === 0) {
    return {
      eyebrow: "Ainda sem oportunidades no radar",
      title: "Sua busca de vagas ainda não gerou oportunidades para acompanhar",
      description: "Sem vagas no workspace, ainda não existe uma oportunidade concreta para salvar, aplicar ou acompanhar.",
      nextStep: "Abra Vagas, rode a busca inicial e monte uma shortlist antes de acompanhar etapas aqui.",
      actionType: "jobs"
    };
  }

  if (savedCount === 0) {
    return {
      eyebrow: "Nenhuma vaga priorizada",
      title: "Falta escolher a primeira vaga para transformar em candidatura",
      description: "Salvar ou aplicar em uma vaga cria o ponto de partida do seu pipeline e deixa o próximo follow-up visível.",
      nextStep: "Abra Vagas, salve as oportunidades mais promissoras ou marque a primeira como aplicada.",
      actionType: "jobs"
    };
  }

  return {
    eyebrow: "Pipeline ainda vazio",
    title: "Nenhuma candidatura rastreada ainda",
    description: "Você já tem base para agir, mas ainda não existe uma candidatura com etapa, contexto e notas para acompanhar.",
    nextStep: "Volte para Vagas e marque a primeira oportunidade como aplicada para abrir o painel operacional dela aqui.",
    actionType: "jobs"
  };
}

export function ApplicationsPage() {
  const { request } = useAuth();
  const [applications, setApplications] = useState([]);
  const [selectedApplicationId, setSelectedApplicationId] = useState(null);
  const [filters, setFilters] = useState({ status: "", search: "", company_name: "", ordering: "-updated_at" });
  const [appliedFilters, setAppliedFilters] = useState({ status: "", search: "", company_name: "", ordering: "-updated_at" });
  const [editingNotes, setEditingNotes] = useState({});
  const [workspaceMeta, setWorkspaceMeta] = useState({ resumeCount: 0, jobCount: 0, savedCount: 0 });
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [busyAction, setBusyAction] = useState("");

  const selectedApplication = useMemo(
    () => applications.find((application) => application.id === selectedApplicationId) ?? null,
    [applications, selectedApplicationId],
  );
  const selectedDecision = useMemo(
    () => getMatchDecisionPresentation(selectedApplication?.current_match ?? {}),
    [selectedApplication],
  );
  const selectedStage = useMemo(() => getApplicationStage(selectedApplication), [selectedApplication]);
  const selectedNextAction = useMemo(() => getApplicationNextAction(selectedApplication), [selectedApplication]);
  const selectedRecordedContext = useMemo(() => getRecordedContext(selectedApplication), [selectedApplication]);
  const selectedMissingContext = useMemo(() => getMissingContext(selectedApplication), [selectedApplication]);
  const statusCounts = useMemo(() => getStatusCounts(applications), [applications]);
  const trackerSummary = useMemo(
    () => buildTrackerSummary(totalCount, applications.length, appliedFilters),
    [applications.length, appliedFilters, totalCount],
  );
  const applicationsEmptyState = useMemo(
    () =>
      getApplicationsEmptyStateContent({
        ...workspaceMeta,
        hasActiveFilters:
          Boolean(appliedFilters.status)
          || Boolean(appliedFilters.search.trim())
          || Boolean(appliedFilters.company_name.trim())
      }),
    [appliedFilters.company_name, appliedFilters.search, appliedFilters.status, workspaceMeta],
  );
  const notesChanged = selectedApplication
    ? (editingNotes[selectedApplication.id] ?? "") !== (selectedApplication.notes ?? "")
    : false;
  const savedNotesPreview = selectedApplication?.notes?.trim()
    ? getSummaryPreview(selectedApplication.notes, "")
    : "Nenhuma nota salva ainda. Use este espaço para registrar contexto, próximas ações e sinais importantes.";
  const selectedNotesHighlights = selectedApplication?.notes_highlights?.length
    ? selectedApplication.notes_highlights
    : selectedApplication?.notes?.trim()
      ? [getSummaryPreview(selectedApplication.notes, "")]
      : [];

  async function loadApplications() {
    setLoading(true);
    setError("");

    const params = new URLSearchParams({
      ordering: appliedFilters.ordering,
      page_size: "100"
    });
    if (appliedFilters.status) {
      params.set("status", appliedFilters.status);
    }
    if (appliedFilters.search.trim()) {
      params.set("search", appliedFilters.search.trim());
    }
    if (appliedFilters.company_name.trim()) {
      params.set("company_name", appliedFilters.company_name.trim());
    }

    try {
      const [payload, jobsPayload, savedPayload, resumesPayload] = await Promise.all([
        request(`/hunter/api/applications/?${params.toString()}`),
        request("/hunter/api/jobs/?page_size=1"),
        request("/hunter/api/saved-jobs/?page_size=1"),
        request("/hunter/api/resumes/?page_size=1")
      ]);
      const items = payload.results ?? [];
      setApplications(items);
      setTotalCount(payload.count ?? items.length);
      setWorkspaceMeta({
        resumeCount: resumesPayload.count ?? 0,
        jobCount: jobsPayload.count ?? 0,
        savedCount: savedPayload.count ?? 0
      });
      setSelectedApplicationId((current) =>
        items.some((item) => item.id === current) ? current : items[0]?.id ?? null
      );
      setEditingNotes(Object.fromEntries(items.map((item) => [item.id, item.notes ?? ""])));
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Não foi possível carregar seu rastreador de candidaturas."));
      setApplications([]);
      setWorkspaceMeta({ resumeCount: 0, jobCount: 0, savedCount: 0 });
      setTotalCount(0);
      setSelectedApplicationId(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadApplications();
  }, [appliedFilters]);

  async function updateApplication(application, payload, successMessage) {
    setBusyAction(`application-${application.id}`);
    setError("");
    setFeedback("");

    try {
      await request(`/hunter/api/applications/${application.id}/`, {
        method: "PATCH",
        body: JSON.stringify(payload)
      });
      setFeedback(successMessage);
      await loadApplications();
      setSelectedApplicationId(application.id);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Não foi possível atualizar esta candidatura."));
    } finally {
      setBusyAction("");
    }
  }

  function appendNoteTemplate(application, template) {
    setEditingNotes((previous) => {
      const currentValue = previous[application.id] ?? "";
      const separator = currentValue.trim() ? "\n\n" : "";
      return {
        ...previous,
        [application.id]: `${currentValue}${separator}${template.value}`
      };
    });
  }

  const overviewCards = [
    { label: "Rastreadas", value: totalCount, helper: "Carregadas do seu pipeline" },
    { label: "Em movimento", value: (statusCounts.applied ?? 0) + (statusCounts.interview ?? 0) + (statusCounts.offer ?? 0), helper: "Pedem acompanhamento real" },
    { label: "Sem notas", value: applications.filter((application) => !application.notes?.trim()).length, helper: "Precisam de contexto salvo" },
    { label: "Ofertas", value: statusCounts.offer ?? 0, helper: "Decisões positivas em aberto" }
  ];

  return (
    <AppShell
      title="Candidaturas"
      subtitle="Gerencie seu pipeline de candidatura com etapa clara, próxima ação, contexto de vaga/currículo e notas de acompanhamento."
      actions={
        <button className="button button--ghost" type="button" onClick={loadApplications}>
          Atualizar rastreador
        </button>
      }
    >
      {error ? <div className="notice notice--blocked">{error}</div> : null}
      {feedback ? <div className="notice notice--success">{feedback}</div> : null}

      <section className="stats-grid">
        {overviewCards.map((card) => (
          <StatCard key={card.label} label={card.label} value={card.value} helper={card.helper} />
        ))}
      </section>

      <SectionCard
        title="Filtrar rastreador"
        subtitle="Afine o pipeline por etapa, termo, empresa e recência para encontrar o próximo follow-up com mais facilidade."
      >
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault();
            setAppliedFilters({ ...filters });
          }}
        >
            <div className="jobs-filter-grid">
              <label className="field">
                <span>Palavra-chave</span>
                <input
                  value={filters.search}
                  onChange={(event) => setFilters((previous) => ({ ...previous, search: event.target.value }))}
                  placeholder="Cargo, recrutador, nota, termo..."
                />
              </label>

              <label className="field">
                <span>Empresa</span>
                <input
                  value={filters.company_name}
                  onChange={(event) => setFilters((previous) => ({ ...previous, company_name: event.target.value }))}
                  placeholder="Acme"
                />
              </label>

              <label className="field">
                <span>Etapa</span>
                <select
                  value={filters.status}
                  onChange={(event) => setFilters((previous) => ({ ...previous, status: event.target.value }))}
                >
                  <option value="">Todas as etapas</option>
                  {APPLICATION_STATUSES.map((status) => (
                    <option key={status} value={status}>
                      {titleize(status)}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>Ordenar por</span>
              <select
                value={filters.ordering}
                onChange={(event) => setFilters((previous) => ({ ...previous, ordering: event.target.value }))}
              >
                {ORDER_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="action-row action-row--wrap">
            <button className="button button--primary" type="submit">
              Aplicar filtros
            </button>
            <button
              className="button button--ghost"
              type="button"
              onClick={() => {
                const cleared = { status: "", search: "", company_name: "", ordering: "-updated_at" };
                setFilters(cleared);
                setAppliedFilters(cleared);
              }}
            >
              Limpar filtros
            </button>
          </div>

          <p className="muted-copy">{trackerSummary}</p>
        </form>
      </SectionCard>

      <section className="two-column-grid two-column-grid--wide-left">
        <SectionCard
          title="Pipeline de candidaturas"
          subtitle="Veja status, origem, recência e contexto de aderência sem precisar abrir cada item."
        >
          {loading ? <div className="loading-panel">Carregando seu fluxo de candidaturas...</div> : null}
          {!loading && !applications.length ? (
            <EmptyState
              eyebrow={applicationsEmptyState.eyebrow}
              title={applicationsEmptyState.title}
              description={applicationsEmptyState.description}
              nextStep={applicationsEmptyState.nextStep}
              action={
                applicationsEmptyState.actionType === "resume" ? (
                  <Link className="button button--secondary" to="/resumes">Enviar currículo</Link>
                ) : applicationsEmptyState.actionType === "filters" ? (
                  <button
                    className="button button--secondary"
                    type="button"
                    onClick={() => {
                      const cleared = { status: "", search: "", company_name: "", ordering: "-updated_at" };
                      setFilters(cleared);
                      setAppliedFilters(cleared);
                    }}
                  >
                    Limpar filtros
                  </button>
                ) : (
                  <Link className="button button--secondary" to="/jobs">Abrir vagas</Link>
                )
              }
            />
          ) : null}

          {!loading && applications.length ? (
            <div className="list-stack">
              {applications.map((application) => {
                const stage = getApplicationStage(application);
                const nextAction = getApplicationNextAction(application);
                const missingContext = getMissingContext(application);
                return (
                <article
                  className={application.id === selectedApplicationId ? "list-item application-list-item is-selected" : "list-item application-list-item"}
                  key={application.id}
                >
                  <div className="application-list-item__main">
                    <div className="application-stage-strip">
                      <div>
                        <span>Etapa atual</span>
                        <strong>{stage.title}</strong>
                      </div>
                      <StatusBadge value={application.status} label={stage.label} tone={stage.tone} />
                    </div>

                    <div className="inline-meta">
                      <button className="list-item__title-button" type="button" onClick={() => setSelectedApplicationId(application.id)}>
                        {application.job_title}
                      </button>
                      {application.job_source ? <span className="status-badge tone-muted">{application.job_source}</span> : null}
                      {application.current_match ? (
                        <span className={`status-badge tone-${getScoreTone(application.current_match.match_score)}`}>
                          {application.current_match.match_score}% aderência
                        </span>
                      ) : null}
                      {application.current_match?.decision_label ? <span className={`status-badge tone-${getMatchDecisionPresentation(application.current_match).tone}`}>{application.current_match.decision_label}</span> : null}
                    </div>

                    <p>
                      {application.company_name || "Empresa não informada"}
                      {application.job_location ? ` | ${application.job_location}` : ""}
                    </p>

                    <p className="muted-copy">
                      {application.applied_at ? `Aplicada em ${formatShortDate(application.applied_at)} | ` : "Ainda não marcada como aplicada | "}
                      Atualizada {formatRelativeDate(application.updated_at)}
                    </p>

                    <div className={`next-action-card next-action-card--compact tone-${nextAction.tone || "medium"}`}>
                      <span>Próxima ação</span>
                      <strong>{nextAction.title}</strong>
                      <p>{nextAction.detail}</p>
                    </div>

                    <p className={application.notes?.trim() ? "notes-preview notes-preview--inline" : ""}>{getApplicationListPreview(application)}</p>

                    <div className="selection-pills">
                      {application.job_is_saved ? <span>Salva no workspace de vagas</span> : null}
                      {application.current_match?.resume_label ? <span>Currículo: {application.current_match.resume_label}</span> : null}
                      {application.notes?.trim() ? <span>Com notas</span> : <span>Sem notas</span>}
                      {missingContext.length ? <span>Faltam {missingContext.length} itens</span> : <span>Contexto completo</span>}
                    </div>
                  </div>

                  <div className="action-row action-row--wrap">
                    <label className="field field--compact">
                      <span>Mover etapa</span>
                      <select
                        value={application.status}
                        disabled={busyAction === `application-${application.id}`}
                        onChange={(event) =>
                          updateApplication(
                            application,
                            { status: event.target.value },
                            `Candidatura movida para ${titleize(event.target.value).toLowerCase()}.`,
                          )
                        }
                      >
                        {APPLICATION_STAGE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button className="button button--ghost" type="button" onClick={() => setSelectedApplicationId(application.id)}>
                      Ver detalhes
                    </button>
                    {application.job_url ? (
                      <a className="button button--ghost" href={application.job_url} target="_blank" rel="noreferrer">
                        Abrir vaga
                      </a>
                    ) : null}
                  </div>
                </article>
                );
              })}
            </div>
          ) : null}
        </SectionCard>

        <SectionCard
          title="Detalhes da candidatura"
          subtitle="Use o item selecionado como painel de controle para etapas, notas e contexto de aderência."
        >
          {!selectedApplication ? (
            <EmptyState
              eyebrow="Falta abrir um item do pipeline"
              title="Selecione uma candidatura"
              description="Ao abrir uma candidatura, você consegue entender a etapa atual, registrar contexto e decidir o próximo follow-up com mais segurança."
              nextStep="Escolha um item da lista para atualizar o status, salvar notas e revisar o contexto da vaga."
            />
          ) : (
            <div className="detail-stack">
              <div className={`application-command-panel tone-${selectedStage.tone || "medium"}`}>
                <div className="application-command-panel__stage">
                  <span>Etapa atual</span>
                  <div className="inline-meta">
                    <strong>{selectedStage.title}</strong>
                    <StatusBadge value={selectedApplication.status} label={selectedStage.label} tone={selectedStage.tone} />
                  </div>
                  <p>{selectedStage.summary}</p>
                </div>

                <div className={`next-action-card tone-${selectedNextAction.tone || "medium"}`}>
                  <span>Próxima ação recomendada</span>
                  <strong>{selectedNextAction.title}</strong>
                  <p>{selectedNextAction.detail}</p>
                </div>
              </div>

              <div className="inline-meta">
                <strong>{selectedApplication.job_title}</strong>
                {selectedApplication.current_match ? (
                  <span className={`status-badge tone-${getScoreTone(selectedApplication.current_match.match_score)}`}>
                    {selectedApplication.current_match.match_score}/100 aderência
                  </span>
                ) : null}
              </div>

              <p className="job-detail-company">
                {selectedApplication.company_name || "Empresa não informada"}
                {selectedApplication.job_location ? ` | ${selectedApplication.job_location}` : ""}
              </p>

              <div className="insight-list insight-list--four">
                <div>
                  <span>Fonte</span>
                  <strong>{selectedApplication.job_source || "Indisponível"}</strong>
                </div>
                <div>
                  <span>Data da aplicação</span>
                  <strong>{selectedApplication.applied_at ? formatShortDate(selectedApplication.applied_at) : "Ainda não marcada"}</strong>
                </div>
                <div>
                  <span>Última atualização</span>
                  <strong>{formatDate(selectedApplication.updated_at)}</strong>
                </div>
                <div>
                  <span>Workspace de vagas</span>
                  <strong>{selectedApplication.job_is_saved ? "Vinculada e salva" : "Apenas candidatura"}</strong>
                </div>
              </div>

              <div className="application-detail-panel">
                <label className="field">
                  <span>Etapa</span>
                  <select
                    value={selectedApplication.status}
                    disabled={busyAction === `application-${selectedApplication.id}`}
                    onChange={(event) =>
                      updateApplication(
                        selectedApplication,
                        { status: event.target.value },
                        `Candidatura movida para ${titleize(event.target.value).toLowerCase()}.`,
                      )
                    }
                  >
                    {APPLICATION_STAGE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <div className="action-row action-row--wrap">
                  {(QUICK_ACTIONS[selectedApplication.status] ?? []).map((action) => (
                    <button
                      key={action.status}
                      className={`button button--${action.variant}`}
                      type="button"
                      disabled={busyAction === `application-${selectedApplication.id}`}
                      onClick={() =>
                        updateApplication(
                          selectedApplication,
                          { status: action.status },
                          `Candidatura movida para ${titleize(action.status).toLowerCase()}.`,
                        )
                      }
                    >
                      {action.label}
                    </button>
                  ))}
                  {selectedApplication.job_url ? (
                    <a className="button button--ghost" href={selectedApplication.job_url} target="_blank" rel="noreferrer">
                      Abrir anúncio original
                    </a>
                  ) : null}
                </div>
              </div>

              <SectionCard
                className="job-detail-subcard"
                title="Contexto operacional"
              subtitle="Veja rapidamente o que já está registrado e o que ainda falta para decidir o próximo passo."
              >
                <div className="context-grid">
                  <article className="context-card context-card--recorded">
                    <strong>Já registrado</strong>
                    <ul className="plain-list">
                      {selectedRecordedContext.map((item, index) => (
                        <li key={`${item}-${index}`}>{item}</li>
                      ))}
                    </ul>
                  </article>

                  <article className="context-card context-card--missing">
                    <div className="inline-meta">
                      <strong>Ainda falta</strong>
                      <span className={`status-badge ${selectedMissingContext.length ? "tone-warning" : "tone-good"}`}>
                        {selectedMissingContext.length ? `${selectedMissingContext.length} itens` : "Tudo essencial"}
                      </span>
                    </div>
                    {selectedMissingContext.length ? (
                      <ul className="plain-list">
                        {selectedMissingContext.map((item, index) => (
                          <li key={`${item}-${index}`}>{item}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="muted-copy">O contexto essencial para acompanhar esta candidatura já está visível.</p>
                    )}
                  </article>
                </div>
                {selectedApplication.current_match ? (
                  <div className={`notice notice--${selectedDecision.tone || getMatchNoticeTone(selectedApplication.current_match.match_score)}`}>
                    <div className="inline-meta">
                      <strong>Currículo e match atual</strong>
                      <span className={`status-badge tone-${getScoreTone(selectedApplication.current_match.match_score)}`}>
                        {selectedApplication.current_match.match_score}/100
                      </span>
                      <span className="status-badge tone-muted">{selectedApplication.current_match.resume_label}</span>
                    </div>
                    <p>{selectedApplication.current_match.recommendation}</p>
                  </div>
                ) : (
                  <div className="notice notice--info">
                    <strong>Match ainda ausente</strong>
                    <p>Atualize a aderência pelo workspace de vagas para ver currículo usado, score e recomendação antes do próximo passo.</p>
                  </div>
                )}
              </SectionCard>

              <SectionCard
                className="job-detail-subcard"
                title="Notas e próximos passos"
                subtitle="Registre retornos de recrutadores, preparo para entrevistas, bloqueios e ações práticas."
              >
                <div className="notes-panel">
                  <div className="inline-meta">
                    <strong>Resumo rápido</strong>
                    <span className={`status-badge ${selectedApplication.notes?.trim() ? "tone-good" : "tone-muted"}`}>
                      {selectedApplication.notes?.trim() ? "Com notas" : "Sem notas"}
                    </span>
                    {notesChanged ? <span className="status-badge tone-medium">Rascunho alterado</span> : null}
                  </div>
                  <p className={selectedApplication.notes?.trim() ? "notes-preview" : "muted-copy"}>{savedNotesPreview}</p>
                  {selectedNotesHighlights.length ? (
                    <ul className="plain-list notes-highlights">
                      {selectedNotesHighlights.map((item, index) => (
                        <li key={`${item}-${index}`}>{item}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>

                <div className="note-template-row">
                  <span>Modelos rápidos</span>
                  <div className="action-row action-row--wrap">
                    {NOTE_TEMPLATES.map((template) => (
                      <button
                        key={template.label}
                        className="button button--ghost"
                        type="button"
                        onClick={() => appendNoteTemplate(selectedApplication, template)}
                      >
                        {template.label}
                      </button>
                    ))}
                  </div>
                </div>

                <label className="field">
                  <span>Notas</span>
                  <textarea
                    rows="8"
                    value={editingNotes[selectedApplication.id] ?? ""}
                    onChange={(event) =>
                      setEditingNotes((previous) => ({
                        ...previous,
                        [selectedApplication.id]: event.target.value
                      }))
                    }
                    placeholder="Adicione contexto do recrutador, preparação para entrevista, informações de remuneração ou próximos passos..."
                  />
                </label>

                {notesChanged ? <div className="notice notice--info">Você tem alterações não salvas nas notas desta candidatura.</div> : null}

                <div className="action-row action-row--wrap">
                  <button
                    className="button button--secondary"
                    type="button"
                    disabled={busyAction === `application-${selectedApplication.id}` || !notesChanged}
                    onClick={() =>
                      updateApplication(
                        selectedApplication,
                        { notes: editingNotes[selectedApplication.id] ?? "" },
                        "Notas da candidatura salvas.",
                      )
                    }
                  >
                    Salvar notas da candidatura
                  </button>
                  <button
                    className="button button--ghost"
                    type="button"
                    disabled={!notesChanged}
                    onClick={() =>
                      setEditingNotes((previous) => ({
                        ...previous,
                        [selectedApplication.id]: selectedApplication.notes ?? ""
                      }))
                    }
                  >
                    Descartar rascunho
                  </button>
                  <span className="muted-copy">Última atualização {formatRelativeDate(selectedApplication.updated_at)}</span>
                </div>
              </SectionCard>

              <SectionCard
                className="job-detail-subcard"
                title="Contexto de match"
                subtitle={
                  selectedApplication.current_match
                    ? `Usando ${selectedApplication.current_match.resume_label} como o contexto mais recente de currículo.`
                    : "Ainda não existe um match relacionado a esta candidatura."
                }
              >
                {selectedApplication.current_match ? (
                  <div className="detail-stack">
                    <div className="insight-list insight-list--three">
                      <div>
                        <span>Score de aderência</span>
                        <strong>{selectedApplication.current_match.match_score}/100</strong>
                      </div>
                      <div>
                        <span>Currículo usado</span>
                        <strong>{selectedApplication.current_match.resume_label}</strong>
                      </div>
                      <div>
                        <span>Atualizado</span>
                        <strong>{formatRelativeDate(selectedApplication.current_match.updated_at)}</strong>
                      </div>
                    </div>

                    <div className={`notice notice--${selectedDecision.tone || getMatchNoticeTone(selectedApplication.current_match.match_score)}`}>
                      <div className="inline-meta">
                        <strong>{selectedDecision.title}</strong>
                        {selectedApplication.current_match.decision_label ? <StatusBadge value={selectedApplication.current_match.decision_class || selectedApplication.current_match.decision_label} label={selectedApplication.current_match.decision_label} tone={selectedDecision.tone} /> : null}
                      </div>
                      <p>{selectedApplication.current_match.recommendation}</p>
                    </div>

                    <div className="signal-list">
                      {selectedApplication.current_match.strengths?.length ? (
                        <article className="signal-card signal-card--positive">
                          <strong>Forças detectadas</strong>
                          <ul className="plain-list">
                            {selectedApplication.current_match.strengths.slice(0, 3).map((item, index) => (
                              <li key={`${item}-${index}`}>{item}</li>
                            ))}
                          </ul>
                        </article>
                      ) : null}

                      {selectedApplication.current_match.gaps?.length ? (
                        <article className="signal-card signal-card--warning">
                          <strong>Pontos de atenção</strong>
                          <ul className="plain-list">
                            {selectedApplication.current_match.gaps.slice(0, 3).map((item, index) => (
                              <li key={`${item}-${index}`}>{item}</li>
                            ))}
                          </ul>
                        </article>
                      ) : null}
                    </div>

                    {selectedApplication.current_match.evidence_signals?.length ? (
                      <div>
                        <strong>Sinais usados na decisão</strong>
                        <ul className="plain-list">
                          {selectedApplication.current_match.evidence_signals.slice(0, 4).map((item, index) => (
                            <li key={`${item}-${index}`}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <p className="muted-copy">
                    Esta candidatura ainda não tem um match associado. Você pode seguir acompanhando o fluxo aqui e atualizar a aderência depois pelo workspace de vagas.
                  </p>
                )}
              </SectionCard>

              <SectionCard
                className="job-detail-subcard"
                title="Resumo da vaga"
                subtitle="Mantenha o contexto da oportunidade por perto enquanto conduz a candidatura."
              >
                <p>{selectedApplication.job_description || "Nenhum resumo detalhado da vaga foi capturado para esta candidatura ainda."}</p>
              </SectionCard>
            </div>
          )}
        </SectionCard>
      </section>
    </AppShell>
  );
}
