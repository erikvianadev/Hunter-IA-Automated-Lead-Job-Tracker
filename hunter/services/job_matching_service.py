from __future__ import annotations

import re

from hunter.models.models import Job, JobMatch, Resume

from .resume_analysis_service import ResumeAnalysisService
from .resume_security_service import ResumeSecurityService, ResumeTrustError
from .seniority_assessment_service import SeniorityAssessmentError, SeniorityAssessmentService


class JobMatchingError(Exception):
    pass


SIGNAL_LIBRARY = (
    {"key": "python", "label": "Python", "variants": ("python",)},
    {"key": "django", "label": "Django", "variants": ("django",)},
    {"key": "flask", "label": "Flask", "variants": ("flask",)},
    {"key": "fastapi", "label": "FastAPI", "variants": ("fastapi",)},
    {"key": "sql", "label": "SQL", "variants": (" sql ", "sql,", "sql.", "sql\n", "sql/")},
    {"key": "docker", "label": "Docker", "variants": ("docker",)},
    {"key": "kubernetes", "label": "Kubernetes", "variants": ("kubernetes", "k8s")},
    {"key": "aws", "label": "AWS", "variants": (" aws ", "aws,", "aws.", "amazon web services")},
    {"key": "azure", "label": "Azure", "variants": ("azure",)},
    {"key": "gcp", "label": "GCP", "variants": (" gcp ", "google cloud")},
    {"key": "rest_api", "label": "APIs REST", "variants": ("api rest", "apis rest", "rest api", "restful api", "apis", " api ")},
    {"key": "microservices", "label": "Microservicos", "variants": ("microservices", "microservicos", "micro services")},
    {"key": "react", "label": "React", "variants": ("react",)},
    {"key": "javascript", "label": "JavaScript", "variants": ("javascript",)},
    {"key": "typescript", "label": "TypeScript", "variants": ("typescript",)},
    {"key": "pandas", "label": "Pandas", "variants": ("pandas",)},
    {"key": "spark", "label": "Spark", "variants": ("spark",)},
    {"key": "tableau", "label": "Tableau", "variants": ("tableau",)},
    {"key": "power_bi", "label": "Power BI", "variants": ("power bi", "powerbi")},
    {"key": "excel", "label": "Excel", "variants": ("excel",)},
    {"key": "machine_learning", "label": "Machine Learning", "variants": ("machine learning", "ml ")},
    {"key": "etl", "label": "ETL", "variants": (" etl ", "pipelines", "pipeline")},
)

TRACK_ORDER = {
    "internship": 0,
    "junior": 1,
    "mid": 2,
    "senior": 3,
}

TRACK_LABELS = {
    "internship": "estagio",
    "junior": "junior",
    "mid": "pleno",
    "senior": "senior",
    "freelance": "freelance",
}


class JobMatchingService:
    def __init__(
        self,
        *,
        analysis_service: ResumeAnalysisService | None = None,
        seniority_service: SeniorityAssessmentService | None = None,
        security_service: ResumeSecurityService | None = None,
    ) -> None:
        self.analysis_service = analysis_service or ResumeAnalysisService()
        self.seniority_service = seniority_service or SeniorityAssessmentService(
            analysis_service=self.analysis_service
        )
        self.security_service = security_service or ResumeSecurityService()

    def match(self, *, owner, resume: Resume, job: Job) -> JobMatch:
        if resume.owner_id != owner.id or job.owner_id != owner.id:
            raise JobMatchingError("O curriculo e a vaga precisam pertencer a sua conta.")
        try:
            self.security_service.assert_trusted(
                resume=resume,
                action="A atualizacao de aderencia foi bloqueada",
            )
        except ResumeTrustError as exc:
            raise JobMatchingError(exc.decision.message) from exc

        analysis = resume.analysis if hasattr(resume, 'analysis') else self.analysis_service.analyze(resume=resume)
        try:
            seniority = (
                resume.seniority_assessment
                if hasattr(resume, 'seniority_assessment')
                else self.seniority_service.assess(resume=resume)
            )
        except SeniorityAssessmentError as exc:
            raise JobMatchingError(str(exc)) from exc
        parsed_resume = analysis.raw_summary.get("parsed_resume", {})
        resume_projects = parsed_resume.get("projects", [])
        resume_text = self._normalize_text(
            " ".join(
                [
                    analysis.raw_summary.get("parsed_resume", {}).get("summary", ""),
                    " ".join(parsed_resume.get("experience", [])),
                    " ".join(parsed_resume.get("projects", [])),
                    " ".join(parsed_resume.get("skills", [])),
                ]
            )
        )
        job_text = self._normalize_text(f"{job.title} {job.description}")
        resume_signals = self._extract_signals(text=resume_text)
        job_signals = self._extract_signals(text=job_text)
        overlap = [job_signals[key] for key in job_signals if key in resume_signals]
        missing = [job_signals[key] for key in job_signals if key not in resume_signals][:5]
        seniority_fit = self._score_seniority_fit(job=job, seniority=seniority)
        seniority_context = self._assess_seniority_alignment(job=job, seniority=seniority)

        missing_penalty = min(len(missing), 4) * 4
        seniority_penalty = 10 if seniority_context["gap_level"] == "high" else 4 if seniority_context["gap_level"] == "medium" else 0
        project_bonus = 8 if resume_projects else 0
        project_evidence_bonus = 4 if analysis.project_score >= 70 and resume_projects else 0
        match_score = max(
            0,
            min(
                100,
                18
                + min(len(overlap), 6) * 9
                + round(analysis.overall_score * 0.24)
                + project_bonus
                + project_evidence_bonus
                + seniority_fit
                - missing_penalty
                - seniority_penalty,
            ),
        )

        strengths = self._build_strengths(
            overlap=overlap,
            analysis=analysis,
            seniority_context=seniority_context,
            resume_projects=resume_projects,
        )
        gaps = self._build_gaps(
            missing=missing,
            analysis=analysis,
            seniority_context=seniority_context,
            resume_projects=resume_projects,
        )
        evidence_signals = self._build_evidence_signals(
            overlap=overlap,
            missing=missing,
            analysis=analysis,
            seniority_context=seniority_context,
            resume_projects=resume_projects,
        )
        decision = self._classify_decision(
            match_score=match_score,
            overlap=overlap,
            missing=missing,
            seniority_context=seniority_context,
        )
        recommendation = self._build_recommendation(
            decision_class=decision["class"],
            overlap=overlap,
            missing=missing,
            seniority_context=seniority_context,
        )
        reasoning = {
            "overlapping_skills": overlap,
            "missing_keywords": missing,
            "resume_overall_score": analysis.overall_score,
            "resume_project_score": analysis.project_score,
            "recommended_track": seniority.recommended_track,
            "seniority_fit_score": seniority_fit,
            "decision_class": decision["class"],
            "decision_label": decision["label"],
            "evidence_signals": evidence_signals,
            "strength_signals": overlap,
            "gap_signals": missing,
            "seniority_context": seniority_context,
        }

        job_match, _ = JobMatch.objects.update_or_create(
            owner=owner,
            resume=resume,
            job=job,
            defaults={
                "match_score": match_score,
                "strengths": strengths,
                "gaps": gaps,
                "recommendation": recommendation,
                "reasoning": reasoning,
            },
        )
        return job_match

    def _score_seniority_fit(self, *, job: Job, seniority) -> int:
        text = f"{job.title} {job.description}".lower()
        if any(keyword in text for keyword in ["intern", "internship", "trainee"]):
            return round(seniority.internship_score * 0.15)
        if any(keyword in text for keyword in ["junior", "entry", "associate"]):
            return round(seniority.junior_score * 0.15)
        if any(keyword in text for keyword in ["senior", "lead", "principal", "staff"]):
            return round(seniority.senior_score * 0.15)
        if any(keyword in text for keyword in ["freelance", "contract", "consultant"]):
            return round(seniority.freelance_score * 0.15)
        return round(seniority.mid_score * 0.15)

    def _extract_signals(self, *, text: str) -> dict[str, str]:
        signals: dict[str, str] = {}
        for signal in SIGNAL_LIBRARY:
            if any(variant in text for variant in signal["variants"]):
                signals[signal["key"]] = signal["label"]
        return signals

    def _normalize_text(self, value: str) -> str:
        normalized = re.sub(r"[^a-z0-9+#./ ]+", " ", value.lower())
        return f" {re.sub(r'\\s+', ' ', normalized).strip()} "

    def _build_strengths(self, *, overlap, analysis, seniority_context, resume_projects) -> list[str]:
        strengths: list[str] = []
        if overlap:
            strengths.append(f"Ha aderencia em {self._format_list(overlap[:4])}.")
        if analysis.project_score >= 60 and resume_projects:
            strengths.append("Os projetos do curriculo ajudam a sustentar execucao pratica para esta vaga.")
        if analysis.structure_score >= 70:
            strengths.append("A estrutura do curriculo esta clara o bastante para uma triagem inicial sem perder sinais importantes.")
        if seniority_context["alignment"] == "aligned":
            strengths.append("A senioridade percebida do curriculo parece coerente com o nivel pedido pela vaga.")
        return strengths[:4]

    def _build_gaps(self, *, missing, analysis, seniority_context, resume_projects) -> list[str]:
        gaps: list[str] = []
        if missing:
            gaps.append(f"Faltam evidencias claras de {self._format_list(missing[:4])}.")
        if analysis.project_score < 55 or not resume_projects:
            gaps.append("A vaga pede sinais de execucao e o curriculo ainda mostra pouca prova pratica em projetos.")
        if seniority_context["alignment"] == "below":
            gaps.append("A senioridade percebida parece abaixo do esperado para esta vaga.")
        elif seniority_context["alignment"] == "above":
            gaps.append("O curriculo parece mais senior do que o contexto indicado nesta vaga.")
        return gaps[:4]

    def _build_evidence_signals(self, *, overlap, missing, analysis, seniority_context, resume_projects) -> list[str]:
        evidence: list[str] = []
        if overlap:
            evidence.append(f"Sinais de aderencia: {self._format_list(overlap[:4])}.")
        if missing:
            evidence.append(f"Sinais ausentes ou fracos: {self._format_list(missing[:4])}.")
        if resume_projects:
            evidence.append(f"O curriculo traz {len(resume_projects)} sinal(is) de projeto para sustentar experiencia aplicada.")
        else:
            evidence.append("Nao ha bloco de projetos forte o bastante para sustentar execucao aplicada.")
        evidence.append(
            f"Senioridade percebida: {seniority_context['perceived_label']}; expectativa da vaga: {seniority_context['expected_label']}."
        )
        evidence.append(f"Score atual do curriculo: {analysis.overall_score}/100, com projetos em {analysis.project_score}/100.")
        return evidence[:5]

    def _classify_decision(self, *, match_score: int, overlap, missing, seniority_context) -> dict[str, str]:
        severe_gap = len(missing) >= 3 or seniority_context["gap_level"] == "high"
        if match_score >= 78 and len(overlap) >= 2 and not severe_gap:
            return {"class": "aplicar_agora", "label": "Aplicar agora"}
        if match_score >= 55 and len(overlap) >= 1:
            return {"class": "aplicar_apos_ajustes", "label": "Aplicar apos ajustes"}
        return {"class": "fortalecer_curriculo_antes", "label": "Fortalecer curriculo antes"}

    def _build_recommendation(self, *, decision_class: str, overlap, missing, seniority_context) -> str:
        if decision_class == "aplicar_agora":
            return (
                "Aplicar agora. Os sinais centrais da vaga ja aparecem no curriculo e as lacunas restantes nao derrubam a decisao."
            )
        if decision_class == "aplicar_apos_ajustes":
            gap_text = self._format_list(missing[:3]) if missing else "alguns sinais de execucao"
            return (
                f"Aplicar apos ajustes. Ha base tecnica relevante, mas vale reforcar {gap_text} antes para aumentar a chance de avancar."
            )
        if seniority_context["alignment"] == "below":
            return (
                "Fortalecer curriculo antes. Alem de gaps tecnicos, a senioridade percebida ainda parece abaixo do que a vaga sugere."
            )
        return (
            "Fortalecer curriculo antes. Hoje faltam sinais centrais para que a recomendacao de candidatura seja coerente com a analise."
        )

    def _assess_seniority_alignment(self, *, job: Job, seniority) -> dict[str, str]:
        expected_track = self._detect_job_track(job=job)
        perceived_track = seniority.recommended_track
        expected_label = TRACK_LABELS.get(expected_track, "pleno")
        perceived_label = TRACK_LABELS.get(perceived_track, perceived_track)

        if expected_track == "freelance" or perceived_track == "freelance":
            return {
                "expected_track": expected_track,
                "expected_label": expected_label,
                "perceived_track": perceived_track,
                "perceived_label": perceived_label,
                "alignment": "aligned",
                "gap_level": "low",
            }

        expected_level = TRACK_ORDER.get(expected_track, TRACK_ORDER["mid"])
        perceived_level = TRACK_ORDER.get(perceived_track, TRACK_ORDER["mid"])
        distance = perceived_level - expected_level
        if distance <= -2:
            alignment = "below"
            gap_level = "high"
        elif distance == -1:
            alignment = "below"
            gap_level = "medium"
        elif distance >= 2:
            alignment = "above"
            gap_level = "medium"
        else:
            alignment = "aligned"
            gap_level = "low"

        return {
            "expected_track": expected_track,
            "expected_label": expected_label,
            "perceived_track": perceived_track,
            "perceived_label": perceived_label,
            "alignment": alignment,
            "gap_level": gap_level,
        }

    def _detect_job_track(self, *, job: Job) -> str:
        text = f"{job.title} {job.description}".lower()
        if any(keyword in text for keyword in ["intern", "internship", "trainee"]):
            return "internship"
        if any(keyword in text for keyword in ["junior", "entry", "associate"]):
            return "junior"
        if any(keyword in text for keyword in ["senior", "lead", "principal", "staff"]):
            return "senior"
        if any(keyword in text for keyword in ["freelance", "contract", "consultant"]):
            return "freelance"
        return "mid"

    def _format_list(self, values: list[str]) -> str:
        cleaned = [value for value in values if value]
        if not cleaned:
            return ""
        if len(cleaned) == 1:
            return cleaned[0]
        if len(cleaned) == 2:
            return f"{cleaned[0]} e {cleaned[1]}"
        return f"{', '.join(cleaned[:-1])} e {cleaned[-1]}"
