import { useEffect, useMemo, useState } from "react";

import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { SectionCard } from "../components/SectionCard";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { formatShortDate, getErrorMessage, titleize } from "../lib/utils";

const READY_PARSE_STATUSES = new Set(["completed"]);
const NOT_READY_PARSE_STATUSES = new Set(["failed", "empty_text", "unsupported_structure", "pending", "processing"]);

function getResumeReadiness(resume) {
  if (!resume) {
    return {
      canAnalyze: false,
      canAssess: false,
      parseTone: "muted",
      statusTitle: "Selecione um currículo",
      statusDetail: "Escolha um currículo para ver o que já está disponível."
    };
  }

  const parseStatus = resume.parse_status;
  const extractedText = (resume.extracted_text || "").trim();
  const hasUsableText = extractedText.length >= 40 && extractedText.split(/\s+/).length >= 8;
  const parseReady = READY_PARSE_STATUSES.has(parseStatus);

  if (!parseReady || !hasUsableText) {
    const detailByStatus = {
      pending: "Este currículo ainda está sendo preparado. Aguarde o parsing terminar para gerar insights.",
      processing: "Este currículo ainda está em processamento. Os insights serão liberados quando o texto estiver pronto.",
      failed: "Não foi possível ler conteúdo suficiente deste arquivo. Envie um PDF ou DOCX mais limpo para continuar.",
      empty_text: "O arquivo foi enviado, mas nenhum texto utilizável foi encontrado. Tente exportar um PDF ou DOCX com texto selecionável.",
      unsupported_structure: "A estrutura do arquivo não pôde ser lida bem o suficiente para gerar insights. Tente uma exportação mais limpa."
    };

    return {
      canAnalyze: false,
      canAssess: false,
      parseTone: "low",
      statusTitle: "Currículo ainda não está pronto",
      statusDetail:
        detailByStatus[parseStatus] ??
        "Este currículo ainda precisa de texto utilizável para liberar análise e avaliação de senioridade.",
      hasUsableText,
      parseReady
    };
  }

  return {
    canAnalyze: true,
    canAssess: true,
    parseTone: "good",
    statusTitle: "Pronto para análise",
    statusDetail: "Este currículo já tem texto suficiente para análise e avaliação de senioridade.",
    hasUsableText,
    parseReady
  };
}

function getInsightStateMessage(kind, error) {
  if (!error) {
    return "";
  }

  if (error.status === 404) {
    return kind === "analysis"
      ? "A análise deste currículo ainda não foi gerada."
      : "A avaliação de senioridade ainda não foi gerada.";
  }

  if (error.status === 400) {
    return getErrorMessage(
      error,
      kind === "analysis"
        ? "Este currículo precisa de mais texto legível antes da análise."
        : "Este currículo precisa de conteúdo suficiente antes da estimativa de senioridade.",
    );
  }

  if (error.status === 403) {
    return "Esse insight premium está disponível apenas nos planos pagos.";
  }

  return getErrorMessage(error, "Não foi possível carregar este insight agora.");
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
      setError(getErrorMessage(requestError, "Não foi possível carregar seus currículos agora."));
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
      setAnalysisState({ status: "ready", message: "A análise do currículo está pronta." });
    } else {
      setAnalysis(null);
      setAnalysisState({
        status: analysisResult.reason?.status === 404 ? "missing" : "blocked",
        message: getInsightStateMessage("analysis", analysisResult.reason)
      });
    }

    if (seniorityResult.status === "fulfilled") {
      setSeniority(seniorityResult.value);
      setSeniorityState({ status: "ready", message: "A avaliação de senioridade está pronta." });
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
      setError("Escolha um currículo em PDF ou DOCX para continuar.");
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
      setFeedback(`"${payload.label || payload.original_filename}" foi enviado e já está disponível para revisão.`);
      setForm({
        file: null,
        label: "",
        target_role: ""
      });
      await loadResumes(false);
      setSelectedResumeId(payload.id);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Não foi possível enviar esse currículo."));
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
      setError(getErrorMessage(requestError, "Não foi possível concluir essa ação."));
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
    <AppShell title="Currículos" subtitle="Evolua seu currículo, compare versões e acompanhe o que já está pronto para gerar insights.">
      {error ? <div className="notice notice--error">{error}</div> : null}
      {feedback ? <div className="notice notice--success">{feedback}</div> : null}

      <section className="two-column-grid two-column-grid--wide-left">
        <SectionCard title="Enviar novo currículo" subtitle="Adicione uma nova versão para revisar, pontuar e usar nas análises de aderência.">
          <form className="stack" onSubmit={handleUpload}>
            <label className="field">
              <span>Arquivo do currículo</span>
              <input
                type="file"
                accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(event) =>
                  setForm((previous) => ({ ...previous, file: event.target.files?.[0] ?? null }))
                }
                required
              />
            </label>

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
          subtitle="Compare duas ou três versões para descobrir qual comunica melhor sua experiência."
          actions={
            <button
              className="button button--secondary"
              type="button"
              disabled={selectedIds.length < 2 || busyAction === "compare"}
              onClick={() =>
                runResumeAction("compare", async () => {
                  const payload = await request(`/hunter/api/resumes/compare/?ids=${selectedIds.join(",")}`);
                  setComparison(payload);
                  setFeedback("Sua comparação de currículos está pronta.");
                })
              }
            >
              {busyAction === "compare" ? "Comparando versões..." : "Comparar versões"}
            </button>
          }
        >
          <p className="muted-copy">
            Selecione duas ou três versões abaixo. O acesso premium continua sendo validado pelas regras do backend.
          </p>
          <div className="selection-pills">
            {selectedCompareResumes.length
              ? selectedCompareResumes.map((resume) => (
                <span key={resume.id}>{resume.label || resume.original_filename}</span>
              ))
              : <span>Selecione as versões que deseja comparar</span>}
          </div>
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
        <SectionCard title="Biblioteca de currículos" subtitle="Escolha sua versão principal e mantenha versões antigas para comparação.">
          {loading ? <div className="loading-panel">Carregando sua biblioteca de currículos...</div> : null}
          {!loading && !resumes.length ? (
            <EmptyState
              title="Nenhum currículo por aqui ainda"
              description="Envie seu primeiro currículo para começar a melhorar o material e liberar insights premium."
            />
          ) : null}
          {!loading && resumes.length ? (
            <div className="list-stack">
              {resumes.map((resume) => (
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
                      <StatusBadge value={resume.parse_status} />
                      {resume.is_active ? <StatusBadge value="active" /> : null}
                    </div>
                    <p>{resume.target_role || "Nenhum cargo-alvo definido ainda"}</p>
                    <p className="muted-copy">Atualizado em {formatShortDate(resume.updated_at)}</p>
                  </div>

                  <div className="action-row">
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
                          setFeedback("Este agora é o seu currículo principal.");
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
                          setFeedback("Currículo removido.");
                        })
                      }
                    >
                      Excluir
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : null}
        </SectionCard>

        <SectionCard
          title="Insights do currículo"
          subtitle="Veja o que já está pronto, o que ainda depende de texto utilizável e o que faz parte do premium."
          actions={
            selectedResume ? (
              <div className="action-row">
                <button
                  className="button button--secondary"
                  type="button"
                  disabled={!readiness.canAnalyze || busyAction === "analyze"}
                  title={!readiness.canAnalyze ? readiness.statusDetail : "Gerar análise do currículo"}
                  onClick={() =>
                    runResumeAction("analyze", async () => {
                      const payload = await request(`/hunter/api/resumes/${selectedResume.id}/analyze/`, {
                        method: "POST"
                      });
                      setAnalysis(payload);
                      setAnalysisState({ status: "ready", message: "A análise do currículo está pronta." });
                      await loadResumes();
                      setFeedback("A análise do currículo está pronta.");
                    })
                  }
                >
                  {busyAction === "analyze" ? "Analisando..." : "Analisar currículo"}
                </button>
                <button
                  className="button button--secondary"
                  type="button"
                  disabled={!readiness.canAssess || busyAction === "seniority"}
                  title={!readiness.canAssess ? readiness.statusDetail : "Gerar avaliação de senioridade"}
                  onClick={() =>
                    runResumeAction("seniority", async () => {
                      const payload = await request(`/hunter/api/resumes/${selectedResume.id}/assess-seniority/`, {
                        method: "POST"
                      });
                      setSeniority(payload);
                      setSeniorityState({ status: "ready", message: "A avaliação de senioridade está pronta." });
                      setFeedback("A avaliação de senioridade está pronta.");
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
                        setReportState({ status: "ready", message: "O insight premium foi liberado." });
                        setFeedback("O insight premium foi liberado.");
                      } catch (requestError) {
                        setReport(null);
                        setReportState({
                          status: requestError.status === 403 ? "locked" : "blocked",
                          message:
                            requestError.status === 403
                              ? "Esse insight premium está disponível apenas nos planos pagos."
                              : getErrorMessage(requestError, "Não foi possível abrir o relatório premium.")
                        });

                        if (requestError.status !== 403) {
                          throw requestError;
                        }
                      }
                    })
                  }
                >
                  {busyAction === "report" ? "Abrindo relatório..." : "Abrir insight premium"}
                </button>
              </div>
            ) : null
          }
        >
          {selectedResume ? (
            <div className="detail-stack">
              <div className="inline-meta">
                <strong>{selectedResume.label || selectedResume.original_filename}</strong>
                <StatusBadge value={selectedResume.parse_status} />
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
                  <strong>{readiness.statusTitle}</strong>
                </div>
                <div>
                  <span>Análise</span>
                  <strong>{analysis ? `${analysis.overall_score}/100` : titleize(analysisState.status)}</strong>
                </div>
                <div>
                  <span>Senioridade</span>
                  <strong>{seniority ? titleize(seniority.recommended_track) : titleize(seniorityState.status)}</strong>
                </div>
              </div>

              <div className={`notice ${readiness.canAnalyze ? "notice--success" : "notice--error"}`}>
                {readiness.statusDetail}
              </div>

              {!analysis && analysisState.message ? (
                <div className={`notice ${analysisState.status === "missing" ? "notice--info" : "notice--error"}`}>
                  {analysisState.message}
                </div>
              ) : null}

              {!seniority && seniorityState.message ? (
                <div className={`notice ${seniorityState.status === "missing" ? "notice--info" : "notice--error"}`}>
                  {seniorityState.message}
                </div>
              ) : null}

              {!report && reportState.message ? (
                <div className={`notice ${reportState.status === "locked" ? "notice--info" : "notice--error"}`}>
                  {reportState.message}
                </div>
              ) : null}

              {analysis ? (
                <div className="detail-stack">
                  <strong>Destaques da análise</strong>
                  <p>
                    Estrutura {analysis.structure_score} | Clareza {analysis.clarity_score} | Aderência {analysis.market_fit_score} | Projetos {analysis.project_score}
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
                    Júnior {seniority.junior_score} | Pleno {seniority.mid_score} | Sênior {seniority.senior_score}
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
              title="Selecione um currículo"
              description="Escolha uma versão da sua biblioteca para ver feedback, senioridade e opções premium."
            />
          )}
        </SectionCard>
      </section>
    </AppShell>
  );
}
