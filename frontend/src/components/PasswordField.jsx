import { useId, useState } from "react";

export function PasswordField({ label, value, onChange, placeholder, autoComplete, required = false }) {
  const inputId = useId();
  const [isVisible, setIsVisible] = useState(false);
  const actionLabel = isVisible ? "Ocultar senha" : "Mostrar senha";

  return (
    <div className="field password-field">
      <label htmlFor={inputId}>{label}</label>
      <div className="password-field__control">
        <input
          id={inputId}
          type={isVisible ? "text" : "password"}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          autoComplete={autoComplete}
          required={required}
        />
        <button
          className="password-field__toggle"
          type="button"
          aria-label={actionLabel}
          aria-pressed={isVisible}
          title={actionLabel}
          onClick={() => setIsVisible((current) => !current)}
        >
          {isVisible ? "Ocultar" : "Mostrar"}
        </button>
      </div>
    </div>
  );
}
