import { useEffect, useState } from "react";

import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { SectionCard } from "../components/SectionCard";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { formatShortDate, getErrorMessage, titleize } from "../lib/utils";

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
      setError(getErrorMessage(requestError, "Não foi possível carregar seu painel agora."));
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

  return (
    <AppShell
      title="Seu progresso"
      subtitle="Acompanhe currículo, candidaturas e qualidade das vagas em uma visão só."
      actions={
        <button className="button button--ghost" type="button" onClick={loadDashboard}>
          Atualizar visão geral
        </button>
      }
    >
      {error ? <div className="notice notice--error">{error}</div> : null}
      {loading ? <div className="loading-panel">Preparando um retrato atualizado do seu progresso...</div> : null}

      {!loading && dashboard ? (
        <>
          <section className="stats-grid">
            <StatCard
              label="Currículos"
              value={summary.total_resumes}
              helper={summary.active_resume_label ?? "Defina seu currículo principal"}
            />
            <StatCard
              label="Candidaturas"
              value={summary.total_applications}
              helper="Acompanhe cada etapa com clareza"
            />
            <StatCard
              label="Matches"
              value={summary.total_matches}
              helper={
                summary.average_match_score != null
                  ? `Aderência média de ${summary.average_match_score}`
                  : "Ainda sem scores de aderência"
              }
            />
            <StatCard
              label="Vagas salvas"
              value={summary.total_saved_jobs}
              helper={
                summary.top_match_score != null
                  ? `Melhor aderência de ${summary.top_match_score}`
                  : "Salve vagas para revisar depois"
              }
            />
          </section>

          <section className="two-column-grid">
            <SectionCard
              title="Currículo em foco"
              subtitle="A versão que alimenta seus insights e recomendações de aderência."
            >
              {dashboard.active_resume ? (
                <div className="detail-stack">
                  <div className="inline-meta">
                    <strong>{dashboard.active_resume.label || dashboard.active_resume.original_filename}</strong>
                    <StatusBadge value={dashboard.active_resume.parse_status} />
                  </div>
                  <p>{dashboard.active_resume.target_role || "Adicione um cargo-alvo para receber orientações mais precisas."}</p>
                  <p className="muted-copy">
                    Atualizado em {formatShortDate(dashboard.active_resume.updated_at)}
                  </p>
                </div>
              ) : (
                <EmptyState
                  title="Adicione seu primeiro currículo"
                  description="Envie um currículo para começar a receber análises, scores de aderência e insights premium."
                />
              )}
            </SectionCard>

            <SectionCard
              title="Direção do perfil"
              subtitle="Uma leitura rápida de onde seu currículo atual está mais forte."
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

          <section className="two-column-grid">
            <SectionCard title="Próximos passos" subtitle="Ações prioritárias geradas com base no seu perfil atual.">
              {priorityActions.length ? (
                <div className="list-stack">
                  {priorityActions.map((item) => (
                    <article className="list-item" key={`${item.action_type}-${item.priority}`}>
                      <div>
                        <div className="inline-meta">
                          <strong>{item.title}</strong>
                          <StatusBadge value={`priority_${item.priority}`} tone="medium" />
                        </div>
                        <p>{item.detail}</p>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="Tudo sob controle por aqui"
                  description="Seu setup atual já cobre os próximos passos mais importantes."
                />
              )}
            </SectionCard>

            <SectionCard title="Prévia premium" subtitle="Uma amostra das orientações mais profundas disponíveis a partir do seu currículo.">
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
                  title="Nenhuma prévia premium ainda"
                  description="Gere a análise do currículo e a avaliação de senioridade para liberar uma visão mais rica aqui."
                />
              )}
            </SectionCard>
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
