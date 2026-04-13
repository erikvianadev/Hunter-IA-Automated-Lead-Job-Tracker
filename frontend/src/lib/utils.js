export function cn(...values) {
  return values.filter(Boolean).join(" ");
}

const DIRECT_LABELS = {
  active: "Ativo",
  completed: "Concluído",
  paid: "Pago",
  applied: "Aplicada",
  offer: "Oferta",
  interview: "Entrevista",
  monthly: "Mensal",
  yearly: "Anual",
  processing: "Processando",
  pending: "Pendente",
  saved: "Salva",
  free: "Grátis",
  archived: "Arquivada",
  canceled: "Cancelada",
  rejected: "Rejeitada",
  failed: "Falhou",
  empty_text: "Sem texto legível",
  unsupported_structure: "Estrutura não suportada",
  blocked: "Bloqueado",
  issue: "Atenção",
  healthy: "Estável",
  ready: "Pronto",
  missing: "Não gerado",
  locked: "Premium",
  priority_high: "Prioridade alta",
  priority_medium: "Prioridade média",
  priority_low: "Prioridade baixa",
  junior: "Júnior",
  mid: "Pleno",
  senior: "Sênior",
  high: "Alta",
  medium: "Média",
  low: "Baixa",
  system: "Sistema",
  light: "Claro",
  dark: "Escuro",
  success: "Sucesso",
  cancel: "Cancelado"
};

const CHUNK_LABELS = {
  active: "Ativo",
  completed: "Concluído",
  paid: "Pago",
  applied: "Aplicada",
  offer: "Oferta",
  interview: "Entrevista",
  monthly: "Mensal",
  yearly: "Anual",
  processing: "Processando",
  pending: "Pendente",
  saved: "Salva",
  free: "Grátis",
  archived: "Arquivada",
  canceled: "Cancelada",
  rejected: "Rejeitada",
  failed: "Falhou",
  junior: "Júnior",
  mid: "Pleno",
  senior: "Sênior",
  high: "Alta",
  medium: "Média",
  low: "Baixa",
  score: "Score",
  fit: "Aderência",
  priority: "Prioridade",
  role: "Vaga",
  company: "Empresa",
  location: "Local",
  system: "Sistema",
  light: "Claro",
  dark: "Escuro"
};

export function formatDate(value) {
  if (!value) {
    return "Sem data";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(date);
}

export function formatShortDate(value) {
  if (!value) {
    return "Sem data";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "medium"
  }).format(date);
}

export function formatRelativeDate(value) {
  if (!value) {
    return "Sem atualização recente";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

  if (Math.abs(diffDays) < 1) {
    return "Hoje";
  }

  if (Math.abs(diffDays) < 30) {
    return new Intl.RelativeTimeFormat("pt-BR", { numeric: "auto" }).format(diffDays, "day");
  }

  return formatShortDate(value);
}

export function formatCurrency(amount, currency = "BRL") {
  const numeric = Number(amount);
  if (Number.isNaN(numeric)) {
    return amount ?? "-";
  }

  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency
  }).format(numeric);
}

export function titleize(value) {
  if (!value) {
    return "-";
  }

  if (DIRECT_LABELS[value]) {
    return DIRECT_LABELS[value];
  }

  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((chunk) => {
      if (CHUNK_LABELS[chunk]) {
        return CHUNK_LABELS[chunk];
      }

      return chunk[0].toUpperCase() + chunk.slice(1);
    })
    .join(" ");
}

export function decodeJwtPayload(token) {
  if (!token) {
    return null;
  }

  try {
    const encoded = token.split(".")[1];
    if (!encoded) {
      return null;
    }

    const base64 = encoded.replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(window.atob(base64));
  } catch (error) {
    return null;
  }
}

const USER_MESSAGE_PATTERNS = [
  {
    pattern: /(no active account found|unable to log in with provided credentials|invalid credentials)/i,
    message: "Usuario ou senha nao conferem. Revise seus dados e tente novamente."
  },
  {
    pattern: /(authentication credentials were not provided|not authenticated)/i,
    message: "Sua sessao nao foi reconhecida. Entre novamente para continuar."
  },
  {
    pattern: /(token is invalid|token is expired|token not valid|given token not valid)/i,
    message: "Sua sessao expirou. Entre novamente para continuar."
  },
  {
    pattern: /(failed to fetch|networkerror|network error)/i,
    message: "Nao foi possivel falar com o servidor agora. Tente novamente em instantes."
  },
  {
    pattern: /(unsupported media type|unsupported file|file type not supported)/i,
    message: "Esse arquivo nao pode ser processado aqui. Envie um PDF ou DOCX."
  },
  {
    pattern: /(permission denied|forbidden|not enough permissions)/i,
    message: "Voce nao tem acesso a essa acao agora."
  }
];

export function normalizeUserMessage(message) {
  if (!message || typeof message !== "string") {
    return message;
  }

  const clean = message.trim();
  if (!clean) {
    return clean;
  }

  const match = USER_MESSAGE_PATTERNS.find((item) => item.pattern.test(clean));
  if (match) {
    return match.message;
  }

  return clean;
}

export function getErrorMessage(error, fallback = "Algo deu errado.") {
  if (!error) {
    return normalizeUserMessage(fallback);
  }

  if (typeof error === "string") {
    return normalizeUserMessage(error);
  }

  if (error.detail) {
    return normalizeUserMessage(error.detail);
  }

  if (error.message) {
    return normalizeUserMessage(error.message);
  }

  return normalizeUserMessage(fallback);
}
