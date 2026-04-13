import { useEffect, useMemo, useState } from "react";

import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { SectionCard } from "../components/SectionCard";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { getResumeInsightPresentation, getResumeParsePresentation } from "../lib/presentation";
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
      badgeLabel: "Selecione um curriculo",
      badgeTone: "muted",
      statusTitle: "Selecione um curriculo",
      statusDetail: "Escolha uma versao da biblioteca para ver o que ja esta pronto.",
      nextStep: "Depois de selecionar, voce podera acompanhar o preparo do arquivo e abrir os insights disponiveis.",
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
      ? "A analise ainda nao foi gerada para este curriculo."
      : "A leitura de senioridade ainda nao foi gerada para este curriculo.";
  }

  if (error.status === 400) {
    return getErrorMessage(
      error,
      kind === "analysis"
        ? "Ainda nao ha texto suficiente para gerar a analise. Reexporte o arquivo com texto selecionavel e tente de novo."
        : "Ainda nao ha conteudo suficiente para estimar senioridade com seguranca.",
    );
  }

  if (error.status === 403) {
    return "Esse insight faz parte do Premium. Faca upgrade para liberar o acesso completo.";
  }

  return getErrorMessage(error, "Nao foi possivel carregar este insight agora.");
}

export function ResumesPage() {
  const { request } = useAuth();
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
  const [form, setForm] = useState({
    file: null,
    label: "",
    target_role: ""
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [busyAction, setBusyAction] = useState("");

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
      setError(getErrorMessage(requestError, "Nao foi possivel carregar sua biblioteca de curriculos agora."));
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
      setAnalysisState({ status: "ready", message: "A analise do curriculo ja esta disponivel." });
    } else {
      setAnalysis(null);
      setAnalysisState({
        status: analysisResult.reason?.status === 404 ? "missing" : "blocked",
        message: getInsightStateMessage("analysis", analysisResult.reason)
      });
    }

    if (seniorityResult.status === "fulfilled") {
      setSeniority(seniorityResult.value);
      setSeniorityState({ status: "ready", message: "A leitura de senioridade ja esta disponivel." });
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

  async function handleUpload(event) {
    event.preventDefault();
    if (!form.file) {
      setError("Escolha um arquivo em PDF ou DOCX para continuar.");
      return;
    }
    if (!isAllowedResumeFile(form.file)) {
      setError("Esse arquivo nao pode ser usado como curriculo. Envie um PDF ou DOCX.");
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
        `"${payload.label || payload.original_filename}" foi recebido. Agora vamos preparar o texto para liberar analise, senioridade e comparacoes.`,
      );
      setForm({
        file: null,
        label: "",
        target_role: ""
      });
      await loadResumes(false);
      setSelectedResumeId(payload.id);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Nao foi possivel enviar esse curriculo agora."));
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
      setError(getErrorMessage(requestError, "Nao foi possivel concluir essa acao agora."));
    } finally {
      setBusyAction("");
    }
  }

  function toggleCompareSelection(resumeId) {
    setSelectedIds((previous) =>
      previous.includes(resumeId)
        ? previous.filter((id) => id !== resumeId)
        : [...previous, resumeId].slice(-3),
    );
  }

  return (
    <AppShell
      title="Curriculos"
      subtitle="Evolua seu curriculo, compare versoes e acompanhe com clareza o que ja esta pronto para gerar insights."
    >
      {error ? <div className="notice notice--blocked">{error}</div> : null}
      {feedback ? <div className="notice notice--success">{feedback}</div> : null}

      <section className="two-column-grid two-column-grid--wide-left">
        <SectionCard
          title="Enviar novo curriculo"
          subtitle="Adicione uma nova versao para revisar, pontuar e usar nas analises de aderencia."
        >
          <form className="stack" onSubmit={handleUpload}>
            <label className="field">
              <span>Arquivo do curriculo</span>
              <input
                type="file"
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(event) =>
                  setForm((previous) => ({ ...previous, file: event.target.files?.[0] ?? null }))
                }
                required
              />
            </label>

            <label className="field">
              <span>Nome da versao</span>
              <input
                value={form.label}
                onChange={(event) => setForm((previous) => ({ ...previous, label: event.target.value }))}
                placeholder="Curriculo backend v3"
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
              {busyAction === "upload" ? "Enviando curriculo..." : "Enviar curriculo"}
            </button>
          </form>
        </SectionCard>

        <SectionCard
          title="Comparacao premium"
          subtitle="Compare duas ou tres versoes para entender qual comunica melhor sua experiencia."
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
                    setFeedback("Comparacao pronta. Revise abaixo os principais contrastes entre as versoes.");
                  } catch (requestError) {
                    if (requestError.status === 403) {
                      setError("A comparacao entre versoes faz parte do Premium. Faca upgrade para liberar esse resultado.");
                      return;
                    }

                    throw requestError;
                  }
                })
              }
            >
              {busyAction === "compare" ? "Comparando versoes..." : "Comparar versoes"}
            </button>
          }
        >
          <p className="muted-copy">
            Selecione duas ou tres versoes abaixo. Se o seu plano ainda nao incluir essa comparacao, vamos avisar antes
            de abrir o resultado.
          </p>
          <div className="selection-pills">
            {selectedCompareResumes.length
              ? selectedCompareResumes.map((resume) => (
                <span key={resume.id}>{resume.label || resume.original_filename}</span>
              ))
              : <span>Selecione as versoes que deseja comparar</span>}
          </div>
          {comparison ? (
            <div className="detail-stack">
              <strong>{comparison.comparison_summary}</strong>
              <p>Cargo-alvo mais provavel: {comparison.likely_target_role ?? "-"}</p>
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
          title="Biblioteca de curriculos"
          subtitle="Escolha sua versao principal e mantenha historico suficiente para revisar evolucoes e comparar resultados."
        >
          {loading ? <div className="loading-panel">Carregando sua biblioteca de curriculos...</div> : null}
          {!loading && !resumes.length ? (
            <EmptyState
              title="Nenhum curriculo por aqui ainda"
              description="Envie seu primeiro curriculo para comecar a melhorar o material e liberar os proximos insights."
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
                      <p>{resume.target_role || "Adicione um cargo-alvo para receber orientacoes mais uteis."}</p>
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
                            setFeedback("Este agora e o curriculo principal usado nas analises e nos matches.");
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
                            setFeedback("Curriculo removido da sua biblioteca.");
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
          title="Insights do curriculo"
          subtitle="Entenda o que ja esta pronto, o que ainda depende de texto utilizavel e o que faz parte do Premium."
          actions={
            selectedResume ? (
              <div className="action-row action-row--wrap">
                <button
                  className="button button--secondary"
                  type="button"
                  disabled={!readiness.canAnalyze || busyAction === "analyze"}
                  title={!readiness.canAnalyze ? `${readiness.statusDetail} ${readiness.nextStep}` : "Gerar analise do curriculo"}
                  onClick={() =>
                    runResumeAction("analyze", async () => {
                      const payload = await request(`/hunter/api/resumes/${selectedResume.id}/analyze/`, {
                        method: "POST"
                      });
                      setAnalysis(payload);
                      setAnalysisState({ status: "ready", message: "A analise do curriculo ja esta pronta." });
                      await loadResumes();
                      setFeedback("Analise concluida. Revise abaixo os pontos fortes e os proximos ajustes.");
                    })
                  }
                >
                  {busyAction === "analyze" ? "Analisando..." : "Analisar curriculo"}
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
                      setSeniorityState({ status: "ready", message: "A leitura de senioridade ja esta pronta." });
                      setFeedback("Leitura de senioridade pronta. Agora voce pode revisar o nivel mais aderente.");
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
                        setReportState({ status: "ready", message: "O insight premium ja esta disponivel." });
                        setFeedback("Insight premium aberto com sucesso.");
                      } catch (requestError) {
                        setReport(null);
                        setReportState({
                          status: requestError.status === 403 ? "locked" : "blocked",
                          message:
                            requestError.status === 403
                              ? "Esse insight faz parte do Premium. Faca upgrade para liberar a visao completa."
                              : getErrorMessage(requestError, "Nao foi possivel abrir o insight premium agora.")
                        });

                        if (requestError.status !== 403) {
                          throw requestError;
                        }
                      }
                    })
                  }
                >
                  {busyAction === "report" ? "Abrindo insight..." : "Abrir insight premium"}
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
                  Abrir curriculo enviado
                </a>
              ) : null}

              <p>{selectedResume.target_role || "Adicione um cargo-alvo para receber orientacoes mais uteis."}</p>

              <div className="insight-list">
                <div>
                  <span>Status do curriculo</span>
                  <strong>{readiness.badgeLabel}</strong>
                </div>
                <div>
                  <span>Analise</span>
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
                </div>
              ) : null}

              {analysis ? (
                <div className="detail-stack">
                  <strong>Destaques da analise</strong>
                  <p>
                    Estrutura {analysis.structure_score} | Clareza {analysis.clarity_score} | Aderencia{" "}
                    {analysis.market_fit_score} | Projetos {analysis.project_score}
                  </p>
                  <ul className="plain-list">
                    {(analysis.recommendations ?? []).map((item, index) => (
                      <li key={`${item}-${index}`}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {seniority ? (
                <div className="detail-stack">
                  <strong>Leitura de senioridade</strong>
                  <p>{titleize(seniority.recommended_track)}</p>
                  <p className="muted-copy">
                    Junior {seniority.junior_score} | Pleno {seniority.mid_score} | Senior {seniority.senior_score}
                  </p>
                </div>
              ) : null}

              {report ? (
                <div className="detail-stack">
                  <strong>Insight premium</strong>
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
              title="Selecione um curriculo"
              description="Escolha uma versao da sua biblioteca para ver feedback, senioridade e recursos premium."
            />
          )}
        </SectionCard>
      </section>
    </AppShell>
  );
}
