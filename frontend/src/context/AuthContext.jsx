import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { decodeJwtPayload, looksLikeHtmlDocument } from "../lib/utils";

const STORAGE_KEY = "hunter-ia-auth";
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const EMPTY_AUTH = { access: null, refresh: null, username: "" };
const SESSION_EXPIRED_MESSAGE = "Sua sessao expirou. Entre novamente para continuar.";

const AuthContext = createContext(null);

function buildUrl(path) {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${API_BASE_URL}${path}`;
}

function isFormDataBody(body) {
  if (!body) {
    return false;
  }

  if (typeof FormData !== "undefined" && body instanceof FormData) {
    return true;
  }

  const tag = Object.prototype.toString.call(body);
  if (tag === "[object FormData]") {
    return true;
  }

  return (
    typeof body === "object" &&
    typeof body.append === "function" &&
    typeof body.get === "function" &&
    typeof body.has === "function" &&
    typeof body.entries === "function"
  );
}

function withDefaultContentType(headers, body) {
  if (!body || headers.has("Content-Type") || isFormDataBody(body)) {
    return headers;
  }

  headers.set("Content-Type", "application/json");
  return headers;
}

async function performFetch(url, options) {
  try {
    return await fetch(url, options);
  } catch (error) {
    throw {
      code: "network_error",
      detail: error?.message ?? "Network error",
      message: error?.message ?? "Network error",
      cause: error
    };
  }
}

function isExpiredJwt(token, skewSeconds = 30) {
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) {
    return Boolean(token);
  }

  return Math.floor(Date.now() / 1000) >= Number(payload.exp) - skewSeconds;
}

function normalizeAuthState(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return EMPTY_AUTH;
  }

  const access = typeof value.access === "string" && value.access.trim() ? value.access : null;
  const refresh = typeof value.refresh === "string" && value.refresh.trim() ? value.refresh : null;
  const username = typeof value.username === "string" ? value.username.trim() : "";

  if (!access || !refresh || isExpiredJwt(refresh)) {
    return EMPTY_AUTH;
  }

  if (!decodeJwtPayload(access)) {
    return EMPTY_AUTH;
  }

  return { access, refresh, username };
}

function loadStoredAuth() {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return { auth: EMPTY_AUTH, notice: "" };
  }

  try {
    const parsed = JSON.parse(raw);
    const hadStoredTokens = Boolean(parsed?.access || parsed?.refresh);
    const auth = normalizeAuthState(parsed);
    return {
      auth,
      notice: hadStoredTokens && !auth.refresh ? SESSION_EXPIRED_MESSAGE : ""
    };
  } catch (error) {
    return {
      auth: EMPTY_AUTH,
      notice: "Nao foi possivel validar sua sessao salva. Entre novamente para continuar."
    };
  }
}

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    try {
      return await response.json();
    } catch (error) {
      return {
        code: "invalid_json_response",
        detail: "",
        response_content_type: contentType,
        response_is_invalid_json: true
      };
    }
  }

  const text = await response.text();
  if (!text) {
    return null;
  }

  return {
    detail: text,
    response_content_type: contentType,
    response_is_html: contentType.includes("text/html") || looksLikeHtmlDocument(text)
  };
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
  const isStructuredPayload = normalized && typeof normalized === "object" && !Array.isArray(normalized);
  const responseIsHtml = Boolean(isStructuredPayload && normalized.response_is_html);
  const responseIsInvalidJson = Boolean(isStructuredPayload && normalized.response_is_invalid_json);
  const shouldHideRawDetail =
    responseIsHtml ||
    responseIsInvalidJson ||
    (response.status >= 500 && !(isStructuredPayload && normalized.code));

  if (shouldHideRawDetail) {
    return {
      status: response.status,
      code: normalized?.code ?? (responseIsHtml ? "html_error_response" : "invalid_json_response"),
      detail: fallbackMessage,
      message: fallbackMessage
    };
  }

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
  const initialAuthState = useMemo(() => loadStoredAuth(), []);
  const [auth, setAuth] = useState(initialAuthState.auth);
  const [sessionNotice, setSessionNotice] = useState(initialAuthState.notice);
  const [bootstrapped, setBootstrapped] = useState(false);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
  }, [auth]);

  useEffect(() => {
    setBootstrapped(true);
  }, []);

  function clearAuth(notice = "") {
    setAuth(EMPTY_AUTH);
    setSessionNotice(notice);
  }

  async function refreshAccessToken(currentRefreshToken) {
    const refreshToken = currentRefreshToken ?? auth.refresh;
    if (!refreshToken) {
      clearAuth(SESSION_EXPIRED_MESSAGE);
      throw {
        code: "session_expired",
        detail: SESSION_EXPIRED_MESSAGE,
        message: SESSION_EXPIRED_MESSAGE
      };
    }

    if (isExpiredJwt(refreshToken, 0)) {
      clearAuth(SESSION_EXPIRED_MESSAGE);
      throw {
        code: "session_expired",
        detail: SESSION_EXPIRED_MESSAGE,
        message: SESSION_EXPIRED_MESSAGE
      };
    }

    const response = await performFetch(buildUrl("/api/token/refresh/"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: refreshToken })
    });
    const payload = await parseResponse(response);

    if (!response.ok || !payload?.access) {
      clearAuth(SESSION_EXPIRED_MESSAGE);
      throw buildHttpError(response, payload, SESSION_EXPIRED_MESSAGE);
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
    withDefaultContentType(headers, options.body);

    if (auth.access) {
      headers.set("Authorization", `Bearer ${auth.access}`);
    }

    const response = await performFetch(buildUrl(path), {
      ...options,
      headers
    });

    if (response.status === 401 && auth.refresh && retry) {
      const nextAccess = await refreshAccessToken(auth.refresh);
      const retryHeaders = new Headers(options.headers ?? {});
      withDefaultContentType(retryHeaders, options.body);

      retryHeaders.set("Authorization", `Bearer ${nextAccess}`);

      const retriedResponse = await performFetch(buildUrl(path), {
        ...options,
        headers: retryHeaders
      });
      const retriedPayload = await parseResponse(retriedResponse);
      if (!retriedResponse.ok) {
        throw buildHttpError(retriedResponse, retriedPayload, "A requisicao falhou.");
      }
      return retriedPayload;
    }

    const payload = await parseResponse(response);
    if (!response.ok) {
      if (response.status === 401) {
        clearAuth(SESSION_EXPIRED_MESSAGE);
      }
      throw buildHttpError(response, payload, "A requisicao falhou.");
    }
    return payload;
  }

  async function login({ username, password }) {
    const response = await performFetch(buildUrl("/api/token/"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });

    const payload = await parseResponse(response);
    if (!response.ok || !payload?.access || !payload?.refresh) {
      throw buildHttpError(response, payload, "Credenciais invalidas.");
    }

    setAuth({
      access: payload.access,
      refresh: payload.refresh,
      username: payload.user?.username ?? username
    });
    setSessionNotice("");
    return payload;
  }

  async function signup({ username, password, password_confirm }) {
    const response = await performFetch(buildUrl("/api/auth/signup/"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, password_confirm })
    });

    const payload = await parseResponse(response);
    if (!response.ok || !payload?.access || !payload?.refresh) {
      throw buildHttpError(response, payload, "Nao foi possivel concluir seu cadastro.");
    }

    setAuth({
      access: payload.access,
      refresh: payload.refresh,
      username: payload.user?.username ?? username
    });
    setSessionNotice("");
    return payload;
  }

  function logout() {
    clearAuth("");
  }

  function clearSessionNotice() {
    setSessionNotice("");
  }

  const user = useMemo(() => {
    const tokenPayload = decodeJwtPayload(auth.access);
    return {
      id: tokenPayload?.user_id ?? null,
      username: auth.username || "Usuario",
      isAuthenticated: Boolean(auth.access && auth.refresh && !isExpiredJwt(auth.refresh, 0))
    };
  }, [auth.access, auth.refresh, auth.username]);

  const value = useMemo(
    () => ({
      auth,
      bootstrapped,
      isAuthenticated: user.isAuthenticated,
      user,
      sessionNotice,
      clearSessionNotice,
      login,
      signup,
      logout,
      request
    }),
    [auth, bootstrapped, user, sessionNotice],
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
