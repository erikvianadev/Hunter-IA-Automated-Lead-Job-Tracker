import { useState } from "react";
import { Link, Navigate } from "react-router-dom";

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
        <span className="hero-chip">Entrada real, progresso confiavel</span>
        <h1>Organize sua busca de emprego com mais clareza, ritmo e confianca.</h1>
        <p>
          O Hunter IA ajuda voce a evoluir seu curriculo, acompanhar cada candidatura
          e priorizar vagas com mais contexto sobre o que fazer agora.
        </p>
        <div className="hero-metrics">
          <article>
            <strong>Entrada simples e segura</strong>
            <span>Entre na sua conta e retome seu workspace sem depender de setup manual</span>
          </article>
          <article>
            <strong>Progresso em um so lugar</strong>
            <span>Curriculos, vagas e candidaturas conectados em um fluxo pratico</span>
          </article>
          <article>
            <strong>Premium quando fizer sentido</strong>
            <span>Desbloqueie comparacoes e diagnosticos mais profundos quando quiser avancar</span>
          </article>
        </div>
      </div>

      <div className="auth-panel auth-panel--form">
        <div className="form-card">
          <span className="form-card__eyebrow">Entrar</span>
          <h2>Bem-vindo de volta</h2>
          <p>Entre para continuar seu progresso com visibilidade sobre curriculo, vagas e proximos passos.</p>

          <form className="stack" onSubmit={handleSubmit}>
            <label className="field">
              <span>Nome de usuario</span>
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
                <p>Revise seus dados. Se o problema continuar, tente novamente em instantes.</p>
              </div>
            ) : null}

            <button className="button button--primary" type="submit" disabled={submitting}>
              {submitting ? "Entrando..." : "Continuar"}
            </button>
          </form>

          <div className="auth-support">
            <span>Ainda nao tem conta?</span>
            <Link to="/signup">Criar conta gratuita</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
