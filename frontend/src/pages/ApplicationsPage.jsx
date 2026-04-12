import { useEffect, useMemo, useState } from "react";

import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { SectionCard } from "../components/SectionCard";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { formatDate, formatRelativeDate, formatShortDate, getErrorMessage, titleize } from "../lib/utils";

const APPLICATION_STATUSES = ["saved", "applied", "interview", "rejected", "offer", "archived"];
const ORDER_OPTIONS = [
  { value: "-updated_at", label: "Recently updated" },
  { value: "-applied_at", label: "Recently applied" },
  { value: "updated_at", label: "Oldest updates first" },
  { value: "applied_at", label: "Oldest applied first" }
];

const QUICK_ACTIONS = {
  saved: [
    { status: "applied", label: "Mark applied", variant: "secondary" },
    { status: "archived", label: "Archive", variant: "ghost" }
  ],
  applied: [
    { status: "interview", label: "Move to interview", variant: "secondary" },
    { status: "rejected", label: "Mark rejected", variant: "ghost" },
    { status: "archived", label: "Archive", variant: "ghost" }
  ],
  interview: [
    { status: "offer", label: "Mark offer", variant: "secondary" },
    { status: "rejected", label: "Mark rejected", variant: "ghost" },
    { status: "archived", label: "Archive", variant: "ghost" }
  ],
  rejected: [
    { status: "archived", label: "Archive", variant: "ghost" },
    { status: "saved", label: "Move back to saved", variant: "ghost" }
  ],
  offer: [
    { status: "archived", label: "Archive", variant: "ghost" },
    { status: "interview", label: "Move back to interview", variant: "ghost" }
  ],
  archived: [
    { status: "saved", label: "Restore to saved", variant: "secondary" },
    { status: "applied", label: "Restore to applied", variant: "ghost" }
  ]
};

function getScoreTone(score) {
  if (score >= 80) return "good";
  if (score >= 60) return "medium";
  return "low";
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
    "Open the application detail to capture notes, stage changes, and follow-up context.",
  );
}

function buildTrackerSummary(count, shown, filters) {
  const parts = [];
  if (filters.search) parts.push(`keyword "${filters.search}"`);
  if (filters.company_name) parts.push(`company "${filters.company_name}"`);
  if (filters.status) parts.push(`${titleize(filters.status)} stage`);

  return parts.length
    ? `Showing ${shown} tracked applications out of ${count} matching ${parts.join(", ")}.`
    : `Showing ${shown} tracked applications out of ${count} in your pipeline.`;
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

export function ApplicationsPage() {
  const { request } = useAuth();
  const [applications, setApplications] = useState([]);
  const [selectedApplicationId, setSelectedApplicationId] = useState(null);
  const [filters, setFilters] = useState({ status: "", search: "", company_name: "", ordering: "-updated_at" });
  const [appliedFilters, setAppliedFilters] = useState({ status: "", search: "", company_name: "", ordering: "-updated_at" });
  const [editingNotes, setEditingNotes] = useState({});
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [busyAction, setBusyAction] = useState("");

  const selectedApplication = useMemo(
    () => applications.find((application) => application.id === selectedApplicationId) ?? null,
    [applications, selectedApplicationId],
  );
  const statusCounts = useMemo(() => getStatusCounts(applications), [applications]);
  const trackerSummary = useMemo(
    () => buildTrackerSummary(totalCount, applications.length, appliedFilters),
    [applications.length, appliedFilters, totalCount],
  );
  const notesChanged = selectedApplication
    ? (editingNotes[selectedApplication.id] ?? "") !== (selectedApplication.notes ?? "")
    : false;

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
      const payload = await request(`/hunter/api/applications/?${params.toString()}`);
      const items = payload.results ?? [];
      setApplications(items);
      setTotalCount(payload.count ?? items.length);
      setSelectedApplicationId((current) =>
        items.some((item) => item.id === current) ? current : items[0]?.id ?? null
      );
      setEditingNotes(Object.fromEntries(items.map((item) => [item.id, item.notes ?? ""])));
    } catch (requestError) {
      setError(getErrorMessage(requestError, "We could not load your application tracker."));
      setApplications([]);
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
      setError(getErrorMessage(requestError, "We could not update this application."));
    } finally {
      setBusyAction("");
    }
  }

  const overviewCards = [
    { label: "Tracked", value: totalCount, helper: "Loaded from your pipeline" },
    { label: "Needs action", value: (statusCounts.saved ?? 0) + (statusCounts.applied ?? 0), helper: "Saved or recently applied" },
    { label: "Interviewing", value: statusCounts.interview ?? 0, helper: "Active conversations" },
    { label: "Offers", value: statusCounts.offer ?? 0, helper: "Positive outcomes in motion" }
  ];

  return (
    <AppShell
      title="Applications"
      subtitle="Turn tracked candidacies into a clean operating workflow with faster triage, clearer detail, and useful notes."
      actions={
        <button className="button button--ghost" type="button" onClick={loadApplications}>
          Refresh tracker
        </button>
      }
    >
      {error ? <div className="notice notice--error">{error}</div> : null}
      {feedback ? <div className="notice notice--success">{feedback}</div> : null}

      <section className="stats-grid">
        {overviewCards.map((card) => (
          <StatCard key={card.label} label={card.label} value={card.value} helper={card.helper} />
        ))}
      </section>

      <SectionCard
        title="Filter your tracker"
        subtitle="Narrow the pipeline by stage, keyword, company, and recency so the next follow-up is easier to find."
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
              <span>Keyword</span>
              <input
                value={filters.search}
                onChange={(event) => setFilters((previous) => ({ ...previous, search: event.target.value }))}
                placeholder="Role, recruiter, note, keyword..."
              />
            </label>

            <label className="field">
              <span>Company</span>
              <input
                value={filters.company_name}
                onChange={(event) => setFilters((previous) => ({ ...previous, company_name: event.target.value }))}
                placeholder="Acme"
              />
            </label>

            <label className="field">
              <span>Stage</span>
              <select
                value={filters.status}
                onChange={(event) => setFilters((previous) => ({ ...previous, status: event.target.value }))}
              >
                <option value="">All stages</option>
                {APPLICATION_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {titleize(status)}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>Sort by</span>
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

          <div className="action-row">
            <button className="button button--primary" type="submit">
              Apply filters
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
              Clear filters
            </button>
          </div>

          <p className="muted-copy">{trackerSummary}</p>
        </form>
      </SectionCard>

      <section className="two-column-grid two-column-grid--wide-left">
        <SectionCard
          title="Applications pipeline"
          subtitle="Scan status, provider, timing, and fit context without opening each record."
        >
          {loading ? <div className="loading-panel">Loading your application workflow...</div> : null}
          {!loading && !applications.length ? (
            <EmptyState
              title="No applications tracked yet"
              description="Start tracking from opportunities, or clear your filters if you expected existing applications here."
            />
          ) : null}

          {!loading && applications.length ? (
            <div className="list-stack">
              {applications.map((application) => (
                <article
                  className={application.id === selectedApplicationId ? "list-item application-list-item is-selected" : "list-item application-list-item"}
                  key={application.id}
                >
                  <div className="application-list-item__main">
                    <div className="inline-meta">
                      <button className="list-item__title-button" type="button" onClick={() => setSelectedApplicationId(application.id)}>
                        {application.job_title}
                      </button>
                      <StatusBadge value={application.status} />
                      {application.job_source ? <span className="status-badge tone-muted">{application.job_source}</span> : null}
                      {application.current_match ? (
                        <span className={`status-badge tone-${getScoreTone(application.current_match.match_score)}`}>
                          {application.current_match.match_score}% fit
                        </span>
                      ) : null}
                    </div>

                    <p>
                      {application.company_name || "Unknown company"}
                      {application.job_location ? ` | ${application.job_location}` : ""}
                    </p>

                    <p className="muted-copy">
                      {application.applied_at ? `Applied ${formatShortDate(application.applied_at)} | ` : "Not marked as applied yet | "}
                      Updated {formatRelativeDate(application.updated_at)}
                    </p>

                    <p>{getApplicationListPreview(application)}</p>

                    <div className="selection-pills">
                      {application.job_is_saved ? <span>Saved in jobs workspace</span> : null}
                      {application.current_match?.resume_label ? <span>Resume: {application.current_match.resume_label}</span> : null}
                    </div>
                  </div>

                  <div className="action-row action-row--wrap">
                    <button className="button button--ghost" type="button" onClick={() => setSelectedApplicationId(application.id)}>
                      Inspect
                    </button>
                    {application.job_url ? (
                      <a className="button button--ghost" href={application.job_url} target="_blank" rel="noreferrer">
                        Open job
                      </a>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          ) : null}
        </SectionCard>

        <SectionCard
          title="Application detail"
          subtitle="Use the selected record as your control panel for stage changes, notes, and fit context."
        >
          {!selectedApplication ? (
            <EmptyState
              title="Choose an application"
              description="Select an item from the pipeline to inspect its timeline, update status, and capture practical follow-up notes."
            />
          ) : (
            <div className="detail-stack">
              <div className="inline-meta">
                <strong>{selectedApplication.job_title}</strong>
                <StatusBadge value={selectedApplication.status} />
                {selectedApplication.current_match ? (
                  <span className={`status-badge tone-${getScoreTone(selectedApplication.current_match.match_score)}`}>
                    {selectedApplication.current_match.match_score}/100 fit
                  </span>
                ) : null}
              </div>

              <p className="job-detail-company">
                {selectedApplication.company_name || "Unknown company"}
                {selectedApplication.job_location ? ` | ${selectedApplication.job_location}` : ""}
              </p>

              <div className="insight-list insight-list--four">
                <div>
                  <span>Source</span>
                  <strong>{selectedApplication.job_source || "Unavailable"}</strong>
                </div>
                <div>
                  <span>Applied date</span>
                  <strong>{selectedApplication.applied_at ? formatShortDate(selectedApplication.applied_at) : "Not yet marked"}</strong>
                </div>
                <div>
                  <span>Last updated</span>
                  <strong>{formatDate(selectedApplication.updated_at)}</strong>
                </div>
                <div>
                  <span>Jobs workspace</span>
                  <strong>{selectedApplication.job_is_saved ? "Linked and saved" : "Application only"}</strong>
                </div>
              </div>

              <div className="application-detail-panel">
                <label className="field">
                  <span>Stage</span>
                  <select
                    value={selectedApplication.status}
                    disabled={busyAction === `application-${selectedApplication.id}`}
                    onChange={(event) =>
                      updateApplication(
                        selectedApplication,
                        { status: event.target.value },
                        `Application moved to ${titleize(event.target.value)}.`,
                      )
                    }
                  >
                    {APPLICATION_STATUSES.map((status) => (
                      <option key={status} value={status}>
                        {titleize(status)}
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
                          `Application moved to ${titleize(action.status)}.`,
                        )
                      }
                    >
                      {action.label}
                    </button>
                  ))}
                  {selectedApplication.job_url ? (
                    <a className="button button--ghost" href={selectedApplication.job_url} target="_blank" rel="noreferrer">
                      Open original posting
                    </a>
                  ) : null}
                </div>
              </div>

              <SectionCard
                className="job-detail-subcard"
                title="Notes and follow-ups"
                subtitle="Capture recruiter replies, interview prep, blockers, and practical next steps."
              >
                <label className="field">
                  <span>Notes</span>
                  <textarea
                    rows="8"
                    value={editingNotes[selectedApplication.id] ?? ""}
                    onChange={(event) =>
                      setEditingNotes((previous) => ({
                        ...previous,
                        [selectedApplication.id]: event.target.value
                      }))
                    }
                    placeholder="Add recruiter context, interview preparation points, compensation notes, or next actions..."
                  />
                </label>

                <div className="action-row action-row--wrap">
                  <button
                    className="button button--secondary"
                    type="button"
                    disabled={busyAction === `application-${selectedApplication.id}` || !notesChanged}
                    onClick={() =>
                      updateApplication(
                        selectedApplication,
                        { notes: editingNotes[selectedApplication.id] ?? "" },
                        "Application notes saved.",
                      )
                    }
                  >
                    Save notes
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
                    Reset draft
                  </button>
                  <span className="muted-copy">Last edited {formatRelativeDate(selectedApplication.updated_at)}</span>
                </div>
              </SectionCard>

              <SectionCard
                className="job-detail-subcard"
                title="Match context"
                subtitle={
                  selectedApplication.current_match
                    ? `Using ${selectedApplication.current_match.resume_label} as the latest known resume context.`
                    : "No related fit check exists for this application yet."
                }
              >
                {selectedApplication.current_match ? (
                  <div className="detail-stack">
                    <div className="insight-list insight-list--three">
                      <div>
                        <span>Match score</span>
                        <strong>{selectedApplication.current_match.match_score}/100</strong>
                      </div>
                      <div>
                        <span>Resume used</span>
                        <strong>{selectedApplication.current_match.resume_label}</strong>
                      </div>
                      <div>
                        <span>Updated</span>
                        <strong>{formatRelativeDate(selectedApplication.current_match.updated_at)}</strong>
                      </div>
                    </div>

                    <div className={`notice notice--${getScoreTone(selectedApplication.current_match.match_score) === "low" ? "error" : "success"}`}>
                      {selectedApplication.current_match.recommendation}
                    </div>

                    {selectedApplication.current_match.strengths?.length ? (
                      <div>
                        <strong>Why this role fits</strong>
                        <ul className="plain-list">
                          {selectedApplication.current_match.strengths.slice(0, 3).map((item, index) => (
                            <li key={`${item}-${index}`}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}

                    {selectedApplication.current_match.gaps?.length ? (
                      <div>
                        <strong>Watch-outs</strong>
                        <ul className="plain-list">
                          {selectedApplication.current_match.gaps.slice(0, 3).map((item, index) => (
                            <li key={`${item}-${index}`}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <p className="muted-copy">
                    This application does not have match guidance yet. You can still track the workflow here, and the jobs workspace can refresh fit context later.
                  </p>
                )}
              </SectionCard>

              <SectionCard
                className="job-detail-subcard"
                title="Job summary"
                subtitle="Keep the original opportunity context close while you work the application."
              >
                <p>{selectedApplication.job_description || "No detailed job summary was captured for this application yet."}</p>
              </SectionCard>
            </div>
          )}
        </SectionCard>
      </section>
    </AppShell>
  );
}
