import { Link, useLocation } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { SectionCard } from "../components/SectionCard";

export function BillingResultPage({ kind }) {
  const location = useLocation();
  const isSuccess = kind === "success";
  const sessionId = new URLSearchParams(location.search).get("session_id");

  return (
    <AppShell
      title={isSuccess ? "Checkout success" : "Checkout canceled"}
      subtitle="Return surface for Stripe redirects configured on the Django side."
    >
      <SectionCard title={isSuccess ? "Payment flow completed" : "Checkout was interrupted"}>
        <div className="detail-stack">
          <p>
            {isSuccess
              ? "Stripe redirected back successfully. Refresh billing to confirm the subscription after webhook processing."
              : "No subscription changes were finalized. You can review plans and try again anytime."}
          </p>
          {sessionId ? <p className="muted-copy">Checkout session: {sessionId}</p> : null}
          <div className="action-row">
            <Link className="button button--primary" to="/billing">
              Go to billing
            </Link>
            <Link className="button button--ghost" to="/dashboard">
              Back to dashboard
            </Link>
          </div>
        </div>
      </SectionCard>
    </AppShell>
  );
}
