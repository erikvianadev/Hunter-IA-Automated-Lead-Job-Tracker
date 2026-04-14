export function getActivationStepPresentation(step) {
  if (step?.completed) {
    return {
      label: "Concluido",
      tone: "good"
    };
  }

  if (step?.current) {
    return {
      label: "Agora",
      tone: "warning"
    };
  }

  return {
    label: "A seguir",
    tone: "muted"
  };
}
