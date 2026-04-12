import { Link, useLocation } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { SectionCard } from "../components/SectionCard";

export function BillingResultPage({ kind }) {
  const location = useLocation();
  const isSuccess = kind === "success";
  const sessionId = new URLSearchParams(location.search).get("session_id");

  return (
    <AppShell
      title={isSuccess ? "Checkout concluído" : "Checkout cancelado"}
      subtitle="Confirme o resultado do pagamento e volte para o seu plano com segurança."
    >
      <SectionCard title={isSuccess ? "Pagamento finalizado" : "Checkout interrompido"}>
        <div className="detail-stack">
          <p>
            {isSuccess
              ? "O Stripe concluiu o redirecionamento. Atualize a página de planos para confirmar a assinatura após o processamento do webhook."
              : "Nenhuma mudança de assinatura foi concluída. Você pode revisar os planos e tentar novamente quando quiser."}
          </p>
          {sessionId ? <p className="muted-copy">Sessão de checkout: {sessionId}</p> : null}
          <div className="action-row">
            <Link className="button button--primary" to="/billing">
              Ir para planos
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
