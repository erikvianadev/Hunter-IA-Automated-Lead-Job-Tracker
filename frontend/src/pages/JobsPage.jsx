import { useEffect, useMemo, useState } from "react";

import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { SectionCard } from "../components/SectionCard";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { formatShortDate, getErrorMessage, titleize } from "../lib/utils";

function buildScrapeFeedback(payload) {
  if (!payload) {
    return "";
  }

  if ((payload.scraped ?? 0) === 0) {
    return "Search completed, but no roles matched this combination yet. Try broader keywords or a wider location filter.";
  }

  const saved = payload.saved ?? 0;
  const scraped = payload.scraped ?? 0;
  return `Search completed. Found ${scraped} roles and saved ${saved} to your workspace.`;
}

function getProviderSummary(payload) {
  if (!payload) {
    return [];
  }

  return [
    {
      label: "Providers checked",
      value: payload.providers_run?.length ?? 0
    },
    {
      label: "Roles found",
      value: payload.scraped ?? 0
    },
    {
      label: "Saved to workspace",
      value: payload.saved ?? 0
    }
  ];
}

export function JobsPage() {
  const { request } = useAuth();
  const [jobs, setJobs] = useState([]);
  const [savedJobs, setSavedJobs] = useState([]);
  const [applications, setApplications] = useState([]);
  const [query, setQuery] = useState({
    search: "",
    company_name: ""
  });
  const [scrapeForm, setScrapeForm] = useState({
    query: "Backend Engineer",
    location: "Remote"
  });
  const [scrapeSummary, setScrapeSummary] = useState(null);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [scrapeLoading, setScrapeLoading] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [busyAction, setBusyAction] = useState("");

  const savedJobIds = useMemo(
    () => new Set(savedJobs.map((item) => item.job.id)),
    [savedJobs],
  );
  const applicationsByJobId = useMemo(
    () => new Map(applications.map((item) => [item.job, item])),
    [applications],
  );

  async function loadJobs() {
    setJobsLoading(true);
    setError("");

    const params = new URLSearchParams();
    if (query.search.trim()) {
      params.set("search", query.search.trim());
    }
    if (query.company_name.trim()) {
      params.set("company_name", query.company_name.trim());
    }

    try {
      const [jobsPayload, savedPayload, applicationsPayload] = await Promise.all([
        request(`/hunter/api/jobs/${params.size ? `?${params.toString()}` : ""}`),
        request("/hunter/api/saved-jobs/"),
        request("/hunter/api/applications/?ordering=-updated_at")
      ]);
      setJobs(jobsPayload.results ?? []);
      setSavedJobs(savedPayload.results ?? []);
      setApplications(applicationsPayload.results ?? []);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "We could not load your opportunities right now."));
    } finally {
      setJobsLoading(false);
    }
  }

  useEffect(() => {
    loadJobs();
  }, []);

  async function runAction(actionKey, callback) {
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

  async function handleScrape(event) {
    event.preventDefault();
    setScrapeLoading(true);
    setError("");
    setFeedback("");
    setScrapeSummary(null);

    try {
      const payload = await request("/hunter/api/scrape/", {
        method: "POST",
        body: JSON.stringify({
          query: scrapeForm.query,
          location: scrapeForm.location
        })
      });
      setScrapeSummary(payload);
      setFeedback(buildScrapeFeedback(payload));
      await loadJobs();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "We could not refresh opportunities from the web right now."));
    } finally {
      setScrapeLoading(false);
    }
  }

  const providerSummary = getProviderSummary(scrapeSummary);
  const hasZeroScrapeResults = scrapeSummary && (scrapeSummary.scraped ?? 0) === 0;

  return (
    <AppShell
      title="Opportunities"
      subtitle="Discover stronger roles, save the best ones, and move them into your application pipeline."
      actions={
        <button className="button button--ghost" type="button" onClick={loadJobs}>
          Refresh jobs
        </button>
      }
    >
      {error ? <div className="notice notice--error">{error}</div> : null}
      {feedback ? <div className="notice notice--success">{feedback}</div> : null}

      <section className="two-column-grid">
        <SectionCard title="Search saved opportunities" subtitle="Filter the roles already in your workspace.">
          <form
            className="inline-form"
            onSubmit={(event) => {
              event.preventDefault();
              loadJobs();
            }}
          >
            <label className="field">
              <span>Keyword</span>
              <input
                value={query.search}
                onChange={(event) => setQuery((previous) => ({ ...previous, search: event.target.value }))}
                placeholder="Python, backend, product..."
              />
            </label>

            <label className="field">
              <span>Company</span>
              <input
                value={query.company_name}
                onChange={(event) =>
                  setQuery((previous) => ({ ...previous, company_name: event.target.value }))
                }
                placeholder="Acme"
              />
            </label>

            <button className="button button--primary" type="submit">
              Search roles
            </button>
          </form>
        </SectionCard>

        <SectionCard title="Find fresh roles" subtitle="Search the web and bring new opportunities into your workspace.">
          <form className="inline-form" onSubmit={handleScrape}>
            <label className="field">
              <span>Role</span>
              <input
                value={scrapeForm.query}
                onChange={(event) =>
                  setScrapeForm((previous) => ({ ...previous, query: event.target.value }))
                }
              />
            </label>

            <label className="field">
              <span>Location</span>
              <input
                value={scrapeForm.location}
                onChange={(event) =>
                  setScrapeForm((previous) => ({ ...previous, location: event.target.value }))
                }
              />
            </label>

            <button className="button button--secondary" type="submit" disabled={scrapeLoading}>
              {scrapeLoading ? "Finding new roles..." : "Find roles"}
            </button>
          </form>

          {scrapeLoading ? (
            <div className="loading-inline">Checking job sources and saving any matching roles...</div>
          ) : null}

          {scrapeSummary ? (
            <div className="detail-stack">
              <div className="inline-meta">
                <strong>Latest search</strong>
                <StatusBadge value={scrapeSummary.status} tone="medium" />
              </div>
              <div className="insight-list">
                {providerSummary.map((item) => (
                  <div key={item.label}>
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                  </div>
                ))}
              </div>

              {hasZeroScrapeResults ? (
                <div className="notice notice--success">
                  No matching roles were found this time. Try broader job titles like "Software Engineer", remove location restrictions, or search for a wider specialty.
                </div>
              ) : null}

              <p className="muted-copy">
                Sources that responded well: {scrapeSummary.providers_succeeded?.join(", ") || "none this time"}
              </p>
              {(scrapeSummary.providers_failed?.length ?? 0) > 0 ? (
                <p className="muted-copy">
                  Sources with issues: {scrapeSummary.providers_failed.join(", ")}
                </p>
              ) : null}
              {(scrapeSummary.providers_blocked?.length ?? 0) > 0 ? (
                <p className="muted-copy">
                  Blocked sources: {scrapeSummary.providers_blocked.join(", ")}
                </p>
              ) : null}
              {(scrapeSummary.duplicates_removed ?? 0) > 0 ? (
                <p className="muted-copy">
                  Duplicate roles removed: {scrapeSummary.duplicates_removed}
                </p>
              ) : null}
            </div>
          ) : null}
        </SectionCard>
      </section>

      <SectionCard title="Opportunity list" subtitle="Save promising roles, match them to your resume, and move the best ones into action.">
        {jobsLoading ? <div className="loading-panel">Loading your saved opportunities...</div> : null}
        {!jobsLoading && !jobs.length ? (
          <EmptyState
            title="No opportunities yet"
            description="Search the web or adjust your filters to start building a stronger shortlist."
          />
        ) : null}
        {!jobsLoading && jobs.length ? (
          <div className="list-stack">
            {jobs.map((job) => {
              const isSaved = savedJobIds.has(job.id);
              const application = applicationsByJobId.get(job.id);
              return (
                <article className="list-item" key={job.id}>
                  <div>
                    <div className="inline-meta">
                      <strong>{job.title}</strong>
                      {application ? <StatusBadge value={application.status} /> : null}
                      {isSaved ? <StatusBadge value="saved" /> : null}
                    </div>
                    <p>
                      {job.company_name} | {job.location}
                    </p>
                    <p className="muted-copy">
                      Added {formatShortDate(job.created_at)}
                      {job.date_posted ? ` | Posted ${job.date_posted}` : ""}
                    </p>
                    {job.description ? <p>{job.description.slice(0, 220)}...</p> : null}
                    {job.tags?.length ? (
                      <div className="selection-pills">
                        {job.tags.map((tag) => (
                          <span key={tag.id}>{tag.name}</span>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  <div className="action-row action-row--wrap">
                    <a className="button button--ghost" href={job.url} target="_blank" rel="noreferrer">
                      View posting
                    </a>
                    <button
                      className="button button--ghost"
                      type="button"
                      disabled={busyAction === `save-${job.id}`}
                      onClick={() =>
                        runAction(`save-${job.id}`, async () => {
                          await request(`/hunter/api/jobs/${job.id}/save/`, {
                            method: isSaved ? "DELETE" : "POST"
                          });
                          await loadJobs();
                          setFeedback(isSaved ? "Removed from saved roles." : "Saved for later.");
                        })
                      }
                    >
                      {isSaved ? "Remove saved" : "Save role"}
                    </button>
                    <button
                      className="button button--secondary"
                      type="button"
                      disabled={busyAction === `apply-${job.id}`}
                      onClick={() =>
                        runAction(`apply-${job.id}`, async () => {
                          const payload = await request(`/hunter/api/jobs/${job.id}/apply/`, {
                            method: "POST",
                            body: JSON.stringify({
                              notes: "Tracked from the opportunities page."
                            })
                          });
                          await loadJobs();
                          setFeedback(`This role is now marked as ${titleize(payload.status)}.`);
                        })
                      }
                    >
                      {application ? "Update application" : "Track application"}
                    </button>
                    <button
                      className="button button--secondary"
                      type="button"
                      disabled={busyAction === `match-${job.id}`}
                      onClick={() =>
                        runAction(`match-${job.id}`, async () => {
                          const payload = await request(`/hunter/api/jobs/${job.id}/match/`, {
                            method: "POST",
                            body: JSON.stringify({})
                          });
                          setFeedback(`Resume fit updated: ${payload.match_score}/100.`);
                        })
                      }
                    >
                      Check resume fit
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        ) : null}
      </SectionCard>
    </AppShell>
  );
}
