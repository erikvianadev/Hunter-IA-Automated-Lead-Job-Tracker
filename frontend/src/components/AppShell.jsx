import { NavLink } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";

const navigation = [
  { to: "/dashboard", label: "Painel" },
  { to: "/resumes", label: "Currículos" },
  { to: "/jobs", label: "Vagas" },
  { to: "/applications", label: "Candidaturas" },
  { to: "/billing", label: "Planos" }
];

export function AppShell({ title, subtitle, actions, children }) {
  const { user, logout } = useAuth();
  const { themePreference, setThemePreference } = useTheme();

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="brand-lockup">
          <span className="brand-lockup__eyebrow">Seu copiloto de carreira</span>
          <h1>Hunter IA</h1>
          <p>Melhore seu currículo, organize sua busca e acompanhe vagas com mais clareza em um só lugar.</p>
        </div>

        <nav className="app-nav">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => (isActive ? "app-nav__link is-active" : "app-nav__link")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="theme-switcher">
          <label className="field">
            <span>Tema</span>
            <select value={themePreference} onChange={(event) => setThemePreference(event.target.value)}>
              <option value="system">Sistema</option>
              <option value="light">Claro</option>
              <option value="dark">Escuro</option>
            </select>
          </label>
        </div>

        <div className="app-sidebar__footer">
          <div>
            <strong>{user.username}</strong>
            <span>Conta #{user.id ?? "-"}</span>
          </div>
          <button className="button button--ghost" type="button" onClick={logout}>
            Sair
          </button>
        </div>
      </aside>

      <main className="app-main">
        <header className="page-header">
          <div>
            <span className="page-header__eyebrow">Workspace de carreira</span>
            <h2>{title}</h2>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
          {actions ? <div className="page-header__actions">{actions}</div> : null}
        </header>

        <div className="page-content">{children}</div>
      </main>
    </div>
  );
}
