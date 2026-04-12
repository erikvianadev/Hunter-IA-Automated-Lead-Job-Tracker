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
      statusTitle: "Select a resume",
      statusDetail: "Choose one resume to see what is available."
    };
  }

  const parseStatus = resume.parse_status;
  const extractedText = (resume.extracted_text || "").trim();
  const hasUsableText = extractedText.length >= 40 && extractedText.split(/\s+/).length >= 8;
  const parseReady = READY_PARSE_STATUSES.has(parseStatus);

  if (!parseReady || !hasUsableText) {
    const detailByStatus = {
      pending: "This resume is still being prepared. Wait for parsing to finish before requesting insights.",
      processing: "This resume is still being processed. Insights will unlock once the text is ready.",
      failed: "We could not read enough content from this file. Upload a cleaner PDF or DOCX to continue.",
      empty_text: "The file uploaded, but no usable text was found. Try a text-based PDF or DOCX export.",
      unsupported_structure: "The file structure could not be read well enough for insight generation. Try a clearer export."
    };

    return {
      canAnalyze: false,
      canAssess: false,
      parseTone: "low",
      statusTitle: "Resume not ready for insights",
      statusDetail:
        detailByStatus[parseStatus] ??
        "This resume still needs usable extracted text before analysis and seniority guidance can run.",
      hasUsableText,
      parseReady
    };
  }

  return {
    canAnalyze: true,
    canAssess: true,
    parseTone: "good",
    statusTitle: "Ready for analysis",
    statusDetail: "This resume has enough readable text for resume review and seniority guidance.",
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
      ? "Resume review has not been generated yet."
      : "Career level guidance has not been generated yet.";
  }

  if (error.status === 400) {
    return getErrorMessage(
      error,
      kind === "analysis"
        ? "This resume needs more readable text before we can review it."
        : "This resume needs enough readable content before we can estimate career level.",
    );
  }

  if (error.status === 403) {
    return "Premium insight is available on paid plans only.";
  }

  return getErrorMessage(error, "We could not load this insight right now.");
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
      setError(getErrorMessage(requestError, "We could not load your resumes right now."));
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
      setAnalysisState({ status: "ready", message: "Resume review is ready." });
    } else {
      setAnalysis(null);
      setAnalysisState({
        status: analysisResult.reason?.status === 404 ? "missing" : "blocked",
        message: getInsightStateMessage("analysis", analysisResult.reason)
      });
    }

    if (seniorityResult.status === "fulfilled") {
      setSeniority(seniorityResult.value);
      setSeniorityState({ status: "ready", message: "Career level guidance is ready." });
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
      setError("Choose a PDF or DOCX resume before continuing.");
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
      setFeedback(`"${payload.label || payload.original_filename}" is ready for review.`);
      setForm({
        file: null,
        label: "",
        target_role: ""
      });
      await loadResumes(false);
      setSelectedResumeId(payload.id);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "We could not upload that resume."));
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
      setError(getErrorMessage(requestError, "This action could not be completed."));
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
    <AppShell title="Resumes" subtitle="Keep improving your resume and compare versions when you want deeper insight.">
      {error ? <div className="notice notice--error">{error}</div> : null}
      {feedback ? <div className="notice notice--success">{feedback}</div> : null}

      <section className="two-column-grid two-column-grid--wide-left">
        <SectionCard title="Add a new resume" subtitle="Upload a fresh version to review, score, and use for job matching.">
          <form className="stack" onSubmit={handleUpload}>
            <label className="field">
              <span>Resume file</span>
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
              <span>Version name</span>
              <input
                value={form.label}
                onChange={(event) => setForm((previous) => ({ ...previous, label: event.target.value }))}
                placeholder="Backend resume v3"
              />
            </label>

            <label className="field">
              <span>Target role</span>
              <input
                value={form.target_role}
                onChange={(event) =>
                  setForm((previous) => ({ ...previous, target_role: event.target.value }))
                }
                placeholder="Backend Engineer"
              />
            </label>

            <button className="button button--primary" type="submit" disabled={busyAction === "upload"}>
              {busyAction === "upload" ? "Uploading your resume..." : "Upload resume"}
            </button>
          </form>
        </SectionCard>

        <SectionCard
          title="Premium comparison"
          subtitle="Compare two or three resume versions to see which one tells the strongest story."
          actions={
            <button
              className="button button--secondary"
              type="button"
              disabled={selectedIds.length < 2 || busyAction === "compare"}
              onClick={() =>
                runResumeAction("compare", async () => {
                  const payload = await request(`/hunter/api/resumes/compare/?ids=${selectedIds.join(",")}`);
                  setComparison(payload);
                  setFeedback("Your resume comparison is ready.");
                })
              }
            >
              {busyAction === "compare" ? "Comparing versions..." : "Compare selected"}
            </button>
          }
        >
          <p className="muted-copy">
            Choose two or three resumes below. Premium access still comes from the backend plan rules.
          </p>
          <div className="selection-pills">
            {selectedIds.length
              ? selectedIds.map((id) => <span key={id}>Resume #{id}</span>)
              : <span>Select versions to compare</span>}
          </div>
          {comparison ? (
            <div className="detail-stack">
              <strong>{comparison.comparison_summary}</strong>
              <p>Likely target role: {comparison.likely_target_role ?? "-"}</p>
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
        <SectionCard title="Your resume library" subtitle="Pick your main version and keep older iterations for comparison.">
          {loading ? <div className="loading-panel">Loading your resume library...</div> : null}
          {!loading && !resumes.length ? (
            <EmptyState
              title="No resumes here yet"
              description="Upload your first resume to start improving it and unlocking premium insights."
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
                    <p>{resume.target_role || "No target role yet"}</p>
                    <p className="muted-copy">Updated {formatShortDate(resume.updated_at)}</p>
                  </div>

                  <div className="action-row">
                    <label className="checkbox-pill">
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(resume.id)}
                        onChange={() => toggleCompareSelection(resume.id)}
                      />
                      Compare
                    </label>
                    <button
                      className="button button--ghost"
                      type="button"
                      onClick={() =>
                        runResumeAction(`activate-${resume.id}`, async () => {
                          await request(`/hunter/api/resumes/${resume.id}/activate/`, { method: "POST" });
                          await loadResumes();
                          setFeedback("This is now your main resume.");
                        })
                      }
                    >
                      Make primary
                    </button>
                    <button
                      className="button button--ghost"
                      type="button"
                      onClick={() =>
                        runResumeAction(`delete-${resume.id}`, async () => {
                          if (!window.confirm(`Delete ${resume.label || resume.original_filename}?`)) {
                            return;
                          }
                          await request(`/hunter/api/resumes/${resume.id}/`, { method: "DELETE" });
                          await loadResumes(false);
                          setFeedback("Resume removed.");
                        })
                      }
                    >
                      Delete
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : null}
        </SectionCard>

        <SectionCard
          title="Resume insights"
          subtitle="See what is ready now, what still needs text cleanup, and what is locked behind premium access."
          actions={
            selectedResume ? (
              <div className="action-row">
                <button
                  className="button button--secondary"
                  type="button"
                  disabled={!readiness.canAnalyze || busyAction === "analyze"}
                  title={!readiness.canAnalyze ? readiness.statusDetail : "Generate resume review"}
                  onClick={() =>
                    runResumeAction("analyze", async () => {
                      const payload = await request(`/hunter/api/resumes/${selectedResume.id}/analyze/`, {
                        method: "POST"
                      });
                      setAnalysis(payload);
                      setAnalysisState({ status: "ready", message: "Resume review is ready." });
                      await loadResumes();
                      setFeedback("Resume review is ready.");
                    })
                  }
                >
                  {busyAction === "analyze" ? "Reviewing..." : "Review resume"}
                </button>
                <button
                  className="button button--secondary"
                  type="button"
                  disabled={!readiness.canAssess || busyAction === "seniority"}
                  title={!readiness.canAssess ? readiness.statusDetail : "Generate career level guidance"}
                  onClick={() =>
                    runResumeAction("seniority", async () => {
                      const payload = await request(`/hunter/api/resumes/${selectedResume.id}/assess-seniority/`, {
                        method: "POST"
                      });
                      setSeniority(payload);
                      setSeniorityState({ status: "ready", message: "Career level guidance is ready." });
                      setFeedback("Career level guidance is ready.");
                    })
                  }
                >
                  {busyAction === "seniority" ? "Assessing..." : "Assess fit"}
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
                        setReportState({ status: "ready", message: "Premium resume insight unlocked." });
                        setFeedback("Premium resume insight unlocked.");
                      } catch (requestError) {
                        setReport(null);
                        setReportState({
                          status: requestError.status === 403 ? "locked" : "blocked",
                          message:
                            requestError.status === 403
                              ? "Premium insight is available on paid plans only."
                              : getErrorMessage(requestError, "We could not open the premium report.")
                        });
                        throw requestError;
                      }
                    })
                  }
                >
                  {busyAction === "report" ? "Opening report..." : "Open premium insight"}
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
                  Open uploaded resume
                </a>
              ) : null}

              <p>{selectedResume.target_role || "Add a target role to sharpen your feedback."}</p>

              <div className="insight-list">
                <div>
                  <span>Resume readiness</span>
                  <strong>{readiness.statusTitle}</strong>
                </div>
                <div>
                  <span>Resume review</span>
                  <strong>{analysis ? `${analysis.overall_score}/100` : titleize(analysisState.status)}</strong>
                </div>
                <div>
                  <span>Career level</span>
                  <strong>{seniority ? titleize(seniority.recommended_track) : titleize(seniorityState.status)}</strong>
                </div>
              </div>

              <div className={`notice ${readiness.canAnalyze ? "notice--success" : "notice--error"}`}>
                {readiness.statusDetail}
              </div>

              {!analysis && analysisState.message ? (
                <div className={`notice ${analysisState.status === "missing" ? "notice--success" : "notice--error"}`}>
                  {analysisState.message}
                </div>
              ) : null}

              {!seniority && seniorityState.message ? (
                <div className={`notice ${seniorityState.status === "missing" ? "notice--success" : "notice--error"}`}>
                  {seniorityState.message}
                </div>
              ) : null}

              {!report && reportState.message ? (
                <div className={`notice ${reportState.status === "locked" ? "notice--success" : "notice--error"}`}>
                  {reportState.message}
                </div>
              ) : null}

              {analysis ? (
                <div className="detail-stack">
                  <strong>Resume review highlights</strong>
                  <p>
                    Structure {analysis.structure_score} | Clarity {analysis.clarity_score} | Market fit {analysis.market_fit_score} | Projects {analysis.project_score}
                  </p>
                  <ul className="plain-list">
                    {analysis.recommendations.map((item, index) => (
                      <li key={`${item}-${index}`}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {seniority ? (
                <div className="detail-stack">
                  <strong>Career level guidance</strong>
                  <p>{titleize(seniority.recommended_track)}</p>
                  <p className="muted-copy">
                    Junior {seniority.junior_score} | Mid {seniority.mid_score} | Senior {seniority.senior_score}
                  </p>
                </div>
              ) : null}

              {report ? (
                <div className="detail-stack">
                  <strong>Premium insight</strong>
                  <p>{report.executive_summary}</p>
                  <ul className="plain-list">
                    {report.priority_actions.map((item, index) => (
                      <li key={`${item}-${index}`}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : (
            <EmptyState
              title="Choose a resume"
              description="Select one version from your library to view feedback and premium insight options."
            />
          )}
        </SectionCard>
      </section>
    </AppShell>
  );
}
