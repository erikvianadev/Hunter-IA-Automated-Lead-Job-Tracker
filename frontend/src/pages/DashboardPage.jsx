import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { SectionCard } from "../components/SectionCard";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { getActivationStepPresentation } from "../lib/activation";
import { getResumeParsePresentation } from "../lib/presentation";
import { formatShortDate, getErrorMessage, titleize } from "../lib/utils";

function hasResumeUsableText(resume) {
  const extractedText = (resume?.extracted_text || "").trim();
  return extractedText.length >= 40 && extractedText.split(/\s+/).length >= 8;
}

function getPrioritySourceLabel(source) {
  const labels = {
    application: "Candidatura",
    job: "Vaga",
    jobs: "Vagas",
    resume: "Currículo",
    resume_gap: "Currículo",
    setup: "Setup"
  };

  return labels[source] ?? "Prioridade";
}

function getPrioritySourceTone(source) {
  if (source === "application") return "warning";
  if (source === "job" || source === "jobs") return "medium";
  if (source === "resume" || source === "resume_gap") return "good";
  return "muted";
}

export function DashboardPage() {
  const { request } = useAuth();
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadDashboard() {
    setLoading(true);
    setError("");

    try {
      const payload = await request("/hunter/api/resumes/dashboard/");
      setDashboard(payload);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Não foi possível carregar sua visão geral agora."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDashboard();
  }, []);

  const summary = dashboard?.summary ?? {};
  const profileInsights = dashboard?.profile_insights ?? {};
  const weeklyControl = dashboard?.weekly_control ?? {};
  const mainPriority = weeklyControl.main_priority;
  const secondaryPriorities = weeklyControl.secondary_priorities ?? [];
  const applicationsNeedingAttention = weeklyControl.applications_needing_attention ?? [];
  const jobsToActNow = weeklyControl.jobs_to_act_now ?? [];
  const resumeGaps = weeklyControl.resume_gaps ?? [];
  const activation = dashboard?.activation;
  const activationChecklist = activation?.checklist ?? [];
  const nextBestAction = activation?.next_best_action;
  const preview = dashboard?.resume_report_preview;
  const activeResumePresentation = dashboard?.active_resume
    ? getResumeParsePresentation(dashboard.active_resume.parse_status, {
      hasUsableText: hasResumeUsableText(dashboard.active_resume)
    })
    : null;

  return (
    <AppShell
      title="Seu progresso"
      subtitle="Acompanhe currículo, candidaturas e qualidade das vagas em uma visão única e fácil de agir."
      actions={
        <button className="button button--ghost" type="button" onClick={loadDashboard}>
          Atualizar visão geral
        </button>
      }
    >
      {error ? <div className="notice notice--blocked">{error}</div> : null}
      {loading ? <div className="loading-panel">Preparando um retrato atualizado do seu progresso...</div> : null}

      {!loading && dashboard ? (
        <>
          <section className="stats-grid">
            <StatCard
              label="Currículos"
              value={summary.total_resumes}
              helper={
                summary.total_resumes
                  ? summary.active_resume_label ?? "Defina um currículo principal para guiar os insights"
                  : "Comece enviando seu primeiro currículo para liberar o fluxo principal."
              }
            />
            <StatCard
              label="Candidaturas"
              value={summary.total_applications}
              helper={
                summary.total_applications
                  ? "Acompanhe cada etapa com mais clareza"
                  : "Quando você marcar vagas como aplicadas, seu pipeline aparece aqui."
              }
            />
            <StatCard
              label="Matches"
              value={summary.total_matches}
              helper={
                summary.average_match_score != null
                  ? `Aderência média de ${summary.average_match_score}`
                  : "Gere aderência com vagas para descobrir onde vale focar."
              }
            />
            <StatCard
              label="Vagas salvas"
              value={summary.total_saved_jobs}
              helper={
                summary.top_match_score != null
                  ? `Melhor aderência de ${summary.top_match_score}`
                  : "Monte sua shortlist salvando vagas com potencial."
              }
            />
          </section>

          {mainPriority ? (
            <section className="weekly-control-grid">
              <article className="weekly-priority-hero">
                <div className="inline-meta">
                  <StatusBadge value="priority_1" label="Prioridade 1 da semana" tone="warning" />
                  <StatusBadge
                    value={mainPriority.source}
                    label={getPrioritySourceLabel(mainPriority.source)}
                    tone={getPrioritySourceTone(mainPriority.source)}
                  />
                </div>
                <div>
                  <span className="weekly-priority-hero__eyebrow">{weeklyControl.headline ?? "Mission Control semanal"}</span>
                  <h2>{mainPriority.title}</h2>
                  <p>{weeklyControl.summary}</p>
                </div>
                <div className="weekly-priority-hero__reason">
                  <div>
                    <span>Por que agora</span>
                    <p>{mainPriority.reason}</p>
                  </div>
                  <div>
                    <span>Ação recomendada</span>
                    <p>{mainPriority.action}</p>
                  </div>
                </div>
                <Link className="button button--primary" to={mainPriority.cta_href}>
                  {mainPriority.cta_label}
                </Link>
              </article>

              <SectionCard
                title="Fila executiva"
                subtitle="O que fazer depois da prioridade 1, em ordem de utilidade prática."
              >
                {secondaryPriorities.length ? (
                  <div className="weekly-secondary-list">
                    {secondaryPriorities.map((priority) => (
                      <article className="weekly-secondary-item" key={`${priority.source}-${priority.source_id ?? priority.rank}`}>
                        <div className="inline-meta">
                          <StatusBadge
                            value={`priority_${Math.min(priority.rank, 3)}`}
                            label={`Prioridade ${priority.rank}`}
                            tone={priority.rank === 2 ? "medium" : "muted"}
                          />
                          <StatusBadge
                            value={priority.source}
                            label={getPrioritySourceLabel(priority.source)}
                            tone={getPrioritySourceTone(priority.source)}
                          />
                        </div>
                        <strong>{priority.title}</strong>
                        <p>{priority.reason}</p>
                        <p className="muted-copy">{priority.action}</p>
                      </article>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    eyebrow="Sem fila secundária"
                    title="A semana está concentrada em uma ação principal"
                    description="Não há sinais suficientes para criar outras prioridades sem aumentar ruído."
                    nextStep="Resolva a prioridade 1 e atualize o painel para recalcular a fila."
                  />
                )}
              </SectionCard>
            </section>
          ) : null}

          <section className="two-column-grid two-column-grid--wide-left">
            <SectionCard
              title="Candidaturas em atenção"
              subtitle="Entram aqui apenas etapas quentes, falta de atualização ou contexto incompleto."
              actions={<Link className="button button--ghost" to="/applications">Ver candidaturas</Link>}
            >
              {applicationsNeedingAttention.length ? (
                <div className="list-stack">
                  {applicationsNeedingAttention.map((application) => (
                    <article className="list-item application-attention-item" key={application.application_id}>
                      <div>
                        <div className="inline-meta">
                          <StatusBadge value={`priority_${Math.min(application.rank, 3)}`} label={`#${application.rank}`} tone={application.rank === 1 ? "warning" : "medium"} />
                          <StatusBadge value={application.status} label={application.status_label} />
                        </div>
                        <strong>{application.title}</strong>
                        <p>{application.company_name}</p>
                        <p>{application.reason}</p>
                        <p className="muted-copy">{application.suggested_action}</p>
                        {application.objective_criteria?.length ? (
                          <div className="selection-pills">
                            {application.objective_criteria.map((criterion) => (
                              <span key={criterion}>{criterion}</span>
                            ))}
                          </div>
                        ) : null}
                      </div>
                      <span className="muted-copy">Atualizada em {formatShortDate(application.updated_at)}</span>
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState
                  eyebrow="Sem alerta operacional"
                  title="Nenhuma candidatura pede foco imediato"
                  description="Não encontramos etapa quente, atraso relevante ou falta crítica de contexto no pipeline atual."
                  nextStep="Use esta folga para agir nas vagas com melhor match ou melhorar o currículo ativo."
                />
              )}
            </SectionCard>

            <SectionCard
              title="Vagas para agir agora"
              subtitle="Matches fortes ainda sem candidatura em andamento."
              actions={<Link className="button button--ghost" to="/jobs">Abrir vagas</Link>}
            >
              {jobsToActNow.length ? (
                <div className="list-stack">
                  {jobsToActNow.map((job) => (
                    <article className="list-item job-action-item" key={job.job_id}>
                      <div>
                        <div className="inline-meta">
                          <StatusBadge value={`priority_${Math.min(job.rank, 3)}`} label={`#${job.rank}`} tone={job.rank === 1 ? "warning" : "medium"} />
                          <StatusBadge value="ready" label={`${job.match_score}/100 match`} tone={job.match_score >= 85 ? "good" : "medium"} />
                        </div>
                        <strong>{job.title}</strong>
                        <p>{job.company_name}{job.location ? ` - ${job.location}` : ""}</p>
                        <p>{job.reason}</p>
                        <p className="muted-copy">{job.suggested_action}</p>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState
                  eyebrow="Sem vaga acionável"
                  title="Nenhum match forte parado agora"
                  description="As vagas atuais não passaram do corte de ação imediata ou já estão no pipeline."
                  nextStep="Busque novas vagas ou atualize matches depois de ajustar o currículo."
                />
              )}
            </SectionCard>
          </section>

          <SectionCard
            title="Lacunas do currículo que importam agora"
            subtitle="Apenas pontos com impacto provável nas próximas candidaturas ou vagas fortes."
            actions={<Link className="button button--ghost" to="/resumes">Abrir currículos</Link>}
          >
            {resumeGaps.length ? (
              <div className="priority-action-grid">
                {resumeGaps.map((gap) => (
                  <article className="priority-card" key={gap.gap_type}>
                    <div className="inline-meta">
                      <StatusBadge value={`priority_${Math.min(gap.rank, 3)}`} label={`#${gap.rank}`} tone={gap.rank === 1 ? "warning" : "muted"} />
                    </div>
                    <strong>{gap.title}</strong>
                    <p>{gap.impact}</p>
                    <p className="muted-copy">{gap.guidance}</p>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState
                eyebrow="Sem lacuna elevada"
                title="Nada do currículo precisa subir para o topo agora"
                description="Não há análise pronta ou nenhuma lacuna atual superou o corte de impacto semanal."
                nextStep="Use as candidaturas e vagas acionáveis como foco principal da semana."
              />
            )}
          </SectionCard>

          {activation ? (
            <section className="two-column-grid">
              <SectionCard
                title="Ativação inicial"
                subtitle="Um caminho curto para chegar ao primeiro valor com clareza."
                actions={
                  nextBestAction ? (
                    <Link className="button button--primary" to={nextBestAction.cta_href}>
                      {nextBestAction.cta_label}
                    </Link>
                  ) : null
                }
              >
                <div className="activation-summary">
                  <div className="inline-meta">
                    <strong>{activation.headline}</strong>
                    <StatusBadge
                      value={`activation-${activation.progress_percent}`}
                      label={`${activation.completed_steps}/${activation.total_steps} etapas`}
                      tone={activation.is_complete ? "good" : "warning"}
                    />
                  </div>
                  <p>{activation.summary}</p>
                  <div className="activation-progress" aria-hidden="true">
                    <span style={{ width: `${activation.progress_percent}%` }} />
                  </div>
                  <p className="muted-copy">{activation.progress_percent}% do caminho inicial concluído.</p>
                  {nextBestAction ? (
                    <div className="notice notice--info">
                      <strong>{nextBestAction.title}</strong>
                      <p>{nextBestAction.detail}</p>
                    </div>
                  ) : null}
                </div>
              </SectionCard>

              <SectionCard
                title="Checklist de ativação"
                subtitle="Veja o que já foi destravado e o que falta para consolidar seu fluxo inicial."
              >
                <div className="activation-checklist">
                  {activationChecklist.map((step) => {
                    const stepPresentation = getActivationStepPresentation(step);

                    return (
                      <article
                        className={step.completed ? "activation-checklist__item is-complete" : "activation-checklist__item"}
                        key={step.id}
                      >
                        <div>
                          <div className="inline-meta">
                            <strong>{step.title}</strong>
                            <StatusBadge
                              value={step.id}
                              label={stepPresentation.label}
                              tone={stepPresentation.tone}
                            />
                          </div>
                          <p>{step.detail}</p>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </SectionCard>
            </section>
          ) : null}

          <section className="two-column-grid">
            <SectionCard
              title="Currículo em foco"
              subtitle="A versão principal que alimenta seus insights e recomendações de aderência."
            >
              {dashboard.active_resume ? (
                <div className="detail-stack">
                  <div className="inline-meta">
                    <strong>{dashboard.active_resume.label || dashboard.active_resume.original_filename}</strong>
                    <StatusBadge
                      value={dashboard.active_resume.parse_status}
                      label={activeResumePresentation.label}
                      tone={activeResumePresentation.tone}
                    />
                  </div>
                  <p>{dashboard.active_resume.target_role || "Adicione um cargo-alvo para receber orientações mais precisas."}</p>
                  <p className="muted-copy">Atualizado em {formatShortDate(dashboard.active_resume.updated_at)}</p>
                  <div className={`notice notice--${activeResumePresentation.tone === "good" ? "success" : activeResumePresentation.tone === "warning" ? "warning" : activeResumePresentation.tone === "blocked" ? "blocked" : "info"}`}>
                    <strong>{activeResumePresentation.title}</strong>
                    <p>{activeResumePresentation.description}</p>
                    <p>{activeResumePresentation.nextStep}</p>
                  </div>
                </div>
              ) : (
                <EmptyState
                  eyebrow="Sem base para os insights"
                  title="Adicione seu primeiro currículo"
                  description="Sem um currículo principal, o produto ainda não consegue gerar análise, senioridade ou aderência com vagas."
                  nextStep="Abra Currículos, envie uma versão em PDF ou DOCX e use esse arquivo como base do seu fluxo inicial."
                  action={<Link className="button button--secondary" to="/resumes">Enviar currículo</Link>}
                />
              )}
            </SectionCard>

            <SectionCard
              title="Direção do perfil"
              subtitle="Uma leitura rápida de onde seu currículo atual está mais forte hoje."
            >
              <div className="insight-list">
                <div>
                  <span>Nível mais aderente</span>
                  <strong>{titleize(profileInsights.recommended_track)}</strong>
                </div>
                <div>
                  <span>Momento atual</span>
                  <strong>{titleize(profileInsights.competitiveness_level)}</strong>
                </div>
                <div>
                  <span>Principal lacuna</span>
                  <strong>{titleize(profileInsights.top_gap_area)}</strong>
                </div>
              </div>
            </SectionCard>
          </section>

          <section>
            <SectionCard title="Prévia premium" subtitle="Uma amostra do tipo de orientação que você libera com um diagnóstico mais profundo.">
              {preview ? (
                <div className="detail-stack">
                  <p>{preview.executive_summary}</p>
                  <div className="insight-list">
                    <div>
                      <span>Área principal de melhoria</span>
                      <strong>{preview.top_gap ?? "-"}</strong>
                    </div>
                    <div>
                      <span>Melhor próximo passo</span>
                      <strong>{preview.top_priority_action ?? "-"}</strong>
                    </div>
                    <div>
                      <span>Aderência média</span>
                      <strong>{preview.average_match_score ?? "-"}</strong>
                    </div>
                  </div>
                </div>
              ) : (
                <EmptyState
                  eyebrow="Insight ainda indisponível"
                  title="Nenhuma prévia premium ainda"
                  description="A prévia premium aparece quando seu currículo já passou por análise e leitura de senioridade."
                  nextStep={
                    dashboard.active_resume
                      ? "Abra Currículos e gere a análise e a senioridade da versão principal para liberar uma orientação mais rica."
                      : "Envie um currículo primeiro e depois gere análise e senioridade para desbloquear esta camada."
                  }
                  action={
                    <Link className="button button--ghost" to="/resumes">
                      {dashboard.active_resume ? "Abrir currículos" : "Enviar currículo"}
                    </Link>
                  }
                />
              )}
            </SectionCard>
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
