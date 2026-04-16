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
  report: "o diagnóstico premium"
};

const BILLING_FEATURE_PRESENTATIONS = {
  dashboard: {
    label: "Painel de progresso",
    description: "Acompanhe prioridades, currículo ativo e próximos passos da busca."
  },
  job_matching: {
    label: "Aderência com vagas",
    description: "Compare seu currículo com oportunidades para decidir onde vale investir energia."
  },
  multiple_resume_versions: {
    label: "Versões para cada estratégia",
    description: "Mantenha variações do currículo por cargo, senioridade ou foco de candidatura."
  },
  premium_reports: {
    label: "Diagnóstico premium",
    description: "Receba uma leitura mais profunda de lacunas, prioridades e ações de maior impacto."
  },
  priority_support: {
    label: "Suporte prioritário",
    description: "Tenha prioridade quando precisar resolver dúvidas sobre uso e acesso."
  },
  resume_analysis: {
    label: "Análise do currículo",
    description: "Veja clareza, estrutura, aderência e sinais que fortalecem sua apresentação."
  },
  resume_comparison: {
    label: "Comparação entre versões",
    description: "Entenda qual versão comunica melhor sua experiência antes de aplicar."
  },
  resume_upload: {
    label: "Envio de currículo",
    description: "Use PDF ou DOCX como base para análises, senioridade e matches."
  },
  seniority_assessment: {
    label: "Leitura de senioridade",
    description: "Entenda o nível mais coerente para posicionar seu currículo e suas vagas."
  }
};

const BILLING_PLAN_LABELS = {
  free: "Plano gratuito",
  pro: "Pro",
  "pro annual": "Pro anual"
};

const BILLING_PLAN_PRESENTATIONS = {
  free: {
    eyebrow: "Base organizada",
    label: "Plano gratuito",
    description: "Para preparar a base da sua busca: enviar currículo, entender senioridade e começar a comparar vagas com mais clareza.",
    outcome: "Ajuda você a sair do achismo inicial e enxergar o que já está pronto para usar.",
    bestFor: "Comece aqui quando ainda está estruturando currículo, cargo-alvo e primeiras oportunidades.",
    cta: "Plano atual"
  },
  "pro-monthly": {
    eyebrow: "Mais decisão por candidatura",
    label: "Pro mensal",
    description: "Para transformar análise em decisões melhores: escolher a versão certa, priorizar ajustes e aprofundar o diagnóstico antes de aplicar.",
    outcome: "Ajuda você a decidir com mais confiança onde ajustar, qual versão usar e quais vagas merecem foco.",
    bestFor: "Faz sentido quando você já está comparando oportunidades ou quer acelerar uma rodada de candidaturas.",
    cta: "Melhorar meus resultados"
  },
  "pro-yearly": {
    eyebrow: "Rotina premium contínua",
    label: "Pro anual",
    description: "Para manter uma busca consistente ao longo do tempo, com diagnósticos profundos e comparações sempre que sua estratégia mudar.",
    outcome: "Ajuda você a manter evolução do currículo, priorização de vagas e aprendizado entre ciclos.",
    bestFor: "Faz sentido quando Hunter IA vira parte da sua rotina de carreira, não só de uma candidatura pontual.",
    cta: "Assinar o Pro anual"
  }
};

const BILLING_CYCLE_PRESENTATIONS = {
  free: "Sem cobrança",
  monthly: "Cobrança mensal",
  yearly: "Cobrança anual"
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
      title: "Resultado mais profundo no Premium",
      description: `O Premium libera ${noun} para transformar os dados do currículo em prioridades mais claras.`,
      nextStep: "Faça upgrade quando quiser comparar decisões, enxergar lacunas e agir com mais confiança."
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
  return getBillingFeaturePresentation(feature).label;
}

export function getBillingFeaturePresentation(feature) {
  return (
    BILLING_FEATURE_PRESENTATIONS[feature] ?? {
      label: titleize(feature),
      description: "Recurso incluído neste plano."
    }
  );
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

export function getBillingPlanPresentation(plan) {
  const planCode = plan?.code ?? "";
  const planName = String(plan?.name ?? "").trim().toLowerCase();
  const planKey = planCode === "pro" ? `pro-${plan?.billing_cycle}` : planCode || planName;
  const fallbackLabel = getBillingPlanLabel(plan);

  return (
    BILLING_PLAN_PRESENTATIONS[planKey] ??
    BILLING_PLAN_PRESENTATIONS[planName] ?? {
      eyebrow: "Plano",
      label: fallbackLabel,
      description: "Plano disponível para continuar sua jornada no Hunter IA.",
      outcome: "Ajuda você a manter o fluxo de carreira organizado.",
      bestFor: "Escolha quando fizer sentido para o seu momento atual.",
      cta: "Escolher este plano"
    }
  );
}

export function getBillingCycleLabel(cycle) {
  return BILLING_CYCLE_PRESENTATIONS[cycle] ?? titleize(cycle);
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
      title: "Upgrade em confirmação",
      subtitle: "Estamos validando o pagamento com segurança antes de liberar o acesso.",
      heading: "Pagamento recebido",
      message:
        "Recebemos a finalização do checkout. Em alguns instantes o plano aparece atualizado com os recursos do Premium.",
      nextStep: "Volte para Planos para confirmar o acesso e seguir para os diagnósticos mais profundos.",
      tone: "success"
    };
  }

  return {
    title: "Upgrade não concluído",
    subtitle: "Seu plano continua igual e nenhuma cobrança nova foi confirmada.",
    heading: "Upgrade interrompido",
    message: "Tudo bem pausar aqui. Seu plano atual segue ativo para continuar organizando currículo, vagas e decisões.",
    nextStep: "Quando o diagnóstico premium fizer sentido para seu momento, volte aos planos e escolha o ciclo ideal.",
    tone: "info"
  };
}
