import { useEffect, useState } from "react";

import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { SectionCard } from "../components/SectionCard";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import {
  getBillingCycleLabel,
  getBillingFeatureLabel,
  getBillingFeaturePresentation,
  getBillingPlanLabel,
  getBillingPlanPresentation,
  getBillingStatusPresentation
} from "../lib/presentation";
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
      setError(getErrorMessage(requestError, "Não foi possível carregar os detalhes do seu plano agora."));
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
      setFeedback("Abrindo o checkout seguro para confirmar seu upgrade...");
      window.location.href = payload.checkout_url;
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Não foi possível abrir o checkout agora."));
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
      setFeedback("Renovação automática desativada. Seu acesso atual continua válido até o fim do ciclo.");
      await loadOverview();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Não foi possível atualizar sua assinatura agora."));
    } finally {
      setBusyAction("");
    }
  }

  const subscription = overview?.subscription;
  const subscriptionStatus = subscription ? getBillingStatusPresentation(subscription.status || subscription.plan_code) : null;
  const lastInvoiceStatus = subscription?.last_invoice
    ? getBillingStatusPresentation(subscription.last_invoice.status)
    : null;
  const currentPlanPresentation = subscription
    ? getBillingPlanPresentation({ ...subscription, name: subscription.plan_name })
    : null;

  return (
    <AppShell
      title="Planos"
      subtitle="Escolha pelo resultado que você quer melhorar: decisões de currículo, priorização de vagas e clareza para aplicar."
      actions={
        <button className="button button--ghost" type="button" onClick={loadOverview}>
          Atualizar planos
        </button>
      }
    >
      {error ? <div className="notice notice--blocked">{error}</div> : null}
      {feedback ? <div className="notice notice--success">{feedback}</div> : null}

      <section className="two-column-grid">
        <SectionCard
          title="Seu plano atual"
          subtitle="Veja o que está ativo hoje e como isso apoia sua busca neste momento."
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
                <strong>{getBillingPlanLabel(subscription)}</strong>
                <StatusBadge
                  value={subscription.status || subscription.plan_code}
                  label={subscriptionStatus.label}
                  tone={subscriptionStatus.tone}
                />
                <StatusBadge value={subscription.billing_cycle} label={getBillingCycleLabel(subscription.billing_cycle)} />
              </div>
              {currentPlanPresentation ? (
                <div className="billing-value-note">
                  <span>{currentPlanPresentation.eyebrow}</span>
                  <p>{currentPlanPresentation.outcome}</p>
                </div>
              ) : null}
              <p>
                {formatCurrency(subscription.price_amount, subscription.currency)} | {getBillingCycleLabel(subscription.billing_cycle)}
                {subscription.plan_code !== "free" ? ` | Renovação ${subscription.auto_renew ? "ativa" : "desativada"}` : ""}
              </p>
              <p className="muted-copy">
                {subscription.started_at ? `Iniciado em ${formatDate(subscription.started_at)}` : "Disponível na sua conta"}
                {subscription.current_period_end ? ` | Ciclo atual termina em ${formatDate(subscription.current_period_end)}` : ""}
              </p>
              <div className={`notice notice--${subscriptionStatus.tone === "good" ? "success" : subscriptionStatus.tone === "warning" ? "warning" : subscriptionStatus.tone === "blocked" ? "blocked" : "info"}`}>
                <strong>
                  {subscription.plan_code === "free"
                    ? "Você já tem a base para organizar a busca"
                    : subscription.auto_renew
                      ? "Seu acesso premium segue ativo"
                      : "Sua renovação automática está desligada"}
                </strong>
                <p>
                  {subscription.plan_code === "free"
                    ? "Use o gratuito para validar currículo, senioridade e matches. O upgrade passa a fazer sentido quando você precisa comparar versões e priorizar ações com mais profundidade."
                    : subscription.auto_renew
                      ? "Enquanto a renovação estiver ativa, você mantém diagnósticos profundos, comparação de versões e suporte para decidir melhor antes de aplicar."
                      : "Seu plano continua disponível até o fim do ciclo atual. Depois disso, o acesso volta para o nível correspondente."}
                </p>
              </div>
              {subscription.features?.length ? (
                <div className="selection-pills">
                  {subscription.features.map((feature) => (
                    <span key={feature}>{getBillingFeatureLabel(feature)}</span>
                  ))}
                </div>
              ) : null}
              {subscription.last_invoice ? (
                <div className="detail-stack">
                  <strong>Ultima fatura</strong>
                  <p>
                    {formatCurrency(subscription.last_invoice.amount, subscription.last_invoice.currency)} |{" "}
                    {lastInvoiceStatus?.label ?? titleize(subscription.last_invoice.status)}
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

        <SectionCard
          title="Confirmação do pagamento"
          subtitle="O upgrade é confirmado com segurança antes de liberar os recursos premium."
        >
          <div className="detail-stack">
            <div className="notice notice--info">
              <strong>Confirmação em alguns instantes</strong>
              <p>Depois do checkout, o plano pode levar alguns instantes para aparecer atualizado.</p>
              <p>Se ainda não mudou, atualize esta página daqui a pouco.</p>
            </div>
            <p className="muted-copy">
              A cobrança e a validação final do acesso continuam protegidas pelo backend. Aqui você acompanha o resultado
              sem precisar interpretar códigos de checkout.
            </p>
          </div>
        </SectionCard>
      </section>

      <SectionCard
        title="Opções de upgrade"
        subtitle="Compare os planos pelo que eles ajudam você a decidir, não só pelos recursos liberados."
      >
        {loading ? <div className="loading-panel">Carregando planos disponíveis...</div> : null}
        {!loading && !overview?.plans?.length ? (
          <EmptyState
            title="Nenhum plano disponível agora"
            description="Atualize a página em instantes para tentar novamente."
          />
        ) : null}
        {!loading && overview?.plans?.length ? (
          <div className="plan-grid">
            {overview.plans.map((plan) => {
              const planPresentation = getBillingPlanPresentation(plan);
              const visibleFeatures = plan.features.map((feature) => getBillingFeaturePresentation(feature));
              const actionKey = `${plan.code}-${plan.billing_cycle}`;
              const actionLabel = plan.is_current
                ? "Plano atual"
                : plan.code === "free"
                  ? "Incluído no gratuito"
                  : busyAction === actionKey
                    ? "Abrindo checkout..."
                    : planPresentation.cta;

              return (
                <article className={plan.highlighted ? "plan-card is-highlighted" : "plan-card"} key={`${plan.code}-${plan.billing_cycle}`}>
                  <div className="plan-card__intro">
                    <span className="plan-card__eyebrow">{planPresentation.eyebrow}</span>
                    <div className="inline-meta">
                      <strong>{planPresentation.label || getBillingPlanLabel(plan)}</strong>
                      {plan.is_current ? <StatusBadge value="active" label="Plano atual" /> : null}
                    </div>
                    <p>{planPresentation.description}</p>
                  </div>
                  <div>
                    <h3>{formatCurrency(plan.price_amount, plan.currency)}</h3>
                    <p className="muted-copy">{getBillingCycleLabel(plan.billing_cycle)}</p>
                  </div>
                  <div className="billing-value-note">
                    <span>Melhor para</span>
                    <p>{planPresentation.bestFor}</p>
                  </div>
                  <ul className="billing-feature-list">
                    {visibleFeatures.map((feature) => (
                      <li key={feature.label}>
                        <strong>{feature.label}</strong>
                        <span>{feature.description}</span>
                      </li>
                    ))}
                  </ul>
                  <button
                    className={plan.highlighted ? "button button--primary" : "button button--secondary"}
                    type="button"
                    disabled={plan.is_current || plan.code === "free" || busyAction === actionKey}
                    onClick={() => subscribe(plan.code, plan.billing_cycle)}
                  >
                    {actionLabel}
                  </button>
                </article>
              );
            })}
          </div>
        ) : null}
      </SectionCard>
    </AppShell>
  );
}
