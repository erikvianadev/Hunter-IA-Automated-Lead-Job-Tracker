import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { SectionCard } from "../components/SectionCard";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { getPriorityTone, getResumeInsightPresentation, getResumeParsePresentation } from "../lib/presentation";
import { formatShortDate, getErrorMessage, titleize } from "../lib/utils";

const READY_PARSE_STATUSES = new Set(["completed"]);
const ALLOWED_RESUME_EXTENSIONS = new Set(["pdf", "docx"]);

function hasResumeUsableText(resume) {
  const extractedText = (resume?.extracted_text || "").trim();
  return extractedText.length >= 40 && extractedText.split(/\s+/).length >= 8;
}

function isAllowedResumeFile(file) {
  if (!file?.name) {
    return false;
  }

  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  return ALLOWED_RESUME_EXTENSIONS.has(extension);
}

function toNoticeTone(tone) {
  if (tone === "good") {
    return "success";
  }

  if (tone === "warning") {
    return "warning";
  }

  if (tone === "blocked") {
    return "blocked";
  }

  if (tone === "premium") {
    return "premium";
  }

  return "info";
}

function getResumeReadiness(resume) {
  if (!resume) {
    return {
      canAnalyze: false,
      canAssess: false,
      badgeLabel: "Selecione um currículo",
      badgeTone: "muted",
      statusTitle: "Selecione um currículo",
      statusDetail: "Escolha uma versão da biblioteca para ver o que já está pronto.",
      nextStep: "Depois de selecionar, você poderá acompanhar o preparo do arquivo e abrir os insights disponíveis.",
      noticeTone: "info"
    };
  }

  const hasUsableText = hasResumeUsableText(resume);
  const parsePresentation = getResumeParsePresentation(resume.parse_status, { hasUsableText });
  const canUseInsights = READY_PARSE_STATUSES.has(resume.parse_status) && hasUsableText;

  return {
    canAnalyze: canUseInsights,
    canAssess: canUseInsights,
    badgeLabel: parsePresentation.label,
    badgeTone: parsePresentation.tone,
    statusTitle: parsePresentation.title,
    statusDetail: parsePresentation.description,
    nextStep: parsePresentation.nextStep,
    noticeTone: parsePresentation.noticeTone
  };
}

function getInsightStateMessage(kind, error) {
  if (!error) {
    return "";
  }

  if (error.status === 404) {
    return kind === "analysis"
      ? "A análise ainda não foi gerada para este currículo."
      : "A leitura de senioridade ainda não foi gerada para este currículo.";
  }

  if (error.status === 400) {
    return getErrorMessage(
      error,
      kind === "analysis"
        ? "Ainda não há texto suficiente para gerar a análise. Reexporte o arquivo com texto selecionável e tente de novo."
        : "Ainda não há conteúdo suficiente para estimar senioridade com segurança.",
    );
  }

  if (error.status === 403) {
    return "Esse diagnóstico é premium porque aprofunda prioridades, lacunas e próximos ajustes do currículo.";
  }

  return getErrorMessage(error, "Não foi possível carregar este insight agora.");
}

function getResumeUploadErrorMessage(error) {
  if (!error) {
    return "Não foi possível enviar esse currículo agora.";
  }

  if (error.code === "network_error") {
    return "Falha de rede ou conexão durante o envio. Confira sua internet e tente novamente.";
  }

  if (error.status === 401) {
    return "Sua sessão expirou. Entre novamente para enviar o currículo.";
  }

  if (error.status === 403) {
    return "Seu acesso não está autorizado para enviar currículos agora.";
  }

  if (error.status === 413) {
    return "O arquivo enviado passou do limite permitido para currículos.";
  }

  if (error.status === 415) {
    return "Esse arquivo não pode ser usado como currículo. Envie um PDF ou DOCX.";
  }

  if (error.status >= 500) {
    return "O servidor está temporariamente indisponível para receber currículos. Tente novamente em instantes.";
  }

  if (error.status === 400) {
    return getErrorMessage(error, "Arquivo invalido. Revise o PDF ou DOCX e tente novamente.");
  }

  return getErrorMessage(error, "Não foi possível enviar esse currículo agora.");
}

function getPriorityDirectiveLabel(summary) {
  if (!summary?.directive) {
    return "";
  }

  return summary.directive;
}

export function ResumesPage() {
  const { request } = useAuth();
  const fileInputRef = useRef(null);
  const [resumes, setResumes] = useState([]);
  const [selectedResumeId, setSelectedResumeId] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [analysisState, setAnalysisState] = useState({ status: "idle", message: "" });
  const [seniority, setSeniority] = useState(null);
  const [seniorityState, setSeniorityState] = useState({ status: "idle", message: "" });
  const [report, setReport] = useState(null);
  const [reportState, setReportState] = useState({ status: "idle", message: "" });
  const [comparison, setComparison] = useState(null);
  const [comparisonUpgradePrompt, setComparisonUpgradePrompt] = useState(false);
  const [form, setForm] = useState({
    file: null,
    label: "",
    target_role: ""
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [busyAction, setBusyAction] = useState("");
  const [isDragActive, setIsDragActive] = useState(false);

  const selectedResume = useMemo(
    () => resumes.find((resume) => resume.id === selectedResumeId) ?? null,
    [resumes, selectedResumeId],
  );
  const selectedCompareResumes = useMemo(
    () => resumes.filter((resume) => selectedIds.includes(resume.id)),
    [resumes, selectedIds],
  );
  const readiness = useMemo(() => getResumeReadiness(selectedResume), [selectedResume]);
  const analysisPresentation = useMemo(
    () => getResumeInsightPresentation("analysis", analysisState.status),
    [analysisState.status],
  );
  const seniorityPresentation = useMemo(
    () => getResumeInsightPresentation("seniority", seniorityState.status),
    [seniorityState.status],
  );
  const reportPresentation = useMemo(
    () => getResumeInsightPresentation("report", reportState.status),
    [reportState.status],
  );

  async function loadResumes(preserveSelection = true) {
    setLoading(true);
    setError("");

    try {
      const payload = await request("/hunter/api/resumes/");
      const items = payload.results ?? [];
      setResumes(items);

      if (!items.length) {
        setSelectedResumeId(null);
        return;
      }

      if (preserveSelection && items.some((item) => item.id === selectedResumeId)) {
        return;
      }

      const activeResume = items.find((item) => item.is_active) ?? items[0];
      setSelectedResumeId(activeResume.id);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Não foi possível carregar sua biblioteca de currículos agora."));
    } finally {
      setLoading(false);
    }
  }

  async function loadSelectedResumeInsights(resumeId) {
    if (!resumeId) {
      setAnalysis(null);
      setAnalysisState({ status: "idle", message: "" });
      setSeniority(null);
      setSeniorityState({ status: "idle", message: "" });
      setReport(null);
      setReportState({ status: "idle", message: "" });
      return;
    }

    const [analysisResult, seniorityResult] = await Promise.allSettled([
      request(`/hunter/api/resumes/${resumeId}/analysis/`),
      request(`/hunter/api/resumes/${resumeId}/seniority/`)
    ]);

    if (analysisResult.status === "fulfilled") {
      setAnalysis(analysisResult.value);
      setAnalysisState({ status: "ready", message: "A análise do currículo já está disponível." });
    } else {
      setAnalysis(null);
      setAnalysisState({
        status: analysisResult.reason?.status === 404 ? "missing" : "blocked",
        message: getInsightStateMessage("analysis", analysisResult.reason)
      });
    }

    if (seniorityResult.status === "fulfilled") {
      setSeniority(seniorityResult.value);
      setSeniorityState({ status: "ready", message: "A leitura de senioridade já está disponível." });
    } else {
      setSeniority(null);
      setSeniorityState({
        status: seniorityResult.reason?.status === 404 ? "missing" : "blocked",
        message: getInsightStateMessage("seniority", seniorityResult.reason)
      });
    }
  }

  useEffect(() => {
    loadResumes(false);
  }, []);

  useEffect(() => {
    loadSelectedResumeInsights(selectedResumeId);
  }, [selectedResumeId]);

  function handleFileSelected(file) {
    if (!file) {
      setForm((previous) => ({ ...previous, file: null }));
      return;
    }

    setForm((previous) => ({ ...previous, file }));
    if (!isAllowedResumeFile(file)) {
      setError("Esse arquivo não pode ser usado como currículo. Envie um PDF ou DOCX.");
      return;
    }

    setError("");
  }

  function openFilePicker() {
    fileInputRef.current?.click();
  }

  async function handleUpload(event) {
    event.preventDefault();
    if (!form.file) {
      setError("Escolha um arquivo em PDF ou DOCX para continuar.");
      return;
    }
    if (!isAllowedResumeFile(form.file)) {
      setError("Esse arquivo não pode ser usado como currículo. Envie um PDF ou DOCX.");
      return;
    }

    setBusyAction("upload");
    setError("");
    setFeedback("");

    const body = new FormData();
    body.append("file", form.file);
    if (form.label) {
      body.append("label", form.label);
    }
    if (form.target_role) {
      body.append("target_role", form.target_role);
    }

    try {
      const payload = await request("/hunter/api/resumes/", {
        method: "POST",
        body
      });
      setFeedback(
        `"${payload.label || payload.original_filename}" foi recebido. Agora vamos preparar o texto para liberar análise, senioridade e comparações.`,
      );
      setForm({
        file: null,
        label: "",
        target_role: ""
      });
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      await loadResumes(false);
      setSelectedResumeId(payload.id);
    } catch (requestError) {
      setError(getResumeUploadErrorMessage(requestError));
    } finally {
      setBusyAction("");
    }
  }

  async function runResumeAction(actionKey, callback) {
    setBusyAction(actionKey);
    setError("");
    setFeedback("");

    try {
      await callback();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Não foi possível concluir essa ação agora."));
    } finally {
      setBusyAction("");
    }
  }

  function toggleCompareSelection(resumeId) {
    setComparisonUpgradePrompt(false);
    setSelectedIds((previous) =>
      previous.includes(resumeId)
        ? previous.filter((id) => id !== resumeId)
        : [...previous, resumeId].slice(-3),
    );
  }

  return (
    <AppShell
      title="Currículos"
      subtitle="Evolua seu currículo, compare versões e acompanhe com clareza o que já está pronto para gerar insights."
    >
      {error ? <div className="notice notice--blocked">{error}</div> : null}
      {feedback ? <div className="notice notice--success">{feedback}</div> : null}

      <section className="two-column-grid two-column-grid--wide-left">
        <SectionCard
          title="Enviar novo currículo"
          subtitle="Adicione uma nova versão para revisar, pontuar e usar nas análises de aderência."
        >
          {!loading && !resumes.length ? (
            <div className="notice notice--info">
              <strong>Seu primeiro valor começa aqui</strong>
              <p>Quando o currículo entra, você libera análise, senioridade e os próximos passos mais úteis do produto.</p>
            </div>
          ) : null}
          <form className="stack" onSubmit={handleUpload}>
            <div className="field">
              <span>Arquivo do currículo</span>
              <input
                ref={fileInputRef}
                className="sr-only"
                id="resume-file-input"
                type="file"
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(event) => handleFileSelected(event.target.files?.[0] ?? null)}
                required
              />
              <div
                className={isDragActive ? "upload-dropzone is-active" : "upload-dropzone"}
                role="button"
                tabIndex={0}
                onClick={openFilePicker}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openFilePicker();
                  }
                }}
                onDragOver={(event) => {
                  event.preventDefault();
                  setIsDragActive(true);
                }}
                onDragEnter={(event) => {
                  event.preventDefault();
                  setIsDragActive(true);
                }}
                onDragLeave={(event) => {
                  event.preventDefault();
                  setIsDragActive(false);
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  setIsDragActive(false);
                  handleFileSelected(event.dataTransfer.files?.[0] ?? null);
                }}
              >
                <strong>{form.file ? "Arquivo selecionado" : "Arraste seu currículo aqui"}</strong>
                <p>
                  {form.file
                    ? `${form.file.name} (${Math.max(1, Math.round(form.file.size / 1024))} KB)`
                    : "Ou clique para escolher um arquivo PDF ou DOCX."}
                </p>
                <span className="status-badge tone-muted">
                  {form.file ? "Pronto para envio" : "PDF ou DOCX"}
                </span>
              </div>
            </div>

            <label className="field">
              <span>Nome da versão</span>
              <input
                value={form.label}
                onChange={(event) => setForm((previous) => ({ ...previous, label: event.target.value }))}
                placeholder="Currículo backend v3"
              />
            </label>

            <label className="field">
              <span>Cargo-alvo</span>
              <input
                value={form.target_role}
                onChange={(event) =>
                  setForm((previous) => ({ ...previous, target_role: event.target.value }))
                }
                placeholder="Engenheiro(a) Backend"
              />
            </label>

            <button className="button button--primary" type="submit" disabled={busyAction === "upload"}>
              {busyAction === "upload" ? "Enviando currículo..." : "Enviar currículo"}
            </button>
          </form>
        </SectionCard>

        <SectionCard
          title="Comparação premium"
          subtitle="Compare duas ou três versões para decidir qual currículo comunica melhor sua experiência antes de aplicar."
          actions={
            <button
              className="button button--secondary"
              type="button"
              disabled={selectedIds.length < 2 || busyAction === "compare"}
              onClick={() =>
                runResumeAction("compare", async () => {
                  try {
                    const payload = await request(`/hunter/api/resumes/compare/?ids=${selectedIds.join(",")}`);
                    setComparison(payload);
                    setComparisonUpgradePrompt(false);
                    setFeedback("Comparação pronta. Revise abaixo os principais contrastes entre as versões.");
                  } catch (requestError) {
                    if (requestError.status === 403) {
                      setComparisonUpgradePrompt(true);
                      return;
                    }

                    throw requestError;
                  }
                })
              }
            >
              {busyAction === "compare" ? "Comparando versões..." : "Comparar versões"}
            </button>
          }
        >
          <p className="muted-copy">
            Use quando estiver em dúvida entre versões, cargos-alvo ou formas de contar sua experiência. Se o seu plano
            ainda não incluir essa comparação, mostramos o próximo passo sem perder sua seleção.
          </p>
          <div className="selection-pills">
            {selectedCompareResumes.length
              ? selectedCompareResumes.map((resume) => (
                <span key={resume.id}>{resume.label || resume.original_filename}</span>
              ))
              : <span>Selecione as versões que deseja comparar</span>}
          </div>
          {comparisonUpgradePrompt ? (
            <div className="notice notice--premium">
              <strong>Upgrade útil para esta decisão</strong>
              <p>
                A comparação premium ajuda a escolher a versão mais forte antes de aplicar, em vez de testar currículos
                no escuro.
              </p>
              <div className="action-row action-row--wrap">
                <Link className="button button--primary" to="/billing">
                  Ver upgrade para comparar versões
                </Link>
              </div>
            </div>
          ) : null}
          {comparison ? (
            <div className="detail-stack">
              <strong>{comparison.comparison_summary}</strong>
              <p>Cargo-alvo mais provável: {comparison.likely_target_role ?? "-"}</p>
              <div className="list-stack">
                {comparison.main_differences.map((item, index) => (
                  <article className="list-item" key={`${item}-${index}`}>
                    <p>{item}</p>
                  </article>
                ))}
              </div>
            </div>
          ) : null}
        </SectionCard>
      </section>

      <section className="two-column-grid two-column-grid--wide-left">
        <SectionCard
          title="Biblioteca de currículos"
          subtitle="Escolha sua versão principal e mantenha histórico suficiente para revisar evoluções e comparar resultados."
        >
          {loading ? <div className="loading-panel">Carregando sua biblioteca de currículos...</div> : null}
          {!loading && !resumes.length ? (
            <EmptyState
              eyebrow="Etapa 1 da ativação"
              title="Nenhum currículo por aqui ainda"
              description="Sem um currículo ativo, a plataforma ainda não consegue gerar análise, senioridade ou recomendar próximos ajustes com contexto."
              nextStep="Escolha um arquivo em PDF ou DOCX, envie a sua melhor versão atual e depois gere a análise do currículo."
              action={<button className="button button--secondary" type="button" onClick={openFilePicker}>Escolher arquivo</button>}
            />
          ) : null}
          {!loading && resumes.length ? (
            <div className="list-stack">
              {resumes.map((resume) => {
                const resumePresentation = getResumeParsePresentation(resume.parse_status, {
                  hasUsableText: hasResumeUsableText(resume)
                });

                return (
                  <article
                    className={resume.id === selectedResumeId ? "list-item is-selected" : "list-item"}
                    key={resume.id}
                  >
                    <div>
                      <div className="inline-meta">
                        <button
                          className="list-item__title-button"
                          type="button"
                          onClick={() => setSelectedResumeId(resume.id)}
                        >
                          {resume.label || resume.original_filename}
                        </button>
                        <StatusBadge value={resume.parse_status} label={resumePresentation.label} tone={resumePresentation.tone} />
                        {resume.is_active ? <StatusBadge value="active" /> : null}
                      </div>
                      <p>{resume.target_role || "Adicione um cargo-alvo para receber orientações mais úteis."}</p>
                      <p className="muted-copy">Atualizado em {formatShortDate(resume.updated_at)}</p>
                    </div>

                    <div className="action-row action-row--wrap">
                      <label className="checkbox-pill">
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(resume.id)}
                          onChange={() => toggleCompareSelection(resume.id)}
                        />
                        Comparar
                      </label>
                      <button
                        className="button button--ghost"
                        type="button"
                        onClick={() =>
                          runResumeAction(`activate-${resume.id}`, async () => {
                            await request(`/hunter/api/resumes/${resume.id}/activate/`, { method: "POST" });
                            await loadResumes();
                            setFeedback("Este agora é o currículo principal usado nas análises e nos matches.");
                          })
                        }
                      >
                        Tornar principal
                      </button>
                      <button
                        className="button button--ghost"
                        type="button"
                        onClick={() =>
                          runResumeAction(`delete-${resume.id}`, async () => {
                            if (!window.confirm(`Excluir ${resume.label || resume.original_filename}?`)) {
                              return;
                            }
                            await request(`/hunter/api/resumes/${resume.id}/`, { method: "DELETE" });
                            await loadResumes(false);
                            setFeedback("Currículo removido da sua biblioteca.");
                          })
                        }
                      >
                        Excluir
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : null}
        </SectionCard>

        <SectionCard
          title="Insights do currículo"
          subtitle="Entenda o que já está pronto, o que ainda depende de texto utilizável e o que faz parte do Premium."
          actions={
            selectedResume ? (
              <div className="action-row action-row--wrap">
                <button
                  className="button button--secondary"
                  type="button"
                  disabled={!readiness.canAnalyze || busyAction === "analyze"}
                  title={!readiness.canAnalyze ? `${readiness.statusDetail} ${readiness.nextStep}` : "Gerar análise do currículo"}
                  onClick={() =>
                    runResumeAction("analyze", async () => {
                      const payload = await request(`/hunter/api/resumes/${selectedResume.id}/analyze/`, {
                        method: "POST"
                      });
                      setAnalysis(payload);
                      setAnalysisState({ status: "ready", message: "A análise do currículo já está pronta." });
                      await loadResumes();
                      setFeedback("Análise concluída. Revise abaixo os pontos fortes e os próximos ajustes.");
                    })
                  }
                >
                  {busyAction === "analyze" ? "Analisando..." : "Analisar currículo"}
                </button>
                <button
                  className="button button--secondary"
                  type="button"
                  disabled={!readiness.canAssess || busyAction === "seniority"}
                  title={
                    !readiness.canAssess
                      ? `${readiness.statusDetail} ${readiness.nextStep}`
                      : "Gerar leitura de senioridade"
                  }
                  onClick={() =>
                    runResumeAction("seniority", async () => {
                      const payload = await request(`/hunter/api/resumes/${selectedResume.id}/assess-seniority/`, {
                        method: "POST"
                      });
                      setSeniority(payload);
                      setSeniorityState({ status: "ready", message: "A leitura de senioridade já está pronta." });
                      setFeedback("Leitura de senioridade pronta. Agora você pode revisar o nível mais aderente.");
                    })
                  }
                >
                  {busyAction === "seniority" ? "Avaliando..." : "Avaliar senioridade"}
                </button>
                <button
                  className="button button--secondary"
                  type="button"
                  disabled={busyAction === "report"}
                  onClick={() =>
                    runResumeAction("report", async () => {
                      try {
                        const payload = await request(`/hunter/api/resumes/${selectedResume.id}/report/`);
                        setReport(payload);
                        setReportState({ status: "ready", message: "O diagnóstico premium já está disponível." });
                        setFeedback("Diagnóstico premium aberto com sucesso.");
                      } catch (requestError) {
                        setReport(null);
                        setReportState({
                          status: requestError.status === 403 ? "locked" : "blocked",
                          message:
                            requestError.status === 403
                              ? "O Premium libera uma leitura mais profunda deste currículo, com prioridades, lacunas e ações para decidir melhor antes de aplicar."
                              : getErrorMessage(requestError, "Não foi possível abrir o diagnóstico premium agora.")
                        });

                        if (requestError.status !== 403) {
                          throw requestError;
                        }
                      }
                    })
                  }
                >
                  {busyAction === "report" ? "Abrindo diagnóstico..." : "Abrir diagnóstico premium"}
                </button>
              </div>
            ) : null
          }
        >
          {selectedResume ? (
            <div className="detail-stack">
              <div className="inline-meta">
                <strong>{selectedResume.label || selectedResume.original_filename}</strong>
                <StatusBadge
                  value={selectedResume.parse_status}
                  label={readiness.badgeLabel}
                  tone={readiness.badgeTone}
                />
              </div>

              {selectedResume.file_url ? (
                <a href={selectedResume.file_url} target="_blank" rel="noreferrer">
                  Abrir currículo enviado
                </a>
              ) : null}

              <p>{selectedResume.target_role || "Adicione um cargo-alvo para receber orientações mais úteis."}</p>

              <div className="insight-list">
                <div>
                  <span>Status do currículo</span>
                  <strong>{readiness.badgeLabel}</strong>
                </div>
                <div>
                  <span>Análise</span>
                  <strong>{analysis ? `${analysis.overall_score}/100` : analysisPresentation.label}</strong>
                </div>
                <div>
                  <span>Senioridade</span>
                  <strong>{seniority ? titleize(seniority.recommended_track) : seniorityPresentation.label}</strong>
                </div>
              </div>

              <div className={`notice notice--${readiness.noticeTone}`}>
                <strong>{readiness.statusTitle}</strong>
                <p>{readiness.statusDetail}</p>
                <p>{readiness.nextStep}</p>
              </div>

              {!analysis && analysisState.message ? (
                <div className={`notice notice--${toNoticeTone(analysisPresentation.tone)}`}>
                  <strong>{analysisPresentation.title}</strong>
                  <p>{analysisState.message}</p>
                  <p>{analysisPresentation.nextStep}</p>
                </div>
              ) : null}

              {!seniority && seniorityState.message ? (
                <div className={`notice notice--${toNoticeTone(seniorityPresentation.tone)}`}>
                  <strong>{seniorityPresentation.title}</strong>
                  <p>{seniorityState.message}</p>
                  <p>{seniorityPresentation.nextStep}</p>
                </div>
              ) : null}

              {!report && reportState.message ? (
                <div className={`notice notice--${toNoticeTone(reportPresentation.tone)}`}>
                  <strong>{reportPresentation.title}</strong>
                  <p>{reportState.message}</p>
                  <p>{reportPresentation.nextStep}</p>
                  {reportState.status === "locked" ? (
                    <div className="action-row action-row--wrap">
                      <Link className="button button--primary" to="/billing">
                        Ver upgrade para este diagnóstico
                      </Link>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {analysis ? (
                <div className="detail-stack">
                  <strong>Destaques da análise</strong>
                  <div className="insight-list insight-list--four">
                    <div>
                      <span>Estrutura</span>
                      <strong>{analysis.structure_score}/100</strong>
                    </div>
                    <div>
                      <span>Clareza</span>
                      <strong>{analysis.clarity_score}/100</strong>
                    </div>
                    <div>
                      <span>Aderência</span>
                      <strong>{analysis.market_fit_score}/100</strong>
                    </div>
                    <div>
                      <span>Projetos</span>
                      <strong>{analysis.project_score}/100</strong>
                    </div>
                  </div>

                  {analysis.priority_summary?.title ? (
                    <div className={`notice notice--${getPriorityTone(analysis.priority_summary.label)}`}>
                      <div className="priority-summary">
                        <div className="inline-meta">
                          <strong>{analysis.priority_summary.title}</strong>
                          <StatusBadge
                            value={analysis.priority_summary.label}
                            label={analysis.priority_summary.label}
                            tone={getPriorityTone(analysis.priority_summary.label)}
                          />
                          {getPriorityDirectiveLabel(analysis.priority_summary) ? (
                            <span className="status-badge tone-muted">{getPriorityDirectiveLabel(analysis.priority_summary)}</span>
                          ) : null}
                        </div>
                        <p>{analysis.priority_summary.impact}</p>
                      </div>
                    </div>
                  ) : null}

                  {analysis.priority_actions?.length ? (
                    <div className="priority-action-grid">
                      {analysis.priority_actions.slice(0, 3).map((item, index) => (
                        <article className="priority-card" key={`${item.title}-${index}`}>
                          <div className="inline-meta">
                            <strong>{item.title}</strong>
                            <StatusBadge
                              value={item.priority_label}
                              label={item.priority_label}
                              tone={getPriorityTone(item.priority_label)}
                            />
                            {item.fix_first ? <span className="status-badge tone-warning">Corrija primeiro</span> : null}
                          </div>
                          <p><strong>Motivo:</strong> {item.reason}</p>
                          <p><strong>Impacto:</strong> {item.impact}</p>
                        </article>
                      ))}
                    </div>
                  ) : null}

                  {analysis.working_signals?.length ? (
                    <div>
                      <strong>O que já está funcionando</strong>
                      <div className="signal-list">
                        {analysis.working_signals.slice(0, 3).map((item, index) => (
                          <article className="signal-card signal-card--positive" key={`${item.title}-${index}`}>
                            <strong>{item.title}</strong>
                            <p>{item.statement}</p>
                            <p className="muted-copy">{item.evidence}</p>
                          </article>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {analysis.missing_signals?.length ? (
                    <div>
                      <strong>O que está te segurando</strong>
                      <div className="signal-list">
                        {analysis.missing_signals.slice(0, 3).map((item, index) => (
                          <article className="signal-card signal-card--warning" key={`${item.title}-${index}`}>
                            <strong>{item.title}</strong>
                            <p>{item.statement}</p>
                            <p className="muted-copy">{item.risk}</p>
                          </article>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {seniority ? (
                <div className="detail-stack">
                  <strong>Leitura de senioridade</strong>
                  <p>{titleize(seniority.recommended_track)}</p>
                  <p className="muted-copy">
                    Estágio {seniority.internship_score} | Júnior {seniority.junior_score} | Pleno {seniority.mid_score} | Sênior {seniority.senior_score}
                  </p>
                </div>
              ) : null}

              {report ? (
                <div className="detail-stack">
                  <strong>Diagnóstico premium</strong>
                  <p>{report.executive_summary}</p>
                  <ul className="plain-list">
                    {(report.priority_actions ?? []).map((item, index) => (
                      <li key={`${item}-${index}`}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : (
            <EmptyState
              eyebrow="Nenhuma versão selecionada"
              title="Selecione um currículo"
              description="Os insights aparecem quando você escolhe uma versão da biblioteca para analisar ou acompanhar."
              nextStep="Selecione um currículo da lista ao lado ou envie uma nova versão para continuar sua ativação."
              action={<button className="button button--secondary" type="button" onClick={openFilePicker}>Enviar currículo</button>}
              secondaryAction={<Link className="button button--ghost" to="/billing">Ver planos</Link>}
            />
          )}
        </SectionCard>
      </section>
    </AppShell>
  );
}
