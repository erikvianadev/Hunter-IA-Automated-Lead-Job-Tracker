export function EmptyState({ eyebrow, title, description, nextStep, action, secondaryAction }) {
  return (
    <div className="empty-state">
      {eyebrow ? <span className="empty-state__eyebrow">{eyebrow}</span> : null}
      <h3>{title}</h3>
      <p>{description}</p>
      {nextStep ? (
        <div className="empty-state__next-step">
          <strong>O que fazer agora</strong>
          <p>{nextStep}</p>
        </div>
      ) : null}
      {action || secondaryAction ? (
        <div className="action-row action-row--wrap">
          {action}
          {secondaryAction}
        </div>
      ) : null}
    </div>
  );
}
