import { useEffect, useState } from "react";

import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { SectionCard } from "../components/SectionCard";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { getResumeParsePresentation } from "../lib/presentation";
import { formatShortDate, getErrorMessage, titleize } from "../lib/utils";

function hasResumeUsableText(resume) {
  const extractedText = (resume?.extracted_text || "").trim();
  return extractedText.length >= 40 && extractedText.split(/\s+/).length >= 8;
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
      setError(getErrorMessage(requestError, "Nao foi possivel carregar sua visao geral agora."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDashboard();
  }, []);

  const summary = dashboard?.summary ?? {};
  const profileInsights = dashboard?.profile_insights ?? {};
  const priorityActions = dashboard?.priority_actions ?? [];
  const preview = dashboard?.resume_report_preview;
  const activeResumePresentation = dashboard?.active_resume
    ? getResumeParsePresentation(dashboard.active_resume.parse_status, {
      hasUsableText: hasResumeUsableText(dashboard.active_resume)
    })
    : null;

  return (
    <AppShell
      title="Seu progresso"
      subtitle="Acompanhe curriculo, candidaturas e qualidade das vagas em uma visao unica e facil de agir."
      actions={
        <button className="button button--ghost" type="button" onClick={loadDashboard}>
          Atualizar visao geral
        </button>
      }
    >
      {error ? <div className="notice notice--blocked">{error}</div> : null}
      {loading ? <div className="loading-panel">Preparando um retrato atualizado do seu progresso...</div> : null}

      {!loading && dashboard ? (
        <>
          <section className="stats-grid">
            <StatCard
              label="Curriculos"
              value={summary.total_resumes}
              helper={summary.active_resume_label ?? "Defina um curriculo principal para guiar os insights"}
            />
            <StatCard
              label="Candidaturas"
              value={summary.total_applications}
              helper="Acompanhe cada etapa com mais clareza"
            />
            <StatCard
              label="Matches"
              value={summary.total_matches}
              helper={
                summary.average_match_score != null
                  ? `Aderencia media de ${summary.average_match_score}`
                  : "Atualize um match para enxergar aderencia media"
              }
            />
            <StatCard
              label="Vagas salvas"
              value={summary.total_saved_jobs}
              helper={
                summary.top_match_score != null
                  ? `Melhor aderencia de ${summary.top_match_score}`
                  : "Salve vagas para montar sua shortlist"
              }
            />
          </section>

          <section className="two-column-grid">
            <SectionCard
              title="Curriculo em foco"
              subtitle="A versao principal que alimenta seus insights e recomendacoes de aderencia."
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
                  <p>{dashboard.active_resume.target_role || "Adicione um cargo-alvo para receber orientacoes mais precisas."}</p>
                  <p className="muted-copy">Atualizado em {formatShortDate(dashboard.active_resume.updated_at)}</p>
                  <div className={`notice notice--${activeResumePresentation.tone === "good" ? "success" : activeResumePresentation.tone === "warning" ? "warning" : activeResumePresentation.tone === "blocked" ? "blocked" : "info"}`}>
                    <strong>{activeResumePresentation.title}</strong>
                    <p>{activeResumePresentation.description}</p>
                    <p>{activeResumePresentation.nextStep}</p>
                  </div>
                </div>
              ) : (
                <EmptyState
                  title="Adicione seu primeiro curriculo"
                  description="Envie um curriculo para comecar a receber analises, scores de aderencia e orientacoes mais profundas."
                />
              )}
            </SectionCard>

            <SectionCard
              title="Direcao do perfil"
              subtitle="Uma leitura rapida de onde seu curriculo atual esta mais forte hoje."
            >
              <div className="insight-list">
                <div>
                  <span>Nivel mais aderente</span>
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

          <section className="two-column-grid">
            <SectionCard title="Proximos passos" subtitle="Acoes prioritarias para manter seu progresso visivel e consistente.">
              {priorityActions.length ? (
                <div className="list-stack">
                  {priorityActions.map((item) => (
                    <article className="list-item" key={`${item.action_type}-${item.priority}`}>
                      <div>
                        <div className="inline-meta">
                          <strong>{item.title}</strong>
                          <StatusBadge value={`priority_${item.priority}`} tone="warning" />
                        </div>
                        <p>{item.detail}</p>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="Tudo sob controle por aqui"
                  description="Seu setup atual ja cobre os proximos passos mais importantes."
                />
              )}
            </SectionCard>

            <SectionCard title="Previa premium" subtitle="Uma amostra do tipo de orientacao que voce libera com um diagnostico mais profundo.">
              {preview ? (
                <div className="detail-stack">
                  <p>{preview.executive_summary}</p>
                  <div className="insight-list">
                    <div>
                      <span>Area principal de melhoria</span>
                      <strong>{preview.top_gap ?? "-"}</strong>
                    </div>
                    <div>
                      <span>Melhor proximo passo</span>
                      <strong>{preview.top_priority_action ?? "-"}</strong>
                    </div>
                    <div>
                      <span>Aderencia media</span>
                      <strong>{preview.average_match_score ?? "-"}</strong>
                    </div>
                  </div>
                </div>
              ) : (
                <EmptyState
                  title="Nenhuma previa premium ainda"
                  description="Gere a analise do curriculo e a leitura de senioridade para liberar uma visao mais rica aqui."
                />
              )}
            </SectionCard>
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
