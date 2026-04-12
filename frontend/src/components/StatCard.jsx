export function StatCard({ label, value, helper }) {
  return (
    <article className="stat-card">
      <span className="stat-card__label">{label}</span>
      <strong className="stat-card__value">{value ?? "-"}</strong>
      <span className="stat-card__helper">{helper ?? ""}</span>
    </article>
  );
}
