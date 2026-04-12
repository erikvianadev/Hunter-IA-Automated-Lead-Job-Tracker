import { useEffect, useMemo, useState } from "react";

import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { SectionCard } from "../components/SectionCard";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { formatRelativeDate, formatShortDate, getErrorMessage, titleize } from "../lib/utils";

const JOBS_PAGE_SIZE = 12;
const APPLICATION_STATUSES = ["saved", "applied", "interview", "rejected", "offer", "archived"];
const STATUS_OPTIONS = [{ value: "all", label: "All jobs" }, { value: "saved", label: "Saved" }, { value: "applied", label: "Applied" }];
const SORT_OPTIONS = [
  { value: "-created_at", label: "Newest saved first" },
  { value: "-date_posted", label: "Most recent posting" },
  { value: "company_name", label: "Company A-Z" },
  { value: "title", label: "Role A-Z" }
];

function buildScrapeFeedback(payload) {
  if (!payload) return "";
  const rawScraped = payload.raw_scraped ?? 0;
  if (!rawScraped) return "Search completed, but no providers returned matching roles. Try a broader role title or a wider location.";
  return `Search completed. ${rawScraped} roles were fetched, ${payload.scraped ?? 0} unique roles remained after deduplication, and ${payload.saved ?? 0} were saved.`;
}

function getProviderSummary(payload) {
  if (!payload) return [];
  return [
    { label: "Providers checked", value: payload.providers_run?.length ?? 0 },
    { label: "Fetched", value: payload.raw_scraped ?? 0 },
    { label: "Unique roles", value: payload.scraped ?? 0 },
    { label: "Saved", value: payload.saved ?? 0 }
  ];
}

function getProviderBreakdown(payload) {
  if (!payload?.provider_job_counts) return [];
  return Object.entries(payload.provider_job_counts)
    .map(([provider, jobsFound]) => {
      const name = provider.toLowerCase();
      const blocked = payload.providers_blocked?.includes(name);
      const failed = payload.providers_failed?.includes(name);
      return {
        provider: titleize(provider),
        jobsFound,
        tone: blocked ? "low" : failed ? "medium" : "good",
        statusLabel: blocked ? "Blocked" : failed ? "Issue" : "Healthy"
      };
    })
    .sort((left, right) => right.jobsFound - left.jobsFound || left.provider.localeCompare(right.provider));
}

function getScoreTone(score) {
  if (score >= 80) return "good";
  if (score >= 60) return "medium";
  return "low";
}

function getDescriptionPreview(description) {
  if (!description) return "No detailed job description was captured yet.";
  return description.length <= 190 ? description : `${description.slice(0, 190).trim()}...`;
}

function getJobRecencyLabel(job) {
  const value = job.date_posted || job.created_at;
  return `${job.date_posted ? "Posted" : "Added"} ${formatShortDate(value)} | ${formatRelativeDate(value)}`;
}

function buildSearchSummary(count, shown, filters) {
  const parts = [];
  if (filters.search) parts.push(`keyword "${filters.search}"`);
  if (filters.company_name) parts.push(`company "${filters.company_name}"`);
  if (filters.location) parts.push(`location "${filters.location}"`);
  if (filters.status && filters.status !== "all") parts.push(`${titleize(filters.status)} jobs`);
  return parts.length
    ? `Showing ${shown} loaded roles out of ${count} total for ${parts.join(", ")}.`
    : `Showing ${shown} loaded roles out of ${count} total in your workspace.`;
}

export function JobsPage() {
  const { request } = useAuth();
  const [jobsState, setJobsState] = useState({ items: [], count: 0, page: 1, hasMore: false });
  const [workspaceStats, setWorkspaceStats] = useState({ savedCount: 0, applicationCount: 0, matchCount: 0 });
  const [resumes, setResumes] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [selectedResumeId, setSelectedResumeId] = useState(null);
  const [filters, setFilters] = useState({ search: "", company_name: "", location: "", status: "all", ordering: "-created_at" });
  const [appliedFilters, setAppliedFilters] = useState({ search: "", company_name: "", location: "", status: "all", ordering: "-created_at" });
  const [scrapeForm, setScrapeForm] = useState({ query: "Backend Engineer", location: "Remote" });
  const [scrapeSummary, setScrapeSummary] = useState(null);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [metaLoading, setMetaLoading] = useState(true);
  const [scrapeLoading, setScrapeLoading] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [busyAction, setBusyAction] = useState("");

  const selectedJob = useMemo(() => jobsState.items.find((job) => job.id === selectedJobId) ?? null, [jobsState.items, selectedJobId]);
  const selectedResume = useMemo(() => resumes.find((resume) => resume.id === selectedResumeId) ?? null, [resumes, selectedResumeId]);
  const providerSummary = useMemo(() => getProviderSummary(scrapeSummary), [scrapeSummary]);
  const providerBreakdown = useMemo(() => getProviderBreakdown(scrapeSummary), [scrapeSummary]);
  const searchSummary = useMemo(() => buildSearchSummary(jobsState.count, jobsState.items.length, appliedFilters), [appliedFilters, jobsState.count, jobsState.items.length]);

  async function loadWorkspaceMeta() {
    setMetaLoading(true);
    try {
      const [savedPayload, applicationsPayload, matchesPayload, resumesPayload] = await Promise.all([
        request("/hunter/api/saved-jobs/?page_size=1"),
        request("/hunter/api/applications/?page_size=1"),
        request("/hunter/api/matches/?page_size=1"),
        request("/hunter/api/resumes/?page_size=100")
      ]);
      setWorkspaceStats({
        savedCount: savedPayload.count ?? 0,
        applicationCount: applicationsPayload.count ?? 0,
        matchCount: matchesPayload.count ?? 0
      });
      const resumeItems = resumesPayload.results ?? [];
      setResumes(resumeItems);
      setSelectedResumeId((current) =>
        resumeItems.some((resume) => resume.id === current)
          ? current
          : resumeItems.find((resume) => resume.is_active)?.id ?? resumeItems[0]?.id ?? null
      );
    } catch (requestError) {
      setError(getErrorMessage(requestError, "We could not load your job workspace details."));
    } finally {
      setMetaLoading(false);
    }
  }

  async function loadJobs({ page = 1, append = false, nextFilters = appliedFilters, pageSize = JOBS_PAGE_SIZE } = {}) {
    setJobsLoading(true);
    setError("");
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize), ordering: nextFilters.ordering });
    if (nextFilters.search.trim()) params.set("search", nextFilters.search.trim());
    if (nextFilters.company_name.trim()) params.set("company_name", nextFilters.company_name.trim());
    if (nextFilters.location.trim()) params.set("location", nextFilters.location.trim());
    if (nextFilters.status !== "all") params.set("status", nextFilters.status);
    try {
      const payload = await request(`/hunter/api/jobs/?${params.toString()}`);
      const incomingItems = payload.results ?? [];
      const combinedItems = append ? [...jobsState.items, ...incomingItems] : incomingItems;
      setJobsState({
        items: combinedItems,
        count: payload.count ?? combinedItems.length,
        page: append ? page : Math.max(1, Math.ceil(combinedItems.length / JOBS_PAGE_SIZE)),
        hasMore: Boolean(payload.next)
      });
      setSelectedJobId((current) => combinedItems.some((job) => job.id === current) ? current : combinedItems[0]?.id ?? null);
    } catch (requestError) {
      if (!append) {
        setJobsState({ items: [], count: 0, page: 1, hasMore: false });
        setSelectedJobId(null);
      }
      setError(getErrorMessage(requestError, "We could not load your opportunities right now."));
    } finally {
      setJobsLoading(false);
    }
  }

  async function refreshJobs(preserveLoaded = true) {
    const pageSize = preserveLoaded ? Math.max(JOBS_PAGE_SIZE, jobsState.page * JOBS_PAGE_SIZE) : JOBS_PAGE_SIZE;
    await loadJobs({ page: 1, append: false, nextFilters: appliedFilters, pageSize });
  }

  useEffect(() => { loadWorkspaceMeta(); }, []);
  useEffect(() => { loadJobs({ page: 1, append: false, nextFilters: appliedFilters, pageSize: JOBS_PAGE_SIZE }); }, [appliedFilters]);

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
        body: JSON.stringify({ query: scrapeForm.query, location: scrapeForm.location })
      });
      setScrapeSummary(payload);
      setFeedback(buildScrapeFeedback(payload));
      await Promise.all([refreshJobs(false), loadWorkspaceMeta()]);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "We could not refresh opportunities from the web right now."));
    } finally {
      setScrapeLoading(false);
    }
  }

  const overviewCards = [
    { label: "Workspace roles", value: jobsState.count, helper: "Across current filters" },
    { label: "Saved roles", value: metaLoading ? "..." : workspaceStats.savedCount, helper: "Ready for review" },
    { label: "Tracked applications", value: metaLoading ? "..." : workspaceStats.applicationCount, helper: "Already in motion" },
    { label: "Match results", value: metaLoading ? "..." : workspaceStats.matchCount, helper: "Roles with fit visibility" }
  ];

  return (
    <AppShell
      title="Opportunities"
      subtitle="Turn fetched jobs into a working shortlist with clear filters, fit signals, and next actions."
      actions={<button className="button button--ghost" type="button" onClick={() => { refreshJobs(false); loadWorkspaceMeta(); }}>Refresh workspace</button>}
    >
      {error ? <div className="notice notice--error">{error}</div> : null}
      {feedback ? <div className="notice notice--success">{feedback}</div> : null}
      <section className="stats-grid">{overviewCards.map((card) => <StatCard key={card.label} label={card.label} value={card.value} helper={card.helper} />)}</section>

      <section className="two-column-grid">
        <SectionCard title="Filter your workspace" subtitle="Find the right role faster with operational filters and recency sorting.">
          <form className="stack" onSubmit={(event) => { event.preventDefault(); setAppliedFilters({ ...filters }); }}>
            <div className="jobs-filter-grid">
              <label className="field"><span>Keyword</span><input value={filters.search} onChange={(event) => setFilters((previous) => ({ ...previous, search: event.target.value }))} placeholder="Backend, Python, platform..." /></label>
              <label className="field"><span>Company</span><input value={filters.company_name} onChange={(event) => setFilters((previous) => ({ ...previous, company_name: event.target.value }))} placeholder="Acme" /></label>
              <label className="field"><span>Location</span><input value={filters.location} onChange={(event) => setFilters((previous) => ({ ...previous, location: event.target.value }))} placeholder="Remote, Brazil, Sao Paulo..." /></label>
              <label className="field"><span>Status</span><select value={filters.status} onChange={(event) => setFilters((previous) => ({ ...previous, status: event.target.value }))}>{STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
              <label className="field"><span>Sort by</span><select value={filters.ordering} onChange={(event) => setFilters((previous) => ({ ...previous, ordering: event.target.value }))}>{SORT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
            </div>
            <div className="action-row">
              <button className="button button--primary" type="submit">Apply filters</button>
              <button className="button button--ghost" type="button" onClick={() => {
                const cleared = { search: "", company_name: "", location: "", status: "all", ordering: "-created_at" };
                setFilters(cleared);
                setAppliedFilters(cleared);
              }}>Clear filters</button>
            </div>
            <p className="muted-copy">{searchSummary}</p>
          </form>
        </SectionCard>

        <SectionCard title="Find fresh roles" subtitle="Scrape active providers, keep the result summary readable, and see which sources are contributing.">
          <form className="stack" onSubmit={handleScrape}>
            <div className="jobs-filter-grid">
              <label className="field"><span>Role</span><input value={scrapeForm.query} onChange={(event) => setScrapeForm((previous) => ({ ...previous, query: event.target.value }))} /></label>
              <label className="field"><span>Location</span><input value={scrapeForm.location} onChange={(event) => setScrapeForm((previous) => ({ ...previous, location: event.target.value }))} /></label>
            </div>
            <button className="button button--secondary" type="submit" disabled={scrapeLoading}>{scrapeLoading ? "Searching providers..." : "Fetch roles"}</button>
          </form>
          {scrapeLoading ? <div className="loading-inline">Checking providers, deduplicating results, and saving any new roles...</div> : null}
          {scrapeSummary ? (
            <div className="detail-stack">
              <div className="inline-meta"><strong>Latest scrape</strong><StatusBadge value={scrapeSummary.status} tone="medium" /></div>
              <div className="insight-list insight-list--four">{providerSummary.map((item) => <div key={item.label}><span>{item.label}</span><strong>{item.value}</strong></div>)}</div>
              {providerBreakdown.length ? <div className="provider-breakdown">{providerBreakdown.map((item) => <article className="provider-breakdown__card" key={item.provider}><div className="inline-meta"><strong>{item.provider}</strong><StatusBadge value={item.statusLabel} tone={item.tone} /></div><p className="muted-copy">{item.jobsFound} roles contributed</p></article>)}</div> : null}
              {(scrapeSummary.raw_scraped ?? 0) === 0 ? <div className="notice notice--success">No matching roles were found this time. Try broader titles like "Software Engineer" or remove location restrictions.</div> : null}
              {(scrapeSummary.duplicates_removed ?? 0) > 0 ? <p className="muted-copy">Deduplicated {scrapeSummary.duplicates_removed} overlapping roles before saving.</p> : null}
            </div>
          ) : null}
        </SectionCard>
      </section>

      <section className="two-column-grid two-column-grid--wide-left">
        <SectionCard title="Jobs workspace" subtitle="Inspect the shortlist, take action, and keep larger result sets manageable with incremental loading.">
          {jobsLoading && !jobsState.items.length ? <div className="loading-panel">Loading your opportunities workspace...</div> : null}
          {!jobsLoading && !jobsState.items.length ? <EmptyState title="No opportunities found" description="Try broader filters or run a fresh scrape to bring new roles into the workspace." /> : null}
          {jobsState.items.length ? <div className="list-stack">{jobsState.items.map((job) => <article className={job.id === selectedJobId ? "list-item job-list-item is-selected" : "list-item job-list-item"} key={job.id}>
            <div className="job-list-item__main">
              <div className="inline-meta">
                <button className="list-item__title-button" type="button" onClick={() => setSelectedJobId(job.id)}>{job.title}</button>
                {job.application_status ? <StatusBadge value={job.application_status} /> : null}
                {!job.application_status && job.is_saved ? <StatusBadge value="saved" /> : null}
                {job.current_match ? <span className={`status-badge tone-${getScoreTone(job.current_match.match_score)}`}>{job.current_match.match_score}% fit</span> : null}
              </div>
              <p>{job.company_name || "Unknown company"} | {job.location || "Location not provided"}</p>
              <p className="muted-copy">{job.source ? `${job.source} | ` : ""}{getJobRecencyLabel(job)}</p>
              <p>{getDescriptionPreview(job.description)}</p>
            </div>
            <div className="action-row action-row--wrap">
              <button className="button button--ghost" type="button" onClick={() => setSelectedJobId(job.id)}>Inspect</button>
              <button className="button button--ghost" type="button" disabled={busyAction === `save-${job.id}`} onClick={() => runAction(`save-${job.id}`, async () => {
                await request(`/hunter/api/jobs/${job.id}/save/`, { method: job.is_saved ? "DELETE" : "POST" });
                await Promise.all([refreshJobs(), loadWorkspaceMeta()]);
                setFeedback(job.is_saved ? "Role removed from saved jobs." : "Role saved to your workspace.");
              })}>{job.is_saved ? "Unsave" : "Save"}</button>
              <button className="button button--secondary" type="button" disabled={busyAction === `apply-${job.id}`} onClick={() => runAction(`apply-${job.id}`, async () => {
                if (job.application_id) {
                  await request(`/hunter/api/applications/${job.application_id}/`, { method: "PATCH", body: JSON.stringify({ status: "applied" }) });
                } else {
                  await request(`/hunter/api/jobs/${job.id}/apply/`, { method: "POST", body: JSON.stringify({ notes: "Tracked from the opportunities workspace." }) });
                }
                await Promise.all([refreshJobs(), loadWorkspaceMeta()]);
                setFeedback("Role moved into your applied workflow.");
              })}>{job.application_status === "applied" ? "Applied" : "Apply"}</button>
              {job.url ? <a className="button button--ghost" href={job.url} target="_blank" rel="noreferrer">Open original</a> : null}
            </div>
          </article>)}</div> : null}
          {jobsState.hasMore ? <div className="jobs-load-more"><button className="button button--ghost" type="button" disabled={jobsLoading} onClick={() => loadJobs({ page: jobsState.page + 1, append: true, nextFilters: appliedFilters, pageSize: JOBS_PAGE_SIZE })}>{jobsLoading ? "Loading more roles..." : "Load more roles"}</button></div> : null}
        </SectionCard>

        <SectionCard title="Job details" subtitle="Keep the next action obvious with original posting access, workflow controls, and match visibility.">
          {!selectedJob ? <EmptyState title="Choose a role" description="Select a job from the list to inspect details, manage its status, and review the resume match." /> : (
            <div className="detail-stack">
              <div className="inline-meta"><strong>{selectedJob.title}</strong>{selectedJob.application_status ? <StatusBadge value={selectedJob.application_status} /> : null}{!selectedJob.application_status && selectedJob.is_saved ? <StatusBadge value="saved" /> : null}</div>
              <p className="job-detail-company">{selectedJob.company_name || "Unknown company"} | {selectedJob.location || "Location not provided"}</p>
              <div className="insight-list insight-list--two"><div><span>Source</span><strong>{selectedJob.source || "Unavailable"}</strong></div><div><span>Recency</span><strong>{getJobRecencyLabel(selectedJob)}</strong></div></div>
              <div className="action-row action-row--wrap">
                <button className="button button--ghost" type="button" disabled={busyAction === `save-detail-${selectedJob.id}`} onClick={() => runAction(`save-detail-${selectedJob.id}`, async () => {
                  await request(`/hunter/api/jobs/${selectedJob.id}/save/`, { method: selectedJob.is_saved ? "DELETE" : "POST" });
                  await Promise.all([refreshJobs(), loadWorkspaceMeta()]);
                  setFeedback(selectedJob.is_saved ? "Role removed from saved jobs." : "Role saved to your workspace.");
                })}>{selectedJob.is_saved ? "Unsave role" : "Save role"}</button>
                <button className="button button--secondary" type="button" disabled={busyAction === `apply-detail-${selectedJob.id}`} onClick={() => runAction(`apply-detail-${selectedJob.id}`, async () => {
                  if (selectedJob.application_id) {
                    await request(`/hunter/api/applications/${selectedJob.application_id}/`, { method: "PATCH", body: JSON.stringify({ status: "applied" }) });
                  } else {
                    await request(`/hunter/api/jobs/${selectedJob.id}/apply/`, { method: "POST", body: JSON.stringify({ notes: "Tracked from the opportunities workspace." }) });
                  }
                  await Promise.all([refreshJobs(), loadWorkspaceMeta()]);
                  setFeedback("Role moved into your applied workflow.");
                })}>Mark as applied</button>
                {selectedJob.url ? <a className="button button--ghost" href={selectedJob.url} target="_blank" rel="noreferrer">Open original posting</a> : null}
              </div>
              {selectedJob.application_id ? <label className="field"><span>Pipeline stage</span><select value={selectedJob.application_status ?? "saved"} disabled={busyAction === `stage-${selectedJob.id}`} onChange={(event) => runAction(`stage-${selectedJob.id}`, async () => {
                await request(`/hunter/api/applications/${selectedJob.application_id}/`, { method: "PATCH", body: JSON.stringify({ status: event.target.value }) });
                await Promise.all([refreshJobs(), loadWorkspaceMeta()]);
                setFeedback(`Role moved to ${titleize(event.target.value)}.`);
              })}>{APPLICATION_STATUSES.map((status) => <option key={status} value={status}>{titleize(status)}</option>)}</select></label> : <div className="notice notice--success">This role is not yet in the application pipeline. Use the apply action when you want to start tracking stages.</div>}
              <SectionCard className="job-detail-subcard" title="Resume match" subtitle={selectedResume ? `Run or refresh the match using ${selectedResume.label || selectedResume.original_filename}.` : "Upload or activate a resume to generate a fit score."} actions={<button className="button button--secondary" type="button" disabled={!selectedResumeId || busyAction === `match-${selectedJob.id}`} onClick={() => runAction(`match-${selectedJob.id}`, async () => {
                const payload = await request(`/hunter/api/jobs/${selectedJob.id}/match/`, { method: "POST", body: JSON.stringify(selectedResumeId ? { resume_id: selectedResumeId } : {}) });
                await Promise.all([refreshJobs(), loadWorkspaceMeta()]);
                setFeedback(`Resume fit updated to ${payload.match_score}/100.`);
              })}>{busyAction === `match-${selectedJob.id}` ? "Refreshing fit..." : "Refresh fit"}</button>}>
                {resumes.length ? <label className="field"><span>Resume for matching</span><select value={selectedResumeId ?? ""} onChange={(event) => setSelectedResumeId(Number(event.target.value))}>{resumes.map((resume) => <option key={resume.id} value={resume.id}>{resume.label || resume.original_filename}{resume.is_active ? " (Primary)" : ""}</option>)}</select></label> : <div className="notice notice--error">No resume is available for matching yet. Upload a resume first to unlock fit scoring.</div>}
                {selectedJob.current_match ? <div className="detail-stack">
                  <div className="insight-list insight-list--three"><div><span>Match score</span><strong>{selectedJob.current_match.match_score}/100</strong></div><div><span>Resume used</span><strong>{selectedJob.current_match.resume_label}</strong></div><div><span>Updated</span><strong>{formatRelativeDate(selectedJob.current_match.updated_at)}</strong></div></div>
                  <div className={`notice notice--${getScoreTone(selectedJob.current_match.match_score) === "low" ? "error" : "success"}`}>{selectedJob.current_match.recommendation}</div>
                  {selectedJob.current_match.gaps?.length ? <div><strong>Top gaps</strong><ul className="plain-list">{selectedJob.current_match.gaps.slice(0, 3).map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul></div> : null}
                  {selectedJob.current_match.strengths?.length ? <div><strong>Why it fits</strong><ul className="plain-list">{selectedJob.current_match.strengths.slice(0, 2).map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul></div> : null}
                </div> : <p className="muted-copy">No match has been generated for this role yet. Run a fit check to expose score, gaps, and recommendation.</p>}
              </SectionCard>
              <div className="detail-stack"><strong>Role description</strong><p>{selectedJob.description || "No detailed description was captured for this job yet."}</p></div>
            </div>
          )}
        </SectionCard>
      </section>
    </AppShell>
  );
}
