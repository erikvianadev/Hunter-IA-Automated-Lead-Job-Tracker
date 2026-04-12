import { useEffect, useState } from "react";

import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { SectionCard } from "../components/SectionCard";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { formatCurrency, formatDate, getErrorMessage, titleize } from "../lib/utils";

export function BillingPage() {
  const { request } = useAuth();
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [busyAction, setBusyAction] = useState("");

  async function loadOverview() {
    setLoading(true);
    setError("");

    try {
      const payload = await request("/hunter/api/billing/subscription/");
      setOverview(payload);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "We could not load your plan details."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadOverview();
  }, []);

  async function subscribe(planCode, billingCycle) {
    setBusyAction(`${planCode}-${billingCycle}`);
    setError("");
    setFeedback("");

    try {
      const payload = await request("/hunter/api/billing/subscribe/", {
        method: "POST",
        body: JSON.stringify({
          plan_code: planCode,
          billing_cycle: billingCycle
        })
      });
      setFeedback("Redirecting you to secure checkout...");
      window.location.href = payload.checkout_url;
    } catch (requestError) {
      setError(getErrorMessage(requestError, "We could not start checkout."));
    } finally {
      setBusyAction("");
    }
  }

  async function cancelSubscription() {
    setBusyAction("cancel");
    setError("");
    setFeedback("");

    try {
      await request("/hunter/api/billing/cancel/", {
        method: "POST",
        body: JSON.stringify({})
      });
      setFeedback("Your renewal settings have been updated.");
      await loadOverview();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "We could not update your subscription."));
    } finally {
      setBusyAction("");
    }
  }

  const subscription = overview?.subscription;

  return (
    <AppShell
      title="Billing"
      subtitle="Choose the right plan for deeper resume insight and a more confident job search."
      actions={
        <button className="button button--ghost" type="button" onClick={loadOverview}>
          Refresh billing
        </button>
      }
    >
      {error ? <div className="notice notice--error">{error}</div> : null}
      {feedback ? <div className="notice notice--success">{feedback}</div> : null}

      <section className="two-column-grid">
        <SectionCard
          title="Your current plan"
          subtitle="See what is active today and when your current access renews."
          actions={
            subscription?.plan_code !== "free" ? (
              <button
                className="button button--ghost"
                type="button"
                disabled={busyAction === "cancel"}
                onClick={cancelSubscription}
              >
                {busyAction === "cancel" ? "Updating..." : "Turn off renewal"}
              </button>
            ) : null
          }
        >
          {loading ? <div className="loading-panel">Loading your plan details...</div> : null}
          {!loading && subscription ? (
            <div className="detail-stack">
              <div className="inline-meta">
                <strong>{subscription.plan_name}</strong>
                <StatusBadge value={subscription.status} />
                <StatusBadge value={subscription.billing_cycle} />
              </div>
              <p>
                {formatCurrency(subscription.price_amount, subscription.currency)} | Renewal{" "}
                {subscription.auto_renew ? "on" : "off"}
              </p>
              <p className="muted-copy">
                Started {formatDate(subscription.started_at)}
                {subscription.current_period_end ? ` | Current period ends ${formatDate(subscription.current_period_end)}` : ""}
              </p>
              {subscription.features?.length ? (
                <div className="selection-pills">
                  {subscription.features.map((feature) => (
                    <span key={feature}>{feature}</span>
                  ))}
                </div>
              ) : null}
              {subscription.last_invoice ? (
                <div className="detail-stack">
                  <strong>Latest invoice</strong>
                  <p>
                    {formatCurrency(subscription.last_invoice.amount, subscription.last_invoice.currency)} |{" "}
                    {titleize(subscription.last_invoice.status)}
                  </p>
                </div>
              ) : null}
            </div>
          ) : null}
        </SectionCard>

        <SectionCard title="After checkout" subtitle="Return here after checkout to confirm your plan and access.">
          <div className="detail-stack">
            <p>
              Success page: <code>/billing/success</code>
            </p>
            <p>
              Cancel page: <code>/billing/cancel</code>
            </p>
            <p className="muted-copy">
              Checkout, plan validation, and premium access are still handled securely by the backend.
            </p>
          </div>
        </SectionCard>
      </section>

      <SectionCard title="Upgrade options" subtitle="Unlock premium insight when you want deeper resume guidance and comparisons.">
        {loading ? <div className="loading-panel">Loading available plans...</div> : null}
        {!loading && !overview?.plans?.length ? (
          <EmptyState
            title="No plans available right now"
            description="Check your billing configuration and refresh this page."
          />
        ) : null}
        {!loading && overview?.plans?.length ? (
          <div className="plan-grid">
            {overview.plans.map((plan) => (
              <article className={plan.highlighted ? "plan-card is-highlighted" : "plan-card"} key={`${plan.code}-${plan.billing_cycle}`}>
                <div className="inline-meta">
                  <strong>{plan.name}</strong>
                  {plan.is_current ? <StatusBadge value="active" /> : null}
                </div>
                <h3>{formatCurrency(plan.price_amount, plan.currency)}</h3>
                <p>{titleize(plan.billing_cycle)}</p>
                <ul className="plain-list">
                  {plan.features.map((feature) => (
                    <li key={feature}>{feature}</li>
                  ))}
                </ul>
                <button
                  className={plan.highlighted ? "button button--primary" : "button button--secondary"}
                  type="button"
                  disabled={plan.is_current || plan.code === "free" || busyAction === `${plan.code}-${plan.billing_cycle}`}
                  onClick={() => subscribe(plan.code, plan.billing_cycle)}
                >
                  {plan.is_current
                    ? "Current plan"
                    : busyAction === `${plan.code}-${plan.billing_cycle}`
                      ? "Opening checkout..."
                      : "Unlock this plan"}
                </button>
              </article>
            ))}
          </div>
        ) : null}
      </SectionCard>
    </AppShell>
  );
}
