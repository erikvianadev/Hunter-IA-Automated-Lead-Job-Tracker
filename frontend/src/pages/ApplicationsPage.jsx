import { useEffect, useState } from "react";

import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { SectionCard } from "../components/SectionCard";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { formatDate, getErrorMessage, titleize } from "../lib/utils";

const APPLICATION_STATUSES = [
  "saved",
  "applied",
  "interview",
  "rejected",
  "offer",
  "archived"
];

export function ApplicationsPage() {
  const { request } = useAuth();
  const [applications, setApplications] = useState([]);
  const [filterStatus, setFilterStatus] = useState("");
  const [editingNotes, setEditingNotes] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [busyAction, setBusyAction] = useState("");

  async function loadApplications() {
    setLoading(true);
    setError("");

    const params = new URLSearchParams({
      ordering: "-updated_at"
    });
    if (filterStatus) {
      params.set("status", filterStatus);
    }

    try {
      const payload = await request(`/hunter/api/applications/?${params.toString()}`);
      const items = payload.results ?? [];
      setApplications(items);
      setEditingNotes(Object.fromEntries(items.map((item) => [item.id, item.notes ?? ""])));
    } catch (requestError) {
      setError(getErrorMessage(requestError, "We could not load your application tracker."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadApplications();
  }, [filterStatus]);

  async function updateApplication(applicationId, payload, successMessage) {
    setBusyAction(`application-${applicationId}`);
    setError("");
    setFeedback("");

    try {
      await request(`/hunter/api/applications/${applicationId}/`, {
        method: "PATCH",
        body: JSON.stringify(payload)
      });
      setFeedback(successMessage);
      await loadApplications();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "We could not update this application."));
    } finally {
      setBusyAction("");
    }
  }

  return (
    <AppShell
      title="Applications"
      subtitle="Keep every application organized so nothing important slips through the cracks."
      actions={
        <button className="button button--ghost" type="button" onClick={loadApplications}>
          Refresh tracker
        </button>
      }
    >
      {error ? <div className="notice notice--error">{error}</div> : null}
      {feedback ? <div className="notice notice--success">{feedback}</div> : null}

      <SectionCard title="Filter by stage" subtitle="Focus on the parts of your pipeline that need attention right now.">
        <div className="action-row">
          <select value={filterStatus} onChange={(event) => setFilterStatus(event.target.value)}>
            <option value="">All stages</option>
            {APPLICATION_STATUSES.map((status) => (
              <option key={status} value={status}>
                {titleize(status)}
              </option>
            ))}
          </select>
        </div>
      </SectionCard>

      <SectionCard title="Application tracker" subtitle="Update each opportunity as conversations, interviews, and offers move forward.">
        {loading ? <div className="loading-panel">Loading your application tracker...</div> : null}
        {!loading && !applications.length ? (
          <EmptyState
            title="No applications tracked yet"
            description="Start tracking from the opportunities page and every next step will show up here."
          />
        ) : null}
        {!loading && applications.length ? (
          <div className="list-stack">
            {applications.map((application) => (
              <article className="list-item" key={application.id}>
                <div>
                  <div className="inline-meta">
                    <strong>{application.job_title}</strong>
                    <StatusBadge value={application.status} />
                  </div>
                  <p>{application.company_name}</p>
                  <p className="muted-copy">
                    Updated {formatDate(application.updated_at)}
                    {application.applied_at ? ` | Applied ${formatDate(application.applied_at)}` : ""}
                  </p>
                </div>

                <div className="application-editor">
                  <label className="field">
                    <span>Stage</span>
                    <select
                      value={application.status}
                      onChange={(event) =>
                        updateApplication(
                          application.id,
                          { status: event.target.value },
                          `Moved to ${titleize(event.target.value)}.`,
                        )
                      }
                      disabled={busyAction === `application-${application.id}`}
                    >
                      {APPLICATION_STATUSES.map((status) => (
                        <option key={status} value={status}>
                          {titleize(status)}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="field">
                    <span>Notes</span>
                    <textarea
                      rows="4"
                      value={editingNotes[application.id] ?? ""}
                      onChange={(event) =>
                        setEditingNotes((previous) => ({
                          ...previous,
                          [application.id]: event.target.value
                        }))
                      }
                    />
                  </label>

                  <button
                    className="button button--secondary"
                    type="button"
                    disabled={busyAction === `application-${application.id}`}
                    onClick={() =>
                      updateApplication(
                        application.id,
                        { notes: editingNotes[application.id] ?? "" },
                        "Application notes saved.",
                      )
                    }
                  >
                    Save notes
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </SectionCard>
    </AppShell>
  );
}
