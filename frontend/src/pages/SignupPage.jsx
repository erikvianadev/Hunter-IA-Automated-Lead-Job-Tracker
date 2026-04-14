import { useState } from "react";
import { Link, Navigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { getErrorMessage } from "../lib/utils";

export function SignupPage() {
  const { isAuthenticated, signup } = useAuth();
  const [form, setForm] = useState({
    username: "",
    password: "",
    password_confirm: ""
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
      await signup(form);
    } catch (requestError) {
      setError(
        getErrorMessage(
          requestError,
          "Nao foi possivel concluir seu cadastro agora. Revise os dados e tente novamente."
        )
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-layout">
      <div className="auth-panel auth-panel--hero">
        <span className="hero-chip">Comece com um plano claro</span>
        <h1>Crie sua conta e entre em um workspace pensado para uma busca de emprego real.</h1>
        <p>
          Sua conta gratuita libera organizacao de curriculos, leitura inicial do perfil,
          acompanhamento de candidaturas e um caminho mais confiavel para evoluir.
        </p>
        <div className="hero-metrics">
          <article>
            <strong>Cadastro direto</strong>
            <span>Crie sua conta e entre no produto sem depender de setup manual</span>
          </article>
          <article>
            <strong>Primeiros passos claros</strong>
            <span>Envie seu curriculo, acompanhe vagas e descubra o que fazer depois</span>
          </article>
          <article>
            <strong>Cresca no seu ritmo</strong>
            <span>Comece no gratuito e libere recursos premium quando eles fizerem sentido</span>
          </article>
        </div>
      </div>

      <div className="auth-panel auth-panel--form">
        <div className="form-card">
          <span className="form-card__eyebrow">Criar conta</span>
          <h2>Abrir meu acesso</h2>
          <p>Use um nome de usuario simples e uma senha forte para entrar com seguranca.</p>

          <form className="stack" onSubmit={handleSubmit}>
            <label className="field">
              <span>Nome de usuario</span>
              <input
                value={form.username}
                onChange={(event) => setForm((previous) => ({ ...previous, username: event.target.value }))}
                placeholder="seu-usuario"
                autoComplete="username"
                required
                minLength={3}
                maxLength={30}
              />
            </label>

            <label className="field">
              <span>Senha</span>
              <input
                type="password"
                value={form.password}
                onChange={(event) => setForm((previous) => ({ ...previous, password: event.target.value }))}
                placeholder="Crie uma senha forte"
                autoComplete="new-password"
                required
              />
            </label>

            <label className="field">
              <span>Confirmar senha</span>
              <input
                type="password"
                value={form.password_confirm}
                onChange={(event) => setForm((previous) => ({ ...previous, password_confirm: event.target.value }))}
                placeholder="Repita sua senha"
                autoComplete="new-password"
                required
              />
            </label>

            <div className="notice notice--info">
              <strong>O que acontece depois</strong>
              <p>Assim que o cadastro for concluido, voce entra automaticamente e ja pode enviar seu curriculo.</p>
              <p>Use de 3 a 30 caracteres no nome de usuario e prefira uma senha forte.</p>
            </div>

            {error ? (
              <div className="notice notice--blocked">
                <strong>Nao foi possivel criar sua conta</strong>
                <p>{error}</p>
                <p>Revise os campos e tente novamente. Se continuar falhando, aguarde um instante e refaca o envio.</p>
              </div>
            ) : null}

            <button className="button button--primary" type="submit" disabled={submitting}>
              {submitting ? "Criando conta..." : "Criar conta e entrar"}
            </button>
          </form>

          <div className="auth-support">
            <span>Ja tem conta?</span>
            <Link to="/login">Entrar</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
