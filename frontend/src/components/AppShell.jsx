import { NavLink } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";

const navigation = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/resumes", label: "Resumes" },
  { to: "/jobs", label: "Jobs" },
  { to: "/applications", label: "Applications" },
  { to: "/billing", label: "Billing" }
];

export function AppShell({ title, subtitle, actions, children }) {
  const { user, logout } = useAuth();
  const { themePreference, setThemePreference } = useTheme();

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="brand-lockup">
          <span className="brand-lockup__eyebrow">Career growth companion</span>
          <h1>Hunter IA</h1>
          <p>Improve your resume, organize applications, and discover stronger opportunities in one place.</p>
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
            <span>Theme</span>
            <select value={themePreference} onChange={(event) => setThemePreference(event.target.value)}>
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </label>
        </div>

        <div className="app-sidebar__footer">
          <div>
            <strong>{user.username}</strong>
            <span>Account #{user.id ?? "-"}</span>
          </div>
          <button className="button button--ghost" type="button" onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="app-main">
        <header className="page-header">
          <div>
            <span className="page-header__eyebrow">Career workspace</span>
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
