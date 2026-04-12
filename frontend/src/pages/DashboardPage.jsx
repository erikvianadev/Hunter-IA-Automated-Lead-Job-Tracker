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
      setError(getErrorMessage(requestError, "We could not load your dashboard right now."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDashboard();
  }, []);

  return (
    <AppShell
      title="Your progress"
      subtitle="See how your resume, applications, and opportunity quality are moving together."
      actions={
        <button className="button button--ghost" type="button" onClick={loadDashboard}>
          Refresh overview
        </button>
      }
    >
      {error ? <div className="notice notice--error">{error}</div> : null}
      {loading ? <div className="loading-panel">Preparing your latest progress snapshot...</div> : null}

      {!loading && dashboard ? (
        <>
          <section className="stats-grid">
            <StatCard
              label="Resumes"
              value={dashboard.summary.total_resumes}
              helper={dashboard.summary.active_resume_label ?? "Choose your main resume"}
            />
            <StatCard
              label="Applications"
              value={dashboard.summary.total_applications}
              helper="Stay on top of every step"
            />
            <StatCard
              label="Matches"
              value={dashboard.summary.total_matches}
              helper={
                dashboard.summary.average_match_score != null
                  ? `Average fit score ${dashboard.summary.average_match_score}`
                  : "No fit scores yet"
              }
            />
            <StatCard
              label="Saved roles"
              value={dashboard.summary.total_saved_jobs}
              helper={
                dashboard.summary.top_match_score != null
                  ? `Best fit score ${dashboard.summary.top_match_score}`
                  : "Save roles to review later"
              }
            />
          </section>

          <section className="two-column-grid">
            <SectionCard
              title="Current focus resume"
              subtitle="The version powering your insights and job-fit recommendations."
            >
              {dashboard.active_resume ? (
                <div className="detail-stack">
                  <div className="inline-meta">
                    <strong>{dashboard.active_resume.label || dashboard.active_resume.original_filename}</strong>
                    <StatusBadge value={dashboard.active_resume.parse_status} />
                  </div>
                  <p>{dashboard.active_resume.target_role || "Add a target role to sharpen your guidance."}</p>
                  <p className="muted-copy">
                    Updated {formatShortDate(dashboard.active_resume.updated_at)}
                  </p>
                </div>
              ) : (
                <EmptyState
                  title="Add your first resume"
                  description="Upload a resume to start getting resume feedback, fit scores, and premium insights."
                />
              )}
            </SectionCard>

            <SectionCard
              title="Profile direction"
              subtitle="A quick read on where your current resume is strongest."
            >
              <div className="insight-list">
                <div>
                  <span>Best-fit level</span>
                  <strong>{titleize(dashboard.profile_insights.recommended_track)}</strong>
                </div>
                <div>
                  <span>Momentum</span>
                  <strong>{titleize(dashboard.profile_insights.competitiveness_level)}</strong>
                </div>
                <div>
                  <span>Biggest gap</span>
                  <strong>{titleize(dashboard.profile_insights.top_gap_area)}</strong>
                </div>
              </div>
            </SectionCard>
          </section>

          <section className="two-column-grid">
            <SectionCard title="What to do next" subtitle="Clear next steps generated from your current profile.">
              {dashboard.priority_actions.length ? (
                <div className="list-stack">
                  {dashboard.priority_actions.map((item) => (
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
                  title="You are in a good place"
                  description="Your current setup already covers the most important next steps."
                />
              )}
            </SectionCard>

            <SectionCard title="Premium insight preview" subtitle="A preview of the deeper guidance available from your resume data.">
              {dashboard.resume_report_preview ? (
                <div className="detail-stack">
                  <p>{dashboard.resume_report_preview.executive_summary}</p>
                  <div className="insight-list">
                    <div>
                      <span>Main improvement area</span>
                      <strong>{dashboard.resume_report_preview.top_gap ?? "-"}</strong>
                    </div>
                    <div>
                      <span>Best next move</span>
                      <strong>{dashboard.resume_report_preview.top_priority_action ?? "-"}</strong>
                    </div>
                    <div>
                      <span>Average job fit</span>
                      <strong>{dashboard.resume_report_preview.average_match_score ?? "-"}</strong>
                    </div>
                  </div>
                </div>
              ) : (
                <EmptyState
                  title="No premium preview yet"
                  description="Generate resume analysis and seniority guidance to unlock a stronger preview here."
                />
              )}
            </SectionCard>
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
