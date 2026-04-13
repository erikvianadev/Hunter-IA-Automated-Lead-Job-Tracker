import { useState } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { getErrorMessage } from "../lib/utils";

export function LoginPage() {
  const { isAuthenticated, login } = useAuth();
  const [form, setForm] = useState({
    username: "",
    password: ""
  });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      await login(form);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Nao foi possivel entrar agora. Revise seus dados e tente novamente."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-layout">
      <div className="auth-panel auth-panel--hero">
        <span className="hero-chip">Encontre vagas melhores com mais confianca</span>
        <h1>Transforme seu progresso em uma busca de emprego mais clara e organizada.</h1>
        <p>
          O Hunter IA ajuda voce a evoluir seu curriculo, acompanhar cada candidatura
          e usar insights premium para priorizar os proximos passos com mais seguranca.
        </p>
        <div className="hero-metrics">
          <article>
            <strong>Um workspace focado</strong>
            <span>Curriculos, vagas, candidaturas e plano no mesmo fluxo</span>
          </article>
          <article>
            <strong>Feito para manter ritmo</strong>
            <span>Melhore seus materiais enquanto acompanha cada oportunidade</span>
          </article>
          <article>
            <strong>Premium quando fizer sentido</strong>
            <span>Desbloqueie comparacoes mais ricas e insights mais profundos de empregabilidade</span>
          </article>
        </div>
      </div>

      <div className="auth-panel auth-panel--form">
        <div className="form-card">
          <span className="form-card__eyebrow">Entrar</span>
          <h2>Bem-vindo de volta</h2>
          <p>Entre para continuar evoluindo seu curriculo e acompanhando sua busca.</p>

          <form className="stack" onSubmit={handleSubmit}>
            <label className="field">
              <span>Usuario</span>
              <input
                value={form.username}
                onChange={(event) => setForm((previous) => ({ ...previous, username: event.target.value }))}
                placeholder="seu-usuario"
                autoComplete="username"
                required
              />
            </label>

            <label className="field">
              <span>Senha</span>
              <input
                type="password"
                value={form.password}
                onChange={(event) => setForm((previous) => ({ ...previous, password: event.target.value }))}
                placeholder="Digite sua senha"
                autoComplete="current-password"
                required
              />
            </label>

            {error ? (
              <div className="notice notice--blocked">
                <strong>Nao foi possivel entrar</strong>
                <p>{error}</p>
                <p>Confira usuario e senha. Se o problema continuar, tente novamente em instantes.</p>
              </div>
            ) : null}

            <button className="button button--primary" type="submit" disabled={submitting}>
              {submitting ? "Entrando..." : "Continuar"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
