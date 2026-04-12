import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { decodeJwtPayload } from "../lib/utils";

const STORAGE_KEY = "hunter-ia-auth";
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

const AuthContext = createContext(null);

function buildUrl(path) {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${API_BASE_URL}${path}`;
}

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  return text ? { detail: text } : null;
}

function normalizeErrorPayload(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return payload;
  }

  if (payload.detail || payload.message) {
    return payload;
  }

  const messages = Object.entries(payload)
    .flatMap(([key, value]) => {
      if (Array.isArray(value)) {
        return value.map((item) => `${key}: ${item}`);
      }
      if (value && typeof value === "object") {
        return Object.values(value).flat().map((item) => `${key}: ${item}`);
      }
      if (value != null) {
        return `${key}: ${value}`;
      }
      return [];
    })
    .filter(Boolean);

  return messages.length ? { detail: messages.join(" ") } : payload;
}

function buildHttpError(response, payload, fallbackMessage) {
  const normalized = normalizeErrorPayload(payload);
  if (normalized && typeof normalized === "object" && !Array.isArray(normalized)) {
    return {
      status: response.status,
      ...normalized,
      message: normalized.message ?? normalized.detail ?? fallbackMessage
    };
  }

  return {
    status: response.status,
    detail: fallbackMessage,
    message: fallbackMessage
  };
}

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(() => {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { access: null, refresh: null, username: "" };
    }

    try {
      return JSON.parse(raw);
    } catch (error) {
      return { access: null, refresh: null, username: "" };
    }
  });
  const [bootstrapped, setBootstrapped] = useState(false);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
  }, [auth]);

  useEffect(() => {
    setBootstrapped(true);
  }, []);

  async function refreshAccessToken(currentRefreshToken) {
    const refreshToken = currentRefreshToken ?? auth.refresh;
    if (!refreshToken) {
      throw new Error("Sua sessão expirou.");
    }

    const response = await fetch(buildUrl("/api/token/refresh/"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: refreshToken })
    });
    const payload = await parseResponse(response);

    if (!response.ok || !payload?.access) {
      setAuth({ access: null, refresh: null, username: "" });
      throw buildHttpError(response, payload, "Não foi possível renovar a sessão.");
    }

    setAuth((previous) => ({
      ...previous,
      access: payload.access,
      refresh: payload.refresh ?? previous.refresh
    }));
    return payload.access;
  }

  async function request(path, options = {}, retry = true) {
    const headers = new Headers(options.headers ?? {});
    const isFormData = options.body instanceof FormData;

    if (!isFormData && !headers.has("Content-Type") && options.body) {
      headers.set("Content-Type", "application/json");
    }

    if (auth.access) {
      headers.set("Authorization", `Bearer ${auth.access}`);
    }

    const response = await fetch(buildUrl(path), {
      ...options,
      headers
    });

    if (response.status === 401 && auth.refresh && retry) {
      const nextAccess = await refreshAccessToken(auth.refresh);
      const retryHeaders = new Headers(options.headers ?? {});

      if (!isFormData && !retryHeaders.has("Content-Type") && options.body) {
        retryHeaders.set("Content-Type", "application/json");
      }

      retryHeaders.set("Authorization", `Bearer ${nextAccess}`);

      const retriedResponse = await fetch(buildUrl(path), {
        ...options,
        headers: retryHeaders
      });
      const retriedPayload = await parseResponse(retriedResponse);
      if (!retriedResponse.ok) {
        throw buildHttpError(retriedResponse, retriedPayload, "A requisição falhou.");
      }
      return retriedPayload;
    }

    const payload = await parseResponse(response);
    if (!response.ok) {
      throw buildHttpError(response, payload, "A requisição falhou.");
    }
    return payload;
  }

  async function login({ username, password }) {
    const response = await fetch(buildUrl("/api/token/"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });

    const payload = await parseResponse(response);
    if (!response.ok || !payload?.access || !payload?.refresh) {
      throw buildHttpError(response, payload, "Credenciais inválidas.");
    }

    setAuth({
      access: payload.access,
      refresh: payload.refresh,
      username
    });
    return payload;
  }

  function logout() {
    setAuth({ access: null, refresh: null, username: "" });
  }

  const user = useMemo(() => {
    const tokenPayload = decodeJwtPayload(auth.access);
    return {
      id: tokenPayload?.user_id ?? null,
      username: auth.username || "Usuário",
      isAuthenticated: Boolean(auth.access && auth.refresh)
    };
  }, [auth.access, auth.refresh, auth.username]);

  const value = useMemo(
    () => ({
      auth,
      bootstrapped,
      isAuthenticated: user.isAuthenticated,
      user,
      login,
      logout,
      request
    }),
    [auth, bootstrapped, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }
  return context;
}
