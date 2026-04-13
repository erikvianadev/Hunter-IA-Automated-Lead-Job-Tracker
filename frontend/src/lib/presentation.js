import { titleize } from "./utils";

const SECURITY_PARSE_STATUSES = new Set([
  "blocked",
  "unsafe",
  "blocked_security",
  "security_blocked",
  "malicious"
]);

const RESUME_PARSE_PRESENTATIONS = {
  completed: {
    label: "Pronto",
    tone: "good",
    title: "Pronto para analise",
    description: "O texto principal do arquivo ja esta disponivel para gerar analise e leitura de senioridade.",
    nextStep: "Voce ja pode abrir os insights ou atualizar o curriculo com uma nova versao.",
    noticeTone: "success"
  },
  pending: {
    label: "Em processamento",
    tone: "warning",
    title: "Estamos preparando seu curriculo",
    description: "O arquivo foi recebido e ainda esta sendo organizado para liberar os insights.",
    nextStep: "Aguarde um instante e atualize a pagina para acompanhar o progresso.",
    noticeTone: "info"
  },
  processing: {
    label: "Em processamento",
    tone: "warning",
    title: "Estamos preparando seu curriculo",
    description: "O arquivo foi recebido e ainda esta sendo organizado para liberar os insights.",
    nextStep: "Aguarde um instante e atualize a pagina para acompanhar o progresso.",
    noticeTone: "info"
  },
  failed: {
    label: "Precisa de correcao",
    tone: "warning",
    title: "Nao conseguimos aproveitar este arquivo",
    description: "A leitura nao ficou boa o bastante para gerar insights com confianca.",
    nextStep: "Exporte novamente em PDF ou DOCX com estrutura mais limpa e envie outra versao.",
    noticeTone: "warning"
  },
  empty_text: {
    label: "Texto insuficiente",
    tone: "warning",
    title: "Encontramos pouco texto utilizavel",
    description: "O arquivo foi enviado, mas nao trouxe texto selecionavel suficiente para analise.",
    nextStep: "Reexporte em PDF ou DOCX com texto selecionavel e tente novamente.",
    noticeTone: "warning"
  },
  unsupported_structure: {
    label: "Formato nao suportado",
    tone: "warning",
    title: "Esse arquivo precisa de uma nova exportacao",
    description: "A estrutura do documento nao ficou estavel o bastante para extrair o conteudo corretamente.",
    nextStep: "Salve uma nova versao em PDF ou DOCX simples e envie novamente.",
    noticeTone: "warning"
  },
  blocked_security: {
    label: "Bloqueado por seguranca",
    tone: "blocked",
    title: "Arquivo bloqueado por seguranca",
    description: "Interrompemos o processamento para proteger sua conta e os proximos passos da plataforma.",
    nextStep: "Revise o arquivo, gere uma nova exportacao confiavel e tente novamente.",
    noticeTone: "blocked"
  }
};

const INSIGHT_LABELS = {
  analysis: "a analise do curriculo",
  seniority: "a leitura de senioridade",
  report: "o insight premium"
};

export function getResumeParsePresentation(parseStatus, options = {}) {
  const { hasUsableText = true } = options;

  if (SECURITY_PARSE_STATUSES.has(parseStatus)) {
    return RESUME_PARSE_PRESENTATIONS.blocked_security;
  }

  if (parseStatus === "completed" && !hasUsableText) {
    return RESUME_PARSE_PRESENTATIONS.empty_text;
  }

  return (
    RESUME_PARSE_PRESENTATIONS[parseStatus] ?? {
      label: titleize(parseStatus),
      tone: "muted",
      title: "Acompanhando o processamento",
      description: "Estamos validando este curriculo antes de liberar os proximos insights.",
      nextStep: "Atualize a pagina em instantes para conferir o status mais recente.",
      noticeTone: "info"
    }
  );
}

export function getResumeInsightPresentation(kind, state) {
  const noun = INSIGHT_LABELS[kind] ?? "este insight";

  if (state === "ready") {
    return {
      label: "Pronto",
      tone: "good",
      title: "Insight disponivel",
      description: `Ja existe resultado para ${noun}.`,
      nextStep: "Revise os destaques abaixo para decidir o proximo ajuste."
    };
  }

  if (state === "missing") {
    return {
      label: "Ainda nao gerado",
      tone: "muted",
      title: "Insight ainda nao gerado",
      description: `Ainda nao encontramos resultado para ${noun}.`,
      nextStep: "Use a acao correspondente quando quiser liberar esse resultado."
    };
  }

  if (state === "locked") {
    return {
      label: "Premium",
      tone: "premium",
      title: "Recurso premium",
      description: `O acesso a ${noun} faz parte do plano Premium.`,
      nextStep: "Faça upgrade para liberar a visao completa quando quiser."
    };
  }

  if (state === "blocked") {
    return {
      label: "Precisa de atencao",
      tone: "blocked",
      title: "Nao foi possivel liberar este insight",
      description: `Ainda nao conseguimos carregar ${noun}.`,
      nextStep: "Revise o curriculo e tente novamente com um arquivo mais limpo, se necessario."
    };
  }

  return {
    label: "Aguardando",
    tone: "muted",
    title: "Aguardando acao",
    description: `Assim que ${noun} estiver disponivel, ele aparecera aqui.`,
    nextStep: "Siga com o fluxo normal para liberar esse resultado."
  };
}

export function getProviderStatusPresentation(state) {
  if (state === "blocked") {
    return { label: "Bloqueado", tone: "blocked" };
  }

  if (state === "issue") {
    return { label: "Instavel", tone: "warning" };
  }

  return { label: "Disponivel", tone: "good" };
}

export function getBillingStatusPresentation(status) {
  const map = {
    active: { label: "Ativo", tone: "good" },
    paid: { label: "Pago", tone: "good" },
    trialing: { label: "Em teste", tone: "warning" },
    incomplete: { label: "Pagamento pendente", tone: "warning" },
    incomplete_expired: { label: "Checkout expirado", tone: "warning" },
    past_due: { label: "Pagamento pendente", tone: "warning" },
    canceled: { label: "Encerrado", tone: "muted" },
    unpaid: { label: "Sem pagamento", tone: "blocked" },
    free: { label: "Gratis", tone: "muted" }
  };

  return map[status] ?? { label: titleize(status), tone: "muted" };
}

export function getMatchNoticeTone(score) {
  if (score >= 80) {
    return "success";
  }

  if (score >= 60) {
    return "warning";
  }

  return "blocked";
}

export function getCheckoutResultPresentation(kind) {
  if (kind === "success") {
    return {
      title: "Checkout concluido",
      subtitle: "Estamos confirmando seu pagamento com seguranca.",
      heading: "Pagamento recebido",
      message:
        "Recebemos a finalizacao do checkout. Seu plano pode levar alguns instantes para aparecer enquanto a confirmacao termina.",
      nextStep: "Atualize a pagina de planos em breve para conferir o acesso liberado.",
      tone: "success"
    };
  }

  return {
    title: "Checkout cancelado",
    subtitle: "Nenhuma alteracao foi aplicada ao seu plano.",
    heading: "Checkout interrompido",
    message: "Seu plano atual continua igual. Quando quiser, voce pode revisar as opcoes e tentar novamente.",
    nextStep: "Volte para a pagina de planos para escolher outro momento ou outra opcao.",
    tone: "info"
  };
}
