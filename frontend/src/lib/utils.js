export function cn(...values) {
  return values.filter(Boolean).join(" ");
}

const DIRECT_LABELS = {
  active: "Ativo",
  analyzed: "Analisado",
  applied: "Aplicada",
  archived: "Arquivada",
  blocked: "Bloqueado",
  cancel: "Cancelado",
  canceled: "Cancelada",
  clarity: "Clareza",
  completed: "Concluido",
  dashboard: "Painel",
  dark: "Escuro",
  empty_text: "Sem texto legivel",
  error: "Falha temporaria",
  expired: "Expirado",
  failed: "Falhou",
  free: "Gratis",
  healthy: "Disponivel",
  high: "Alta",
  incomplete: "Pagamento pendente",
  incomplete_expired: "Checkout expirado",
  interview: "Entrevista",
  invalid_file: "Arquivo invalido",
  issue: "Atencao",
  job_matching: "Match com vagas",
  junior: "Junior",
  light: "Claro",
  locked: "Premium",
  low: "Baixa",
  market_fit: "Aderencia ao mercado",
  medium: "Media",
  mid: "Pleno",
  missing: "Nao gerado",
  monthly: "Mensal",
  multiple_resume_versions: "Multiplas versoes de curriculo",
  not_set: "Nao definido",
  offer: "Oferta",
  paid: "Pago",
  parsing_failed: "Falha na leitura",
  parsing_timeout_or_budget_exceeded: "Arquivo complexo demais",
  past_due: "Pagamento pendente",
  partial_success: "Sucesso parcial",
  pending: "Pendente",
  priority_1: "Prioridade 1",
  priority_2: "Prioridade 2",
  priority_3: "Prioridade 3",
  premium_reports: "Relatorios premium",
  priority_high: "Prioridade alta",
  priority_medium: "Prioridade media",
  priority_low: "Prioridade baixa",
  priority_support: "Atendimento prioritario",
  processing: "Em processamento",
  pro: "Pro",
  projects: "Projetos",
  quarantined_or_blocked_by_policy: "Bloqueado por politica",
  ready: "Pronto",
  rejected: "Rejeitada",
  resume_analysis: "Analise de curriculo",
  resume_comparison: "Comparacao entre versoes",
  resume_upload: "Envio de curriculo",
  saved: "Salva",
  scanned_or_image_pdf: "PDF escaneado",
  senior: "Senior",
  seniority_assessment: "Leitura de senioridade",
  structure: "Estrutura",
  success: "Sucesso",
  system: "Sistema",
  trialing: "Em teste",
  unpaid: "Sem pagamento",
  unsupported_file_type: "Formato nao suportado",
  unsupported_or_unsafe_structure: "Estrutura nao suportada",
  unsupported_structure: "Estrutura nao suportada",
  upload_too_large: "Arquivo grande demais",
  uploaded: "Enviado",
  yearly: "Anual"
};

const CHUNK_LABELS = {
  active: "Ativo",
  annual: "Anual",
  applied: "Aplicada",
  archived: "Arquivada",
  canceled: "Cancelada",
  company: "Empresa",
  completed: "Concluido",
  dark: "Escuro",
  failed: "Falhou",
  fit: "Aderencia",
  free: "Gratis",
  high: "Alta",
  issue: "Atencao",
  junior: "Junior",
  light: "Claro",
  location: "Local",
  low: "Baixa",
  medium: "Media",
  mid: "Pleno",
  monthly: "Mensal",
  paid: "Pago",
  pending: "Pendente",
  priority: "Prioridade",
  processing: "Processando",
  pro: "Pro",
  ready: "Pronto",
  rejected: "Rejeitada",
  role: "Vaga",
  saved: "Salva",
  score: "Score",
  senior: "Senior",
  system: "Sistema",
  title: "Titulo",
  unsupported: "Nao suportado",
  yearly: "Anual"
};

const SAFE_ERROR_CODE_MESSAGES = {
  html_error_response: "Nao foi possivel concluir essa etapa agora. Tente novamente em instantes.",
  invalid_file: "Nao conseguimos validar esse arquivo como um curriculo PDF ou DOCX confiavel.",
  invalid_json_response: "A resposta do servidor nao veio no formato esperado. Tente novamente em instantes.",
  job_search_failed: "Nao foi possivel atualizar a busca de vagas agora. Tente novamente em instantes.",
  unsupported_file_type: "Esse arquivo nao pode ser usado como curriculo. Envie um PDF ou DOCX.",
  upload_too_large: "O arquivo enviado passou do limite permitido para curriculos."
};

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
    message: "Esse arquivo nao pode ser usado como curriculo. Envie um PDF ou DOCX."
  },
  {
    pattern: /(permission denied|forbidden|not enough permissions)/i,
    message: "Voce nao tem acesso a essa acao agora."
  },
  {
    pattern: /(already exists|already taken|username.*not available)/i,
    message: "Esse nome de usuario nao esta disponivel no momento. Tente outra variacao."
  }
];

const INFRA_ERROR_PATTERNS = [
  /internal server error/i,
  /traceback/i,
  /<title>.*error/i,
  /nginx/i,
  /apache/i,
  /cloudflare/i
];

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
    return "Sem atualizacao recente";
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

  const raw = String(value).trim();
  if (!raw) {
    return "-";
  }

  const normalizedKey = raw.toLowerCase();
  if (DIRECT_LABELS[normalizedKey]) {
    return DIRECT_LABELS[normalizedKey];
  }

  return raw
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((chunk) => {
      const normalizedChunk = chunk.toLowerCase();
      if (CHUNK_LABELS[normalizedChunk]) {
        return CHUNK_LABELS[normalizedChunk];
      }

      return normalizedChunk[0].toUpperCase() + normalizedChunk.slice(1);
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

export function looksLikeHtmlDocument(message) {
  if (!message || typeof message !== "string") {
    return false;
  }

  const sample = message.trim().slice(0, 500);
  if (!sample) {
    return false;
  }

  return (
    /^<!doctype html/i.test(sample) ||
    /^<html[\s>]/i.test(sample) ||
    /<head[\s>]/i.test(sample) ||
    /<body[\s>]/i.test(sample) ||
    /<\/html>/i.test(sample) ||
    /<\/body>/i.test(sample)
  );
}

function getSafeMessageForCode(code) {
  if (!code) {
    return "";
  }

  return SAFE_ERROR_CODE_MESSAGES[String(code).trim().toLowerCase()] ?? "";
}

function getPrimaryFieldError(error) {
  const fieldErrors = error?.field_errors;
  if (!fieldErrors || typeof fieldErrors !== "object") {
    return "";
  }

  const firstEntry = Object.values(fieldErrors).find((value) => Array.isArray(value) && value.length);
  return typeof firstEntry?.[0] === "string" ? firstEntry[0] : "";
}

export function normalizeUserMessage(message) {
  if (!message || typeof message !== "string") {
    return message;
  }

  const clean = message.trim();
  if (!clean) {
    return clean;
  }

  if (looksLikeHtmlDocument(clean) || INFRA_ERROR_PATTERNS.some((pattern) => pattern.test(clean))) {
    return "Nao foi possivel concluir essa etapa agora. Tente novamente em instantes.";
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

  const codeMessage = getSafeMessageForCode(error.code);
  if (codeMessage) {
    return codeMessage;
  }

  const fieldError = getPrimaryFieldError(error);
  if (fieldError) {
    return normalizeUserMessage(fieldError);
  }

  if (error.detail) {
    return normalizeUserMessage(error.detail);
  }

  if (error.message) {
    return normalizeUserMessage(error.message);
  }

  return normalizeUserMessage(fallback);
}
