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
      setError(getErrorMessage(requestError, "Não foi possível carregar os detalhes do seu plano."));
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
      setFeedback("Redirecionando para o checkout seguro...");
      window.location.href = payload.checkout_url;
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Não foi possível iniciar o checkout."));
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
      setFeedback("As configurações de renovação foram atualizadas.");
      await loadOverview();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Não foi possível atualizar sua assinatura."));
    } finally {
      setBusyAction("");
    }
  }

  const subscription = overview?.subscription;

  return (
    <AppShell
      title="Planos"
      subtitle="Escolha o plano certo para liberar insights mais profundos e apoiar sua busca com mais confiança."
      actions={
        <button className="button button--ghost" type="button" onClick={loadOverview}>
          Atualizar planos
        </button>
      }
    >
      {error ? <div className="notice notice--error">{error}</div> : null}
      {feedback ? <div className="notice notice--success">{feedback}</div> : null}

      <section className="two-column-grid">
        <SectionCard
          title="Seu plano atual"
          subtitle="Veja o que está ativo hoje e quando o acesso atual será renovado."
          actions={
            subscription?.plan_code !== "free" ? (
              <button
                className="button button--ghost"
                type="button"
                disabled={busyAction === "cancel"}
                onClick={cancelSubscription}
              >
                {busyAction === "cancel" ? "Atualizando..." : "Desativar renovação"}
              </button>
            ) : null
          }
        >
          {loading ? <div className="loading-panel">Carregando detalhes do seu plano...</div> : null}
          {!loading && subscription ? (
            <div className="detail-stack">
              <div className="inline-meta">
                <strong>{subscription.plan_name}</strong>
                <StatusBadge value={subscription.status} />
                <StatusBadge value={subscription.billing_cycle} />
              </div>
              <p>
                {formatCurrency(subscription.price_amount, subscription.currency)} | Renovação{" "}
                {subscription.auto_renew ? "ativa" : "desativada"}
              </p>
              <p className="muted-copy">
                Iniciado em {formatDate(subscription.started_at)}
                {subscription.current_period_end ? ` | Ciclo atual termina em ${formatDate(subscription.current_period_end)}` : ""}
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
                  <strong>Última fatura</strong>
                  <p>
                    {formatCurrency(subscription.last_invoice.amount, subscription.last_invoice.currency)} |{" "}
                    {titleize(subscription.last_invoice.status)}
                  </p>
                </div>
              ) : null}
            </div>
          ) : null}
          {!loading && !subscription ? (
            <EmptyState
              title="Nenhum plano encontrado"
              description="Assim que sua assinatura estiver disponível, os detalhes vão aparecer aqui."
            />
          ) : null}
        </SectionCard>

        <SectionCard title="Depois do checkout" subtitle="Volte aqui após o pagamento para confirmar o plano e o acesso liberado.">
          <div className="detail-stack">
            <p>
              Página de sucesso: <code>/billing/success</code>
            </p>
            <p>
              Página de cancelamento: <code>/billing/cancel</code>
            </p>
            <p className="muted-copy">
              Checkout, validação do plano e acesso premium continuam sendo controlados com segurança pelo backend.
            </p>
          </div>
        </SectionCard>
      </section>

      <SectionCard title="Opções de upgrade" subtitle="Desbloqueie insights premium quando quiser análises mais profundas e comparações avançadas.">
        {loading ? <div className="loading-panel">Carregando planos disponíveis...</div> : null}
        {!loading && !overview?.plans?.length ? (
          <EmptyState
            title="Nenhum plano disponível agora"
            description="Verifique a configuração de cobrança e atualize esta página."
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
                    ? "Plano atual"
                    : busyAction === `${plan.code}-${plan.billing_cycle}`
                      ? "Abrindo checkout..."
                      : "Escolher este plano"}
                </button>
              </article>
            ))}
          </div>
        ) : null}
      </SectionCard>
    </AppShell>
  );
}
