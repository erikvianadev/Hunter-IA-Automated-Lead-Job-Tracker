import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

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

// ─── Constantes de trial ─────────────────────────────────────────────────────

const TRIAL_PLANS = [
  {
    code: "pro",
    billing_cycle: "trial_15",
    days: 15,
    label: "Acesso 15 dias",
    eyebrow: "Teste rápido",
    price_amount: "14.90",
    currency: "BRL",
    description: "Ideal para validar o fluxo completo antes de uma rodada intensa de candidaturas.",
    bestFor: "Faz sentido quando você quer testar o diagnóstico premium antes de assinar o ciclo completo.",
    cta: "Começar 15 dias",
    highlighted: false,
    features: [
      "resume_upload", "resume_analysis", "seniority_assessment",
      "job_matching", "dashboard", "premium_reports",
      "resume_comparison", "priority_support", "multiple_resume_versions"
    ]
  },
  {
    code: "pro",
    billing_cycle: "trial_30",
    days: 30,
    label: "Acesso 30 dias",
    eyebrow: "Mais popular no beta",
    price_amount: "24.90",
    currency: "BRL",
    description: "Tempo suficiente para uma rodada completa: currículo, matches, decisões e candidaturas.",
    bestFor: "Faz sentido quando você está ativamente buscando e quer o Premium por um ciclo completo.",
    cta: "Começar 30 dias",
    highlighted: true,
    features: [
      "resume_upload", "resume_analysis", "seniority_assessment",
      "job_matching", "dashboard", "premium_reports",
      "resume_comparison", "priority_support", "multiple_resume_versions"
    ]
  },
  {
    code: "pro",
    billing_cycle: "trial_90",
    days: 90,
    label: "Acesso 90 dias",
    eyebrow: "Melhor custo-benefício",
    price_amount: "59.90",
    currency: "BRL",
    description: "Para manter o premium ativo durante toda uma busca estratégica sem interrupções.",
    bestFor: "Faz sentido quando você está em transição de carreira e precisa de consistência por meses.",
    cta: "Começar 90 dias",
    highlighted: false,
    features: [
      "resume_upload", "resume_analysis", "seniority_assessment",
      "job_matching", "dashboard", "premium_reports",
      "resume_comparison", "priority_support", "multiple_resume_versions"
    ]
  }
];

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
              Assinatura em carência
            </strong>
            <span className="status-badge tone-warning">Cancelada — acesso temporário</span>
          </div>
          <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: "0.9rem" }}>
            {daysLabel} Seu plano foi cancelado, mas você ainda tem acesso completo até o fim do ciclo pago.
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
          {isBusy ? "Aguarde..." : "Reativar assinatura Pro"}
        </button>
        <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.82rem", alignSelf: "center" }}>
          Reativar mantém seu histórico, matches e currículos intactos.
        </p>
      </div>
    </div>
  );
}

function TrialPlanCard({ plan, isCurrent, busyAction, onSubscribe }) {
  const actionKey = `${plan.code}-${plan.billing_cycle}`;
  const isBusy = busyAction === actionKey;
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
          Mais popular no beta
        </div>
      )}

      <div className="plan-card__intro">
        <span className="plan-card__eyebrow">{plan.eyebrow}</span>
        <div className="inline-meta">
          <strong>{plan.label}</strong>
          {/* Badge de duração */}
          <span className="status-badge tone-medium">
            {getTrialDurationLabel(plan.days)}
          </span>
          {isCurrent && <StatusBadge value="active" label="Plano atual" />}
        </div>
        <p>{plan.description}</p>
      </div>

      <div>
        <h3>{formatCurrency(plan.price_amount, plan.currency)}</h3>
        <p className="muted-copy">pagamento único · {getTrialDurationLabel(plan.days)} de acesso Pro</p>
      </div>

      <div className="billing-value-note">
        <span>Melhor para</span>
        <p>{plan.bestFor}</p>
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
        className={plan.highlighted ? "button button--secondary" : "button button--ghost"}
        type="button"
        disabled={isCurrent || isBusy}
        onClick={() => onSubscribe(plan.code, plan.billing_cycle)}
      >
        {isBusy ? "Abrindo checkout..." : isCurrent ? "Ativo agora" : plan.cta}
      </button>
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

  useEffect(() => { loadOverview(); }, []);

  async function subscribe(planCode, billingCycle) {
    setBusyAction(`${planCode}-${billingCycle}`);
    setError("");
    setFeedback("");
    try {
      const payload = await request("/hunter/api/billing/subscribe/", {
        method: "POST",
        body: JSON.stringify({ plan_code: planCode, billing_cycle: billingCycle })
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
      await request("/hunter/api/billing/cancel/", { method: "POST", body: JSON.stringify({}) });
      setFeedback("Renovação automática desativada. Seu acesso atual continua válido até o fim do ciclo.");
      await loadOverview();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Não foi possível atualizar sua assinatura agora."));
    } finally {
      setBusyAction("");
    }
  }

  // Reativar assinatura: abre checkout do plano mensal
  async function reactivateSubscription() {
    await subscribe("pro", "monthly");
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

  // Determina o plano de trial atual (se houver)
  const currentTrialCycle = subscription?.billing_cycle;
  const isTrialPlan = currentTrialCycle?.startsWith("trial_");

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
      {error && <div className="notice notice--blocked">{error}</div>}
      {feedback && <div className="notice notice--success">{feedback}</div>}

      {/* ── Banner de carência ────────────────────────────────────────── */}
      {subscription && (
        <GracePeriodBanner
          subscription={subscription}
          onRenew={reactivateSubscription}
          isBusy={busyAction === "pro-monthly"}
        />
      )}

      {/* ── Plano atual + Confirmação ─────────────────────────────────── */}
      <section className="two-column-grid">
        <SectionCard
          title="Seu plano atual"
          subtitle="Veja o que está ativo hoje e como isso apoia sua busca neste momento."
          actions={
            canCancelSubscription ? (
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
          {loading && <div className="loading-panel">Carregando detalhes do seu plano...</div>}
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
                  label={
                    isTrialPlan
                      ? `Acesso ${subscription.billing_cycle.replace("trial_", "")} dias`
                      : getBillingCycleLabel(subscription.billing_cycle)
                  }
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
                  ? `Acesso por ${subscription.billing_cycle.replace("trial_", "")} dias · pagamento único`
                  : getBillingCycleLabel(subscription.billing_cycle)}
                {subscription.plan_code !== "free" && !isTrialPlan
                  ? ` | Renovação ${subscription.auto_renew ? "ativa" : "desativada"}`
                  : ""}
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
                    ? "Você já tem a base para organizar a busca"
                    : subscription.auto_renew
                    ? "Seu acesso premium segue ativo"
                    : "Sua renovação automática está desligada"}
                </strong>
                <p>
                  {inGrace
                    ? "A assinatura foi cancelada, mas o acesso premium permanece até o fim do ciclo pago. Reative para não perder continuidade nos diagnósticos e comparações."
                    : subscription.plan_code === "free"
                    ? "Use o gratuito para validar currículo, senioridade e matches. O upgrade passa a fazer sentido quando você precisa comparar versões e priorizar ações com mais profundidade."
                    : subscription.auto_renew
                    ? "Enquanto a renovação estiver ativa, você mantém diagnósticos profundos, comparação de versões e suporte para decidir melhor antes de aplicar."
                    : "Seu plano continua disponível até o fim do ciclo atual. Depois disso, o acesso volta para o nível correspondente."}
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
              title="Nenhum plano encontrado"
              description="Assim que sua assinatura estiver disponível, os detalhes vão aparecer aqui."
            />
          )}
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
              A cobrança e a validação final do acesso continuam protegidas pelo backend. Aqui você
              acompanha o resultado sem precisar interpretar códigos de checkout.
            </p>
          </div>
        </SectionCard>
      </section>

      {/* ── Planos recorrentes ────────────────────────────────────────── */}
      <SectionCard
        title="Opções de upgrade"
        subtitle="Compare os planos pelo que eles ajudam você a decidir, não só pelos recursos liberados."
      >
        {loading && <div className="loading-panel">Carregando planos disponíveis...</div>}
        {!loading && !overview?.plans?.length && (
          <EmptyState
            title="Nenhum plano disponível agora"
            description="Atualize a página em instantes para tentar novamente."
          />
        )}
        {!loading && overview?.plans?.length > 0 && (
          <div className="plan-grid">
            {overview.plans.map((plan) => {
              const planPresentation = getBillingPlanPresentation(plan);
              const visibleFeatures = plan.features.map((f) => getBillingFeaturePresentation(f));
              const actionKey = `${plan.code}-${plan.billing_cycle}`;
              const actionLabel = plan.is_current
                ? "Plano atual"
                : plan.code === "free"
                ? "Incluído no gratuito"
                : busyAction === actionKey
                ? "Abrindo checkout..."
                : planPresentation.cta;

              return (
                <article
                  className={plan.highlighted ? "plan-card is-highlighted" : "plan-card"}
                  key={`${plan.code}-${plan.billing_cycle}`}
                >
                  <div className="plan-card__intro">
                    <span className="plan-card__eyebrow">{planPresentation.eyebrow}</span>
                    <div className="inline-meta">
                      <strong>{planPresentation.label || getBillingPlanLabel(plan)}</strong>
                      {plan.is_current && <StatusBadge value="active" label="Plano atual" />}
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
        )}
      </SectionCard>

      {/* ── Planos de acesso antecipado (trial) ──────────────────────── */}
      <SectionCard
        title="Acesso antecipado — Escolha seu tempo"
        subtitle="Planos sem recorrência para quem quer testar o Premium por um período definido, sem compromisso de renovação automática."
      >
        {/* Aviso de contexto pre-beta */}
        <div className="notice notice--info" style={{ marginBottom: "16px" }}>
          <strong>Disponível durante o período de beta</strong>
          <p>
            Esses planos são pagamentos únicos com acesso total ao Premium por um tempo limitado.
            Sem renovação automática. Ideal para validar o produto antes de migrar para um plano recorrente.
          </p>
        </div>

        <div className="plan-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
          {TRIAL_PLANS.map((plan) => (
            <TrialPlanCard
              key={plan.billing_cycle}
              plan={plan}
              isCurrent={!!(subscription && isTrialPlan && currentTrialCycle === plan.billing_cycle)}
              busyAction={busyAction}
              onSubscribe={subscribe}
            />
          ))}
        </div>

        {/* Tabela de comparação rápida entre trials */}
        <div style={{
          marginTop: "20px",
          padding: "16px 20px",
          borderRadius: "var(--radius-md)",
          border: "1px solid var(--border)",
          background: "color-mix(in srgb, var(--surface-strong) 72%, transparent)"
        }}>
          <strong style={{ fontSize: "0.9rem", color: "var(--muted)", letterSpacing: "0.04em", textTransform: "uppercase" }}>
            Comparação rápida
          </strong>
          <div style={{
            display: "grid",
            gridTemplateColumns: "1fr repeat(3, auto)",
            gap: "8px 24px",
            marginTop: "12px",
            alignItems: "center"
          }}>
            {/* Header */}
            <span />
            {TRIAL_PLANS.map((p) => (
              <strong key={p.billing_cycle} style={{ fontSize: "0.9rem", textAlign: "center" }}>
                {getTrialDurationLabel(p.days)}
              </strong>
            ))}
            {/* Custo por dia */}
            <span className="muted-copy" style={{ fontSize: "0.88rem" }}>Custo / dia</span>
            {TRIAL_PLANS.map((p) => {
              const costPerDay = (parseFloat(p.price_amount) / p.days).toFixed(2);
              return (
                <span key={p.billing_cycle} style={{ textAlign: "center", fontSize: "0.88rem" }}>
                  R$ {costPerDay}
                </span>
              );
            })}
            {/* Renovação automática */}
            <span className="muted-copy" style={{ fontSize: "0.88rem" }}>Renovação automática</span>
            {TRIAL_PLANS.map((p) => (
              <span key={p.billing_cycle} style={{ textAlign: "center" }}>
                <span className="status-badge tone-muted" style={{ fontSize: "0.78rem" }}>Não</span>
              </span>
            ))}
            {/* Todos os recursos Pro */}
            <span className="muted-copy" style={{ fontSize: "0.88rem" }}>Todos os recursos Pro</span>
            {TRIAL_PLANS.map((p) => (
              <span key={p.billing_cycle} style={{ textAlign: "center" }}>
                <span className="status-badge tone-good" style={{ fontSize: "0.78rem" }}>Sim</span>
              </span>
            ))}
          </div>
        </div>
      </SectionCard>

    </AppShell>
  );
}
