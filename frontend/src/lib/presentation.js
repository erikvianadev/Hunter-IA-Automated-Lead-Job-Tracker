import { titleize } from "./utils";

const SECURITY_PARSE_STATUSES = new Set([
  "blocked",
  "unsafe",
  "blocked_security",
  "security_blocked",
  "malicious",
  "quarantined_or_blocked_by_policy"
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
  upload_too_large: {
    label: "Arquivo grande demais",
    tone: "warning",
    title: "O arquivo passou do limite permitido",
    description: "Recebemos o envio, mas o arquivo esta acima do tamanho aceito para curriculos.",
    nextStep: "Gere uma versao menor em PDF ou DOCX e tente novamente.",
    noticeTone: "warning"
  },
  invalid_file: {
    label: "Arquivo invalido",
    tone: "warning",
    title: "Nao conseguimos validar esse arquivo",
    description: "O arquivo enviado nao se comporta como um curriculo PDF ou DOCX confiavel.",
    nextStep: "Exporte novamente o curriculo em PDF ou DOCX e envie uma nova versao.",
    noticeTone: "warning"
  },
  unsupported_file_type: {
    label: "Formato nao suportado",
    tone: "warning",
    title: "Esse formato nao entra na analise",
    description: "Aceitamos apenas curriculos em PDF ou DOCX no fluxo atual.",
    nextStep: "Converta o arquivo para PDF ou DOCX antes de tentar novamente.",
    noticeTone: "warning"
  },
  failed: {
    label: "Precisa de correcao",
    tone: "warning",
    title: "Nao conseguimos aproveitar este arquivo",
    description: "A leitura nao ficou boa o bastante para gerar insights com confianca.",
    nextStep: "Exporte novamente em PDF ou DOCX com estrutura mais limpa e envie outra versao.",
    noticeTone: "warning"
  },
  parsing_failed: {
    label: "Precisa de correcao",
    tone: "warning",
    title: "Nao conseguimos concluir a leitura",
    description: "O arquivo foi recebido, mas a leitura nao ficou estavel o bastante para liberar os proximos insights.",
    nextStep: "Exporte novamente em PDF ou DOCX com texto selecionavel e tente outra versao.",
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
  insufficient_text: {
    label: "Texto insuficiente",
    tone: "warning",
    title: "Ainda falta texto confiavel",
    description: "A leitura encontrou pouco conteudo util para liberar analise, senioridade e match com seguranca.",
    nextStep: "Adicione mais texto selecionavel ao curriculo e envie uma nova exportacao.",
    noticeTone: "warning"
  },
  scanned_or_image_pdf: {
    label: "PDF escaneado",
    tone: "warning",
    title: "Esse PDF parece ser uma imagem",
    description: "O arquivo nao trouxe texto selecionavel suficiente para leitura automatica.",
    nextStep: "Exporte o curriculo como PDF com texto selecionavel ou envie uma versao DOCX.",
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
  unsupported_or_unsafe_structure: {
    label: "Estrutura nao suportada",
    tone: "warning",
    title: "O arquivo nao passou na validacao estrutural",
    description: "Bloqueamos a leitura porque a estrutura do documento nao ficou confiavel para processamento seguro.",
    nextStep: "Reexporte o curriculo a partir do editor original e tente novamente.",
    noticeTone: "warning"
  },
  parsing_timeout_or_budget_exceeded: {
    label: "Arquivo complexo demais",
    tone: "warning",
    title: "Interrompemos a leitura para manter o processamento seguro",
    description: "O arquivo ultrapassou os limites seguros de leitura definidos para esse fluxo.",
    nextStep: "Simplifique o documento, remova excesso de paginas ou elementos embutidos e envie outra exportacao.",
    noticeTone: "warning"
  },
  blocked_security: {
    label: "Bloqueado por seguranca",
    tone: "blocked",
    title: "Arquivo bloqueado por seguranca",
    description: "Interrompemos o processamento para proteger sua conta e os proximos passos da plataforma.",
    nextStep: "Revise o arquivo, gere uma nova exportacao confiavel e tente novamente.",
    noticeTone: "blocked"
  },
  quarantined_or_blocked_by_policy: {
    label: "Bloqueado por seguranca",
    tone: "blocked",
    title: "Arquivo bloqueado por politica de seguranca",
    description: "O processamento foi interrompido antes dos insights para preservar a seguranca da ingestao.",
    nextStep: "Gere uma nova exportacao limpa e tente novamente.",
    noticeTone: "blocked"
  }
};

const INSIGHT_LABELS = {
  analysis: "a analise do curriculo",
  seniority: "a leitura de senioridade",
  report: "o insight premium"
};

const BILLING_FEATURE_LABELS = {
  dashboard: "Painel com progresso e prioridades",
  job_matching: "Match com vagas",
  multiple_resume_versions: "Multiplas versoes de curriculo",
  premium_reports: "Relatorios premium",
  priority_support: "Atendimento prioritario",
  resume_analysis: "Analise de curriculo",
  resume_comparison: "Comparacao entre versoes",
  resume_upload: "Envio de curriculo",
  seniority_assessment: "Leitura de senioridade"
};

const BILLING_PLAN_LABELS = {
  free: "Plano gratuito",
  "pro annual": "Pro anual"
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
      nextStep: "Faca upgrade para liberar a visao completa quando quiser."
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
    canceled: { label: "Encerrado", tone: "muted" },
    expired: { label: "Expirado", tone: "muted" },
    free: { label: "Gratis", tone: "muted" },
    incomplete: { label: "Pagamento pendente", tone: "warning" },
    incomplete_expired: { label: "Checkout expirado", tone: "warning" },
    paid: { label: "Pago", tone: "good" },
    past_due: { label: "Pagamento pendente", tone: "warning" },
    trialing: { label: "Em teste", tone: "warning" },
    unpaid: { label: "Sem pagamento", tone: "blocked" }
  };

  return map[status] ?? { label: titleize(status), tone: "muted" };
}

export function getBillingFeatureLabel(feature) {
  return BILLING_FEATURE_LABELS[feature] ?? titleize(feature);
}

export function getBillingPlanLabel(plan) {
  if (!plan) {
    return "-";
  }

  const explicitName = String(plan.name ?? "").trim().toLowerCase();
  if (BILLING_PLAN_LABELS[explicitName]) {
    return BILLING_PLAN_LABELS[explicitName];
  }

  if (plan.code === "free") {
    return "Plano gratuito";
  }

  return titleize(plan.name || plan.code);
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
