import { Link, useLocation } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { SectionCard } from "../components/SectionCard";
import { getCheckoutResultPresentation } from "../lib/presentation";

export function BillingResultPage({ kind }) {
  const location = useLocation();
  const hasCheckoutReference = new URLSearchParams(location.search).has("session_id");
  const presentation = getCheckoutResultPresentation(kind);

  return (
    <AppShell title={presentation.title} subtitle={presentation.subtitle}>
      <SectionCard title={presentation.heading}>
        <div className="detail-stack">
          <div className={`notice notice--${presentation.tone}`}>
            <strong>{presentation.heading}</strong>
            <p>{presentation.message}</p>
            <p>{presentation.nextStep}</p>
          </div>
          {hasCheckoutReference ? (
            <p className="muted-copy">
              A confirmação do checkout foi recebida com uma referência segura para suporte.
            </p>
          ) : null}
          <div className="action-row action-row--wrap">
            <Link className="button button--primary" to="/billing">
              Conferir acesso
            </Link>
            <Link className="button button--ghost" to="/dashboard">
              Voltar ao painel
            </Link>
          </div>
        </div>
      </SectionCard>
    </AppShell>
  );
}
