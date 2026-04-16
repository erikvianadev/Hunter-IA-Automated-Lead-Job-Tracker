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
    title: "Pronto para análise",
    description: "O texto principal do arquivo já está disponível para gerar análise e leitura de senioridade.",
    nextStep: "Você já pode abrir os insights ou atualizar o currículo com uma nova versão.",
    noticeTone: "success"
  },
  pending: {
    label: "Em processamento",
    tone: "warning",
    title: "Estamos preparando seu currículo",
    description: "O arquivo foi recebido e ainda está sendo organizado para liberar os insights.",
    nextStep: "Aguarde um instante e atualize a página para acompanhar o progresso.",
    noticeTone: "info"
  },
  processing: {
    label: "Em processamento",
    tone: "warning",
    title: "Estamos preparando seu currículo",
    description: "O arquivo foi recebido e ainda está sendo organizado para liberar os insights.",
    nextStep: "Aguarde um instante e atualize a página para acompanhar o progresso.",
    noticeTone: "info"
  },
  upload_too_large: {
    label: "Arquivo grande demais",
    tone: "warning",
    title: "O arquivo passou do limite permitido",
    description: "Recebemos o envio, mas o arquivo está acima do tamanho aceito para currículos.",
    nextStep: "Gere uma versão menor em PDF ou DOCX e tente novamente.",
    noticeTone: "warning"
  },
  invalid_file: {
    label: "Arquivo inválido",
    tone: "warning",
    title: "Não conseguimos validar esse arquivo",
    description: "O arquivo enviado não se comporta como um currículo PDF ou DOCX confiável.",
    nextStep: "Exporte novamente o currículo em PDF ou DOCX e envie uma nova versão.",
    noticeTone: "warning"
  },
  unsupported_file_type: {
    label: "Formato não suportado",
    tone: "warning",
    title: "Esse formato não entra na análise",
    description: "Aceitamos apenas currículos em PDF ou DOCX no fluxo atual.",
    nextStep: "Converta o arquivo para PDF ou DOCX antes de tentar novamente.",
    noticeTone: "warning"
  },
  failed: {
    label: "Precisa de correção",
    tone: "warning",
    title: "Não conseguimos aproveitar este arquivo",
    description: "A leitura não ficou boa o bastante para gerar insights com confiança.",
    nextStep: "Exporte novamente em PDF ou DOCX com estrutura mais limpa e envie outra versão.",
    noticeTone: "warning"
  },
  parsing_failed: {
    label: "Precisa de correção",
    tone: "warning",
    title: "Não conseguimos concluir a leitura",
    description: "O arquivo foi recebido, mas a leitura não ficou estável o bastante para liberar os próximos insights.",
    nextStep: "Exporte novamente em PDF ou DOCX com texto selecionável e tente outra versão.",
    noticeTone: "warning"
  },
  empty_text: {
    label: "Texto insuficiente",
    tone: "warning",
    title: "Encontramos pouco texto utilizável",
    description: "O arquivo foi enviado, mas não trouxe texto selecionável suficiente para análise.",
    nextStep: "Reexporte em PDF ou DOCX com texto selecionável e tente novamente.",
    noticeTone: "warning"
  },
  insufficient_text: {
    label: "Texto insuficiente",
    tone: "warning",
    title: "Ainda falta texto confiável",
    description: "A leitura encontrou pouco conteúdo útil para liberar análise, senioridade e match com segurança.",
    nextStep: "Adicione mais texto selecionável ao currículo e envie uma nova exportação.",
    noticeTone: "warning"
  },
  scanned_or_image_pdf: {
    label: "PDF escaneado",
    tone: "warning",
    title: "Esse PDF parece ser uma imagem",
    description: "O arquivo não trouxe texto selecionável suficiente para leitura automática.",
    nextStep: "Exporte o currículo como PDF com texto selecionável ou envie uma versão DOCX.",
    noticeTone: "warning"
  },
  unsupported_structure: {
    label: "Formato não suportado",
    tone: "warning",
    title: "Esse arquivo precisa de uma nova exportação",
    description: "A estrutura do documento não ficou estável o bastante para extrair o conteúdo corretamente.",
    nextStep: "Salve uma nova versão em PDF ou DOCX simples e envie novamente.",
    noticeTone: "warning"
  },
  unsupported_or_unsafe_structure: {
    label: "Estrutura não suportada",
    tone: "warning",
    title: "O arquivo não passou na validação estrutural",
    description: "Bloqueamos a leitura porque a estrutura do documento não ficou confiável para processamento seguro.",
    nextStep: "Reexporte o currículo a partir do editor original e tente novamente.",
    noticeTone: "warning"
  },
  parsing_timeout_or_budget_exceeded: {
    label: "Arquivo complexo demais",
    tone: "warning",
    title: "Interrompemos a leitura para manter o processamento seguro",
    description: "O arquivo ultrapassou os limites seguros de leitura definidos para esse fluxo.",
    nextStep: "Simplifique o documento, remova excesso de páginas ou elementos embutidos e envie outra exportação.",
    noticeTone: "warning"
  },
  blocked_security: {
    label: "Bloqueado por segurança",
    tone: "blocked",
    title: "Arquivo bloqueado por segurança",
    description: "Interrompemos o processamento para proteger sua conta e os próximos passos da plataforma.",
    nextStep: "Revise o arquivo, gere uma nova exportação confiável e tente novamente.",
    noticeTone: "blocked"
  },
  quarantined_or_blocked_by_policy: {
    label: "Bloqueado por segurança",
    tone: "blocked",
    title: "Arquivo bloqueado por política de segurança",
    description: "O processamento foi interrompido antes dos insights para preservar a segurança da ingestão.",
    nextStep: "Gere uma nova exportação limpa e tente novamente.",
    noticeTone: "blocked"
  }
};

const INSIGHT_LABELS = {
  analysis: "a análise do currículo",
  seniority: "a leitura de senioridade",
  report: "o insight premium"
};

const BILLING_FEATURE_LABELS = {
  dashboard: "Painel com progresso e prioridades",
  job_matching: "Match com vagas",
  multiple_resume_versions: "Múltiplas versões de currículo",
  premium_reports: "Relatórios premium",
  priority_support: "Atendimento prioritário",
  resume_analysis: "Análise de currículo",
  resume_comparison: "Comparação entre versões",
  resume_upload: "Envio de currículo",
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
      description: "Estamos validando este currículo antes de liberar os próximos insights.",
      nextStep: "Atualize a página em instantes para conferir o status mais recente.",
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
      title: "Insight disponível",
      description: `Já existe resultado para ${noun}.`,
      nextStep: "Revise os destaques abaixo para decidir o próximo ajuste."
    };
  }

  if (state === "missing") {
    return {
      label: "Ainda não gerado",
      tone: "muted",
      title: "Insight ainda não gerado",
      description: `Ainda não encontramos resultado para ${noun}.`,
      nextStep: "Use a ação correspondente quando quiser liberar esse resultado."
    };
  }

  if (state === "locked") {
    return {
      label: "Premium",
      tone: "premium",
      title: "Recurso premium",
      description: `O acesso a ${noun} faz parte do plano Premium.`,
      nextStep: "Faça upgrade para liberar a visão completa quando quiser."
    };
  }

  if (state === "blocked") {
    return {
      label: "Precisa de atenção",
      tone: "blocked",
      title: "Não foi possível liberar este insight",
      description: `Ainda não conseguimos carregar ${noun}.`,
      nextStep: "Revise o currículo e tente novamente com um arquivo mais limpo, se necessário."
    };
  }

  return {
    label: "Aguardando",
    tone: "muted",
    title: "Aguardando ação",
    description: `Assim que ${noun} estiver disponível, ele aparecerá aqui.`,
    nextStep: "Siga com o fluxo normal para liberar esse resultado."
  };
}

export function getProviderStatusPresentation(state) {
  if (state === "blocked") {
    return { label: "Bloqueado", tone: "blocked" };
  }

  if (state === "issue") {
    return { label: "Instável", tone: "warning" };
  }

  return { label: "Disponível", tone: "good" };
}

export function getBillingStatusPresentation(status) {
  const map = {
    active: { label: "Ativo", tone: "good" },
    canceled: { label: "Encerrado", tone: "muted" },
    expired: { label: "Expirado", tone: "muted" },
    free: { label: "Grátis", tone: "muted" },
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

export function getPriorityTone(priorityLabel) {
  if (priorityLabel === "Alta prioridade") {
    return "warning";
  }

  if (priorityLabel === "Media prioridade") {
    return "medium";
  }

  return "muted";
}

export function getMatchDecisionPresentation(match = {}) {
  const decisionClass = match.decision_class || match.reasoning?.decision_class;
  const decisionLabel = match.decision_label || match.reasoning?.decision_label;

  if (decisionClass === "aplicar_agora") {
    return {
      label: decisionLabel || "Aplicar agora",
      title: "Decisão coerente para agir",
      tone: "success"
    };
  }

  if (decisionClass === "aplicar_apos_ajustes") {
    return {
      label: decisionLabel || "Aplicar após ajustes",
      title: "Vale agir, mas com ajuste antes",
      tone: "warning"
    };
  }

  if (decisionClass === "fortalecer_curriculo_antes") {
    return {
      label: decisionLabel || "Fortalecer currículo antes",
      title: "A decisão mais coerente é preparar melhor o material",
      tone: "blocked"
    };
  }

  if ((match.match_score ?? 0) >= 80) {
    return {
      label: "Aplicar agora",
      title: "Boa aderência para priorizar",
      tone: "success"
    };
  }

  if ((match.match_score ?? 0) >= 60) {
    return {
      label: "Aplicar após ajustes",
      title: "Aderência promissora, com ajustes",
      tone: "warning"
    };
  }

  return {
    label: "Fortalecer currículo antes",
    title: "Aderência baixa neste momento",
    tone: "blocked"
  };
}

export function getJobsOverviewCardsPresentation(input = {}) {
  const jobsCount = Number.isFinite(input.jobsCount) ? input.jobsCount : 0;
  const metaLoading = Boolean(input.metaLoading);
  const workspaceStats = input.workspaceStats ?? {};
  const savedCount = Number.isFinite(workspaceStats.savedCount) ? workspaceStats.savedCount : 0;
  const applicationCount = Number.isFinite(workspaceStats.applicationCount) ? workspaceStats.applicationCount : 0;
  const matchCount = Number.isFinite(workspaceStats.matchCount) ? workspaceStats.matchCount : 0;

  return [
    {
      label: "Vagas no workspace",
      value: jobsCount,
      helper: jobsCount ? "Dentro dos filtros atuais" : "Busque vagas para montar sua shortlist inicial."
    },
    {
      label: "Vagas salvas",
      value: metaLoading ? "..." : savedCount,
      helper: savedCount ? "Prontas para revisão" : "Salve oportunidades para comparar com calma."
    },
    {
      label: "Candidaturas",
      value: metaLoading ? "..." : applicationCount,
      helper: applicationCount ? "Já em andamento" : "Marque vagas como aplicadas para acompanhar as etapas."
    },
    {
      label: "Matches gerados",
      value: metaLoading ? "..." : matchCount,
      helper: matchCount ? "Com visibilidade de aderência" : "Atualize a aderência para descobrir onde vale focar."
    }
  ];
}

export function getCheckoutResultPresentation(kind) {
  if (kind === "success") {
    return {
      title: "Checkout concluído",
      subtitle: "Estamos confirmando seu pagamento com segurança.",
      heading: "Pagamento recebido",
      message:
        "Recebemos a finalização do checkout. Seu plano pode levar alguns instantes para aparecer enquanto a confirmação termina.",
      nextStep: "Atualize a página de planos em breve para conferir o acesso liberado.",
      tone: "success"
    };
  }

  return {
    title: "Checkout cancelado",
    subtitle: "Nenhuma alteração foi aplicada ao seu plano.",
    heading: "Checkout interrompido",
    message: "Seu plano atual continua igual. Quando quiser, você pode revisar as opções e tentar novamente.",
    nextStep: "Volte para a página de planos para escolher outro momento ou outra opção.",
    tone: "info"
  };
}
