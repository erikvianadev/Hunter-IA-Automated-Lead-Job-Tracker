import { useState } from "react";
import { Link, Navigate } from "react-router-dom";

import { PasswordField } from "../components/PasswordField";
import { useAuth } from "../context/AuthContext";
import { getErrorMessage } from "../lib/utils";

export function LoginPage() {
  const { isAuthenticated, login, sessionNotice, clearSessionNotice } = useAuth();
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
    clearSessionNotice();

    try {
      await login(form);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Não foi possível entrar agora. Revise seus dados e tente novamente."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-layout">
      <div className="auth-panel auth-panel--hero">
        <span className="hero-chip">Entrada real, progresso confiável</span>
        <h1>Organize sua busca de emprego com mais clareza, ritmo e confiança.</h1>
        <p>
          O Hunter IA ajuda você a evoluir seu currículo, acompanhar cada candidatura
          e priorizar vagas com mais contexto sobre o que fazer agora.
        </p>
        <div className="hero-metrics">
          <article>
            <strong>Entrada simples e segura</strong>
            <span>Entre na sua conta e retome seu workspace sem depender de setup manual</span>
          </article>
          <article>
            <strong>Progresso em um só lugar</strong>
            <span>Currículos, vagas e candidaturas conectados em um fluxo prático</span>
          </article>
          <article>
            <strong>Premium quando fizer sentido</strong>
            <span>Desbloqueie comparações e diagnósticos mais profundos quando quiser avançar</span>
          </article>
        </div>
      </div>

      <div className="auth-panel auth-panel--form">
        <div className="form-card">
          <span className="form-card__eyebrow">Entrar</span>
          <h2>Bem-vindo de volta</h2>
          <p>Entre para continuar seu progresso com visibilidade sobre currículo, vagas e próximos passos.</p>

          {sessionNotice ? (
            <div className="notice notice--warning">
              <strong>Entre novamente</strong>
              <p>{sessionNotice}</p>
            </div>
          ) : null}

          <form className="stack" onSubmit={handleSubmit}>
            <label className="field">
              <span>Nome de usuário</span>
              <input
                value={form.username}
                onChange={(event) => setForm((previous) => ({ ...previous, username: event.target.value }))}
                placeholder="seu-usuario"
                autoComplete="username"
                required
              />
            </label>

            <PasswordField
              label="Senha"
              value={form.password}
              onChange={(event) => setForm((previous) => ({ ...previous, password: event.target.value }))}
              placeholder="Digite sua senha"
              autoComplete="current-password"
              required
            />

            {error ? (
              <div className="notice notice--blocked">
                <strong>Não foi possível entrar</strong>
                <p>{error}</p>
                <p>Revise seus dados. Se o problema continuar, tente novamente em instantes.</p>
              </div>
            ) : null}

            <button className="button button--primary" type="submit" disabled={submitting}>
              {submitting ? "Entrando..." : "Continuar"}
            </button>
          </form>

          <div className="auth-support">
            <span>Ainda não tem conta?</span>
            <Link to="/signup">Criar conta gratuita</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
