from __future__ import annotations

import re
from decimal import Decimal

from django.conf import settings

from hunter.choices import ResumeParseStatus
from hunter.models.models import Job, JobMatch, Resume

from .resume_security_service import ResumeSecurityService


class JobMatchingError(Exception):
    pass


class JobMatchingService:
    def __init__(self, *, security_service: ResumeSecurityService | None = None) -> None:
        self.security_service = security_service or ResumeSecurityService()

    def match(self, *, resume: Resume, job: Job) -> JobMatch:
        self.security_service.assert_trusted(resume=resume, action="job_matching")

        existing = JobMatch.objects.filter(resume=resume, job=job).first()
        if existing:
            return existing

        analysis = getattr(resume, "analysis", None)
        if not analysis:
            raise JobMatchingError("Resume analysis is required for matching.")

        seniority = getattr(resume, "seniority_assessment", None)
        seniority_context = seniority.reasoning if seniority else {}

        resume_text = self._normalize_text(resume.extracted_text or "")
        job_requirements = getattr(job, "requirements", "")
        job_text = self._normalize_text(f"{job.title} {job.description} {job_requirements}")

        overlap = self._compute_overlap(resume_text=resume_text, job_text=job_text)
        
        score = self._calculate_score(
            overlap=overlap,
            analysis=analysis,
            seniority_context=seniority_context,
        )

        match = JobMatch.objects.create(
            owner=resume.owner,
            resume=resume,
            job=job,
            match_score=int(score),
            strengths=self._build_strengths(
                overlap=overlap,
                analysis=analysis,
                seniority_context=seniority_context,
                resume_projects=analysis.raw_summary.get("projects", []),
            ),
            gaps=self._build_gaps(
                overlap=overlap,
                analysis=analysis,
                job_text=job_text,
            ),
            recommendation=self._build_recommendation(score=score, overlap=overlap),
            reasoning={
                "decision_class": self._classify_match(score),
                "decision_label": self._get_decision_label(score),
                "evidence_signals": self._collect_evidence(overlap),
                "seniority_context": seniority_context,
            },
        )
        return match

    def _compute_overlap(self, *, resume_text: str, job_text: str) -> dict[str, float]:
        signals = {
            "python": 1.2,
            "django": 1.0,
            "flask": 0.8,
            "fastapi": 0.8,
            "sql": 0.7,
            "aws": 0.9,
            "docker": 0.7,
            "kubernetes": 0.8,
            "react": 1.0,
            "typescript": 0.9,
            "javascript": 0.7,
            "node": 0.8,
            "machine learning": 1.2,
            "data science": 1.2,
            "product management": 1.1,
            "agile": 0.5,
            "scrum": 0.5,
        }
        
        overlap: dict[str, float] = {}
        for term, weight in signals.items():
            if f" {term} " in job_text:
                if f" {term} " in resume_text:
                    overlap[term] = weight
                else:
                    overlap[term] = 0.0
        return overlap

    def _calculate_score(self, *, overlap, analysis, seniority_context) -> float:
        base_score = float(analysis.overall_score or 50)
        
        found_signals = [w for w in overlap.values() if w > 0]
        missing_signals = [w for w in overlap.values() if w == 0]
        
        signal_bonus = sum(found_signals) * 8.0
        signal_penalty = sum(missing_signals) * 12.0
        
        seniority_bonus = 0.0
        if seniority_context.get("recommended_track") == "senior":
            seniority_bonus = 10.0
        
        final_score = base_score + signal_bonus - signal_penalty + seniority_bonus
        return max(0.0, min(100.0, final_score))

    def _classify_match(self, score: float) -> str:
        if score >= 85: return "strong"
        if score >= 65: return "good"
        if score >= 40: return "fair"
        return "weak"

    def _get_decision_label(self, score: float) -> str:
        if score >= 85: return "Altamente Recomendado"
        if score >= 65: return "Boa Aderencia"
        if score >= 40: return "Aderencia Parcial"
        return "Baixa Aderencia"

    def _collect_evidence(self, overlap) -> list[dict[str, str]]:
        evidence = []
        for term, weight in overlap.items():
            if weight > 0:
                evidence.append({
                    "key": term,
                    "label": term.title(),
                    "type": "skill_overlap"
                })
        return evidence

    def _build_strengths(self, *, overlap, analysis, seniority_context, resume_projects) -> list[str]:
        strengths = []
        top_skills = [k.title() for k, v in overlap.items() if v > 0]
        if top_skills:
            strengths.append(f"Domínio técnico em: {', '.join(top_skills[:3])}")
        
        if analysis.overall_score >= 80:
            strengths.append("Perfil profissional sólido e bem estruturado")
        
        if resume_projects:
            strengths.append(f"Experiência prática demonstrada em {len(resume_projects)} projetos")
            
        return strengths

    def _build_gaps(self, *, overlap, analysis, job_text) -> list[str]:
        gaps = []
        missing = [k.title() for k, v in overlap.items() if v == 0]
        if missing:
            gaps.append(f"Faltam evidências claras de: {', '.join(missing[:3])}")
            
        if analysis.market_fit_score < 60:
            gaps.append("Apresentação do currículo pode ser otimizada para o mercado")
            
        return gaps

    def _build_recommendation(self, *, score: float, overlap) -> str:
        if score >= 85:
            return "Candidato excepcional. Prossiga com prioridade máxima."
        if score >= 65:
            return "Forte candidato. Vale avançar para entrevista técnica."
        if score >= 40:
            return "Candidato razoável. Avalie se os gaps técnicos são impeditivos."
        return "Baixa aderência inicial. Considere outros perfis antes de avançar."

    def _normalize_text(self, value: str) -> str:
        normalized = re.sub(r"[^a-z0-9+#./ ]+", " ", value.lower())
        clean = re.sub(r"\s+", " ", normalized).strip()
        return f" {clean} "
