import { useState } from "react";
import { Link, Navigate } from "react-router-dom";

import { PasswordField } from "../components/PasswordField";
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
          "Não foi possível concluir seu cadastro agora. Revise os dados e tente novamente."
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
          Sua conta gratuita libera organização de currículos, leitura inicial do perfil,
          acompanhamento de candidaturas e um caminho mais confiável para evoluir.
        </p>
        <div className="hero-metrics">
          <article>
            <strong>Cadastro direto</strong>
            <span>Crie sua conta e entre no produto sem depender de setup manual</span>
          </article>
          <article>
            <strong>Primeiros passos claros</strong>
            <span>Envie seu currículo, acompanhe vagas e descubra o que fazer depois</span>
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
          <p>Use um nome de usuário simples e uma senha forte para entrar com segurança.</p>

          <form className="stack" onSubmit={handleSubmit}>
            <label className="field">
              <span>Nome de usuário</span>
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

            <PasswordField
              label="Senha"
              value={form.password}
              onChange={(event) => setForm((previous) => ({ ...previous, password: event.target.value }))}
              placeholder="Crie uma senha forte"
              autoComplete="new-password"
              required
            />

            <PasswordField
              label="Confirmar senha"
              value={form.password_confirm}
              onChange={(event) => setForm((previous) => ({ ...previous, password_confirm: event.target.value }))}
              placeholder="Repita sua senha"
              autoComplete="new-password"
              required
            />

            <div className="notice notice--info">
              <strong>O que acontece depois</strong>
              <p>Assim que o cadastro for concluído, você entra automaticamente e já pode enviar seu currículo.</p>
              <p>Use de 3 a 30 caracteres no nome de usuário e prefira uma senha forte.</p>
            </div>

            {error ? (
              <div className="notice notice--blocked">
                <strong>Não foi possível criar sua conta</strong>
                <p>{error}</p>
                <p>Revise os campos e tente novamente. Se continuar falhando, aguarde um instante e refaça o envio.</p>
              </div>
            ) : null}

            <button className="button button--primary" type="submit" disabled={submitting}>
              {submitting ? "Criando conta..." : "Criar conta e entrar"}
            </button>
          </form>

          <div className="auth-support">
            <span>Já tem conta?</span>
            <Link to="/login">Entrar</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
