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

const TRIAL_DAYS_BY_CYCLE = {
  trial_15: 15,
  trial_30: 30,
  trial_90: 90
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

const GRACE_STATES = new Set(["active_until_period_end", "grace_period"]);

function isInGracePeriod(subscription) {
  if (!subscription) return false;
  return (
    GRACE_STATES.has(subscription.access_state) ||
    (subscription.status === "canceled" && subscription.access_until != null)
  );
}

function getTrialDurationLabel(days) {
  if (days === 1) return "1 dia";
  return `${days} dias`;
}

function getTrialDays(cycle) {
  return TRIAL_DAYS_BY_CYCLE[cycle] ?? null;
}

function isTrialCycle(cycle) {
  return getTrialDays(cycle) != null;
}

function getAccessCycleLabel(cycle) {
  const days = getTrialDays(cycle);
  return days ? `${getTrialDurationLabel(days)} de acesso` : getBillingCycleLabel(cycle);
}

// ─── Sub-componentes ──────────────────────────────────────────────────────────

function GracePeriodBanner({ subscription, onRenew, isBusy }) {
  if (!isInGracePeriod(subscription)) return null;

  const daysLabel = subscription.access_until
    ? (() => {
        const diff = Math.ceil(
          (new Date(subscription.access_until) - Date.now()) / (1000 * 60 * 60 * 24)
        );
        return diff > 0 ? `Acesso válido por mais ${diff} dia${diff !== 1 ? "s" : ""}.` : "Acesso encerrado hoje.";
      })()
    : "Verifique a data de encerramento abaixo.";

  return (
    <div style={{
      display: "grid",
      gap: "12px",
      padding: "18px 22px",
      borderRadius: "var(--radius-lg)",
      border: "1.5px solid color-mix(in srgb, var(--accent) 40%, transparent)",
      background: "linear-gradient(135deg, color-mix(in srgb, var(--accent-soft) 78%, var(--surface-strong)), color-mix(in srgb, var(--surface-strong) 88%, transparent))",
      marginBottom: "4px"
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
        {/* Ícone de alerta */}
        <span style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: "32px",
          height: "32px",
          borderRadius: "50%",
          background: "color-mix(in srgb, var(--accent) 18%, transparent)",
          border: "1px solid color-mix(in srgb, var(--accent) 30%, transparent)",
          fontSize: "1rem",
          flexShrink: 0
        }}>⚠</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            <strong style={{ color: "var(--accent-strong)", fontSize: "1rem" }}>
              Acesso em encerramento
            </strong>
            <span className="status-badge tone-warning">Acesso temporário</span>
          </div>
          <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: "0.9rem" }}>
            {daysLabel} O acesso premium continua disponível até o fim do período já confirmado.
          </p>
        </div>
        {subscription.access_until && (
          <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.82rem", whiteSpace: "nowrap", flexShrink: 0 }}>
            Encerra em {formatDate(subscription.access_until)}
          </p>
        )}
      </div>
      <div className="action-row">
        <button
          className="button button--primary"
          type="button"
          disabled={isBusy}
          onClick={onRenew}
          style={{ flex: "0 1 auto" }}
        >
          {isBusy ? "Aguarde..." : "Ativar 30 dias"}
        </button>
        <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.82rem", alignSelf: "center" }}>
          A nova ativação mantém seu histórico, matches e currículos intactos.
        </p>
      </div>
    </div>
  );
}

function TrialPlanCard({ plan, isCurrent, busyAction, planErrors, onSubscribe }) {
  const actionKey = `${plan.code}-${plan.billing_cycle}`;
  const isBusy = busyAction === actionKey;
  const planError = planErrors?.[actionKey] || "";
  const planPresentation = getBillingPlanPresentation(plan);
  const days = getTrialDays(plan.billing_cycle);
  const durationLabel = days ? getTrialDurationLabel(days) : getBillingCycleLabel(plan.billing_cycle);
  const visibleFeatures = plan.features.map((f) => getBillingFeaturePresentation(f));

  return (
    <article
      className={plan.highlighted ? "plan-card is-highlighted" : "plan-card"}
      style={{
        position: "relative",
        ...(plan.highlighted ? {
          border: "1.5px solid color-mix(in srgb, var(--secondary) 35%, transparent)",
          background: "linear-gradient(180deg, color-mix(in srgb, var(--secondary-soft) 22%, var(--surface-elevated)), var(--surface-elevated))"
        } : {})
      }}
    >
      {plan.highlighted && (
        <div style={{
          position: "absolute",
          top: "-13px",
          left: "50%",
          transform: "translateX(-50%)",
          background: "linear-gradient(135deg, var(--secondary), var(--secondary-strong))",
          color: "#eef8f5",
          fontSize: "0.72rem",
          fontWeight: 700,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          padding: "4px 14px",
          borderRadius: "999px",
          whiteSpace: "nowrap"
        }}>
          {planPresentation.eyebrow}
        </div>
      )}

      <div className="plan-card__intro">
        <span className="plan-card__eyebrow">{planPresentation.eyebrow}</span>
        <div className="inline-meta">
          <strong>{planPresentation.label || getBillingPlanLabel(plan)}</strong>
          <span className="status-badge tone-medium">
            {durationLabel}
          </span>
          {isCurrent && <StatusBadge value="active" label="Acesso atual" />}
        </div>
        <p>{planPresentation.description}</p>
      </div>

      <div>
        <h3>{formatCurrency(plan.price_amount, plan.currency)}</h3>
        <p className="muted-copy">pagamento único · {durationLabel} Premium</p>
      </div>

      <div className="billing-value-note">
        <span>Melhor para</span>
        <p>{planPresentation.bestFor}</p>
      </div>

      <ul className="billing-feature-list">
        {visibleFeatures.slice(0, 5).map((feature) => (
          <li key={feature.label}>
            <strong>{feature.label}</strong>
            <span>{feature.description}</span>
          </li>
        ))}
        {visibleFeatures.length > 5 && (
          <li>
            <strong style={{ color: "var(--muted)" }}>
              + {visibleFeatures.length - 5} recursos adicionais
            </strong>
          </li>
        )}
      </ul>

      <button
        className={
          planError
            ? "button button--ghost"
            : plan.highlighted
            ? "button button--secondary"
            : "button button--ghost"
        }
        type="button"
        disabled={isCurrent || isBusy}
        onClick={() => onSubscribe(plan.code, plan.billing_cycle)}
        style={planError ? { borderColor: "var(--color-error, #dc2626)", color: "var(--color-error, #dc2626)" } : undefined}
      >
        {isBusy ? "Abrindo checkout..." : isCurrent ? "Ativo agora" : planError ? "Tentar novamente" : planPresentation.cta}
      </button>
      {planError && (
        <p style={{ marginTop: "8px", fontSize: "0.78rem", color: "var(--color-error, #dc2626)", lineHeight: 1.4 }}>
          {planError}
        </p>
      )}
    </article>
  );
}

// ─── Componente principal ─────────────────────────────────────────────────────

export function BillingPage() {
  const { request } = useAuth();
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [busyAction, setBusyAction] = useState("");
  const [planErrors, setPlanErrors] = useState({});

  async function loadOverview() {
    setLoading(true);
    setError("");
    try {
      const payload = await request("/hunter/api/billing/subscription/");
      setOverview(payload);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Não foi possível carregar os detalhes do seu acesso agora."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadOverview(); }, []);

  async function subscribe(planCode, billingCycle) {
    const actionKey = `${planCode}-${billingCycle}`;
    setBusyAction(actionKey);
    setPlanErrors((prev) => ({ ...prev, [actionKey]: "" }));
    setError("");
    setFeedback("");
    try {
      const payload = await request("/hunter/api/billing/subscribe/", {
        method: "POST",
        body: JSON.stringify({ plan_code: planCode, billing_cycle: billingCycle })
      });
      setFeedback("Abrindo o checkout seguro para confirmar seu acesso...");
      window.location.href = payload.checkout_url;
    } catch (requestError) {
      let planMessage = "Não foi possível abrir o checkout agora.";
      if (requestError?.code === "network_error" || !requestError?.status) {
        planMessage = "Sem conexão com o servidor. Verifique sua internet e tente novamente.";
      } else if (requestError.status >= 400 && requestError.status < 500) {
        planMessage = "Sessão expirada. Recarregue a página e tente novamente.";
      } else if (requestError.status >= 500) {
        planMessage = "Erro temporário no servidor de pagamentos. Tente novamente em alguns instantes.";
      }
      setPlanErrors((prev) => ({ ...prev, [actionKey]: planMessage }));
      setBusyAction("");
      // Auto-reactivate button after 5s so it never stays permanently disabled
      setTimeout(() => {
        setPlanErrors((prev) => ({ ...prev, [actionKey]: "" }));
      }, 5_000);
      return;
    }
    setBusyAction("");
  }

  async function cancelSubscription() {
    setBusyAction("cancel");
    setError("");
    setFeedback("");
    try {
      await request("/hunter/api/billing/cancel/", { method: "POST", body: JSON.stringify({}) });
      setFeedback("Acesso atualizado. O período atual continua válido até a data já confirmada.");
      await loadOverview();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Não foi possível atualizar seu acesso agora."));
    } finally {
      setBusyAction("");
    }
  }

  async function reactivateSubscription() {
    await subscribe("pro", "trial_30");
  }

  const subscription = overview?.subscription;
  const subscriptionStatus = subscription
    ? getBillingStatusPresentation(subscription.access_state || subscription.status || subscription.plan_code)
    : null;
  const lastInvoiceStatus = subscription?.last_invoice
    ? getBillingStatusPresentation(subscription.last_invoice.status)
    : null;
  const currentPlanPresentation = subscription
    ? getBillingPlanPresentation({ ...subscription, name: subscription.plan_name })
    : null;
  const canCancelSubscription =
    subscription?.plan_code !== "free" &&
    subscription?.status === "active" &&
    subscription?.auto_renew;
  const inGrace = isInGracePeriod(subscription);

  const availablePlans = overview?.plans ?? [];
  const currentTrialCycle = subscription?.billing_cycle;
  const isTrialPlan = isTrialCycle(currentTrialCycle);

  return (
    <AppShell
      title="Acesso Premium"
      subtitle="Escolha um período único de acesso para aprofundar diagnósticos, comparações e decisões antes de aplicar."
      actions={
        <button className="button button--ghost" type="button" onClick={loadOverview}>
          Atualizar acesso
        </button>
      }
    >
      {error && <div className="notice notice--blocked">{error}</div>}
      {feedback && <div className="notice notice--success">{feedback}</div>}

      {/* ── Banner de carência ────────────────────────────────────────── */}
      {subscription && (
        <GracePeriodBanner
          subscription={subscription}
          onRenew={reactivateSubscription}
          isBusy={busyAction === "pro-trial_30"}
        />
      )}

      {/* ── Acesso atual + Confirmação ────────────────────────────────── */}
      <section className="two-column-grid">
        <SectionCard
          title="Acesso atual"
          subtitle="Veja o período ativo hoje e até quando os recursos premium ficam liberados."
          actions={
            canCancelSubscription ? (
              <button
                className="button button--ghost"
                type="button"
                disabled={busyAction === "cancel"}
                onClick={cancelSubscription}
              >
                {busyAction === "cancel" ? "Atualizando..." : "Encerrar no fim do período"}
              </button>
            ) : null
          }
        >
          {loading && <div className="loading-panel">Carregando detalhes do seu acesso...</div>}
          {!loading && subscription && (
            <div className="detail-stack">
              <div className="inline-meta">
                <strong>{getBillingPlanLabel(subscription)}</strong>
                <StatusBadge
                  value={subscription.status || subscription.plan_code}
                  label={subscriptionStatus.label}
                  tone={subscriptionStatus.tone}
                />
                <StatusBadge
                  value={subscription.billing_cycle}
                  label={getAccessCycleLabel(subscription.billing_cycle)}
                />
                {inGrace && (
                  <span className="status-badge tone-warning">Em carência</span>
                )}
              </div>

              {currentPlanPresentation && (
                <div className="billing-value-note">
                  <span>{currentPlanPresentation.eyebrow}</span>
                  <p>{currentPlanPresentation.outcome}</p>
                </div>
              )}

              <p>
                {formatCurrency(subscription.price_amount, subscription.currency)}{" "}
                |{" "}
                {isTrialPlan
                  ? `${getAccessCycleLabel(subscription.billing_cycle)} · pagamento único`
                  : getBillingCycleLabel(subscription.billing_cycle)}
              </p>

              <p className="muted-copy">
                {subscription.started_at
                  ? `Iniciado em ${formatDate(subscription.started_at)}`
                  : "Disponível na sua conta"}
                {subscription.access_until
                  ? ` | Acesso válido até ${formatDate(subscription.access_until)}`
                  : ""}
              </p>

              {/* Notice contextual */}
              <div className={`notice notice--${
                inGrace ? "warning"
                  : subscriptionStatus.tone === "good" ? "success"
                  : subscriptionStatus.tone === "warning" ? "warning"
                  : subscriptionStatus.tone === "blocked" ? "blocked"
                  : "info"
              }`}>
                <strong>
                  {inGrace
                    ? "Seu acesso premium ainda está ativo"
                    : subscription.plan_code === "free"
                    ? "Você ainda não ativou um período premium"
                    : "Seu acesso premium segue ativo"}
                </strong>
                <p>
                  {inGrace
                    ? "O acesso premium permanece até o fim do período pago. Ative um novo período para manter continuidade nos diagnósticos e comparações."
                    : subscription.plan_code === "free"
                    ? "Escolha 15, 30 ou 90 dias quando quiser liberar diagnóstico premium, comparação de versões e suporte para decidir melhor antes de aplicar."
                    : "Durante o período ativo, você mantém diagnósticos profundos, comparação de versões e suporte para decidir melhor antes de aplicar."}
                </p>
              </div>

              {subscription.features?.length > 0 && (
                <div className="selection-pills">
                  {subscription.features.map((feature) => (
                    <span key={feature}>{getBillingFeatureLabel(feature)}</span>
                  ))}
                </div>
              )}

              {subscription.last_invoice && (
                <div className="detail-stack">
                  <strong>Última fatura</strong>
                  <p>
                    {formatCurrency(subscription.last_invoice.amount, subscription.last_invoice.currency)}{" "}
                    | {lastInvoiceStatus?.label ?? titleize(subscription.last_invoice.status)}
                  </p>
                </div>
              )}
            </div>
          )}
          {!loading && !subscription && (
            <EmptyState
              title="Nenhum acesso encontrado"
              description="Assim que um período premium estiver disponível, os detalhes vão aparecer aqui."
            />
          )}
        </SectionCard>

        <SectionCard
          title="Confirmação do pagamento"
          subtitle="A ativação é confirmada com segurança antes de liberar os recursos premium."
        >
          <div className="detail-stack">
            <div className="notice notice--info">
              <strong>Confirmação em alguns instantes</strong>
              <p>Depois do checkout, o acesso pode levar alguns instantes para aparecer atualizado.</p>
              <p>Se ainda não mudou, atualize esta página daqui a pouco.</p>
            </div>
            <p className="muted-copy">
              A cobrança e a validação final do acesso continuam protegidas pelo backend. Aqui você
              acompanha o resultado sem precisar interpretar códigos de checkout.
            </p>
          </div>
        </SectionCard>
      </section>

      {/* ── Períodos de acesso ───────────────────────────────────────── */}
      <SectionCard
        title="Escolha seu período"
        subtitle="Acesso premium por pagamento único, sem renovação automática: 15, 30 ou 90 dias."
      >
        {loading && <div className="loading-panel">Carregando períodos disponíveis...</div>}
        {!loading && !availablePlans.length && (
          <EmptyState
            title="Nenhum período disponível agora"
            description="Atualize a página em instantes para tentar novamente."
          />
        )}
        {!loading && availablePlans.length > 0 && (
          <div className="plan-grid">
            {availablePlans.map((plan) => (
              <TrialPlanCard
                key={plan.billing_cycle}
                plan={plan}
                isCurrent={!!(plan.is_current || (subscription && isTrialPlan && currentTrialCycle === plan.billing_cycle))}
                busyAction={busyAction}
                planErrors={planErrors}
                onSubscribe={subscribe}
              />
            ))}
          </div>
        )}

        {/* Tabela de comparação rápida entre trials */}
        {!loading && availablePlans.length > 0 && (
        <div className="billing-comparison">
          <strong className="billing-comparison__title">
            Comparação rápida
          </strong>
          <div className="billing-comparison__grid">
            {/* Header */}
            <span />
            {availablePlans.map((p) => (
              <strong className="billing-comparison__plan" key={p.billing_cycle}>
                {getAccessCycleLabel(p.billing_cycle)}
              </strong>
            ))}
            {/* Custo por dia */}
            <span className="billing-comparison__label muted-copy">Custo / dia</span>
            {availablePlans.map((p) => {
              const days = getTrialDays(p.billing_cycle);
              const costPerDay = days ? (parseFloat(p.price_amount) / days).toFixed(2) : null;
              return (
                <span className="billing-comparison__value" key={p.billing_cycle}>
                  {costPerDay ? `R$ ${costPerDay}` : "-"}
                </span>
              );
            })}
            {/* Recorrência */}
            <span className="billing-comparison__label muted-copy">Recorrência</span>
            {availablePlans.map((p) => (
              <span className="billing-comparison__value" key={p.billing_cycle}>
                <span className="status-badge tone-muted">Não</span>
              </span>
            ))}
            {/* Todos os recursos Pro */}
            <span className="billing-comparison__label muted-copy">Todos os recursos Pro</span>
            {availablePlans.map((p) => (
              <span className="billing-comparison__value" key={p.billing_cycle}>
                <span className="status-badge tone-good">Sim</span>
              </span>
            ))}
          </div>
        </div>
        )}
      </SectionCard>

    </AppShell>
  );
}
