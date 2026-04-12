import { cn } from "../lib/utils";

export function SectionCard({ title, subtitle, actions, className, children }) {
  return (
    <section className={cn("section-card", className)}>
      {(title || subtitle || actions) && (
        <div className="section-card__header">
          <div>
            {title ? <h2>{title}</h2> : null}
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
          {actions ? <div className="section-card__actions">{actions}</div> : null}
        </div>
      )}
      {children}
    </section>
  );
}
