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
      setError(getErrorMessage(requestError, "We could not sign you in right now."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-layout">
      <div className="auth-panel auth-panel--hero">
        <span className="hero-chip">Find better opportunities with more confidence</span>
        <h1>Turn resume progress into a clearer, calmer job search.</h1>
        <p>
          Hunter IA helps you improve your resume, organize every application, and
          unlock premium insights that make your next move easier to prioritize.
        </p>
        <div className="hero-metrics">
          <article>
            <strong>One focused workspace</strong>
            <span>Resume progress, opportunities, applications, and billing in one flow</span>
          </article>
          <article>
            <strong>Built for momentum</strong>
            <span>Keep improving your materials while staying on top of every opening</span>
          </article>
          <article>
            <strong>Premium when needed</strong>
            <span>Unlock richer resume comparisons and deeper employability insights</span>
          </article>
        </div>
      </div>

      <div className="auth-panel auth-panel--form">
        <div className="form-card">
          <span className="form-card__eyebrow">Sign in</span>
          <h2>Welcome back</h2>
          <p>Sign in to continue improving your resume and tracking your search.</p>

          <form className="stack" onSubmit={handleSubmit}>
            <label className="field">
              <span>Username</span>
              <input
                value={form.username}
                onChange={(event) => setForm((previous) => ({ ...previous, username: event.target.value }))}
                placeholder="your-username"
                autoComplete="username"
                required
              />
            </label>

            <label className="field">
              <span>Password</span>
              <input
                type="password"
                value={form.password}
                onChange={(event) => setForm((previous) => ({ ...previous, password: event.target.value }))}
                placeholder="Enter your password"
                autoComplete="current-password"
                required
              />
            </label>

            {error ? <div className="notice notice--error">{error}</div> : null}

            <button className="button button--primary" type="submit" disabled={submitting}>
              {submitting ? "Signing you in..." : "Continue"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
