from __future__ import annotations

from collections import Counter

from django.db.models import Avg, Max

from hunter.models.models import JobMatch, Resume


class ResumeComparisonService:
    def build(self, *, owner, resume_ids: list[int] | None = None) -> dict[str, object]:
        queryset = (
            Resume.objects
            .filter(owner=owner)
            .select_related('analysis', 'seniority_assessment')
            .order_by('-is_active', '-created_at')
        )
        if resume_ids:
            queryset = queryset.filter(id__in=resume_ids)

        resumes = list(queryset)
        compared_resumes = [self._serialize_resume(resume) for resume in resumes]
        likely_target_role = self._derive_likely_target_role(compared_resumes=compared_resumes)

        return {
            "compared_resumes": compared_resumes,
            "best_resume_by_score": self._pick_best_resume(compared_resumes=compared_resumes),
            "best_resume_for_likely_target": self._pick_best_for_target(
                compared_resumes=compared_resumes,
                likely_target_role=likely_target_role,
            ),
            "likely_target_role": likely_target_role,
            "comparison_summary": self._build_summary(
                compared_resumes=compared_resumes,
                likely_target_role=likely_target_role,
            ),
            "main_differences": self._build_main_differences(compared_resumes=compared_resumes),
            "stronger_areas": self._build_stronger_areas(compared_resumes=compared_resumes),
        }

    def _serialize_resume(self, resume: Resume) -> dict[str, object]:
        analysis = resume.analysis if hasattr(resume, 'analysis') else None
        seniority = resume.seniority_assessment if hasattr(resume, 'seniority_assessment') else None
        match_summary = JobMatch.objects.filter(resume=resume).aggregate(
            average_match_score=Avg('match_score'),
            best_match_score=Max('match_score'),
        )
        average_match_score = match_summary["average_match_score"]
        return {
            "id": resume.id,
            "label": resume.label,
            "target_role": resume.target_role,
            "is_active": resume.is_active,
            "parse_status": resume.parse_status,
            "overall_score": analysis.overall_score if analysis is not None else None,
            "structure_score": analysis.structure_score if analysis is not None else None,
            "clarity_score": analysis.clarity_score if analysis is not None else None,
            "market_fit_score": analysis.market_fit_score if analysis is not None else None,
            "project_score": analysis.project_score if analysis is not None else None,
            "recommended_track": (
                seniority.recommended_track if seniority is not None else None
            ),
            "average_match_score": (
                round(float(average_match_score), 2)
                if average_match_score is not None
                else None
            ),
            "best_match_score": match_summary["best_match_score"],
            "created_at": resume.created_at,
            "updated_at": resume.updated_at,
        }

    def _pick_best_resume(self, *, compared_resumes: list[dict[str, object]]):
        scored_resumes = [
            resume for resume in compared_resumes if resume["overall_score"] is not None
        ]
        if not scored_resumes:
            return None
        return max(
            scored_resumes,
            key=lambda item: (
                item["overall_score"],
                item["market_fit_score"] or 0,
                item["project_score"] or 0,
                item["best_match_score"] or 0,
                int(bool(item["is_active"])),
            ),
        )

    def _pick_best_for_target(
        self,
        *,
        compared_resumes: list[dict[str, object]],
        likely_target_role: str | None,
    ):
        if not compared_resumes:
            return None
        target_candidates = [
            resume
            for resume in compared_resumes
            if likely_target_role
            and (resume["target_role"] or "").strip().lower() == likely_target_role.lower()
        ]
        candidates = target_candidates or compared_resumes
        scored_candidates = [
            resume for resume in candidates if resume["market_fit_score"] is not None
        ]
        if not scored_candidates:
            return None
        return max(
            scored_candidates,
            key=lambda item: (
                item["market_fit_score"],
                item["overall_score"] or 0,
                item["best_match_score"] or 0,
                int(bool(item["is_active"])),
            ),
        )

    def _derive_likely_target_role(self, *, compared_resumes: list[dict[str, object]]) -> str | None:
        active_target = next(
            (
                resume["target_role"]
                for resume in compared_resumes
                if resume["is_active"] and resume["target_role"]
            ),
            None,
        )
        if active_target:
            return active_target

        roles = [resume["target_role"] for resume in compared_resumes if resume["target_role"]]
        if not roles:
            return None
        return Counter(roles).most_common(1)[0][0]

    def _build_summary(
        self,
        *,
        compared_resumes: list[dict[str, object]],
        likely_target_role: str | None,
    ) -> str:
        if not compared_resumes:
            return "No resumes are available to compare."

        best_resume = self._pick_best_resume(compared_resumes=compared_resumes)
        if len(compared_resumes) == 1:
            return "Only one resume is available, so comparison insights are limited."

        if best_resume is None:
            return "Compared resumes are uploaded, but scoring data is still missing for a richer comparison."

        target_text = (
            f" for {likely_target_role}"
            if likely_target_role
            else ""
        )
        return (
            f"{best_resume['label']} is currently the strongest overall version{target_text}, "
            f"driven by its score profile and recent match signals."
        )

    def _build_main_differences(self, *, compared_resumes: list[dict[str, object]]) -> list[str]:
        if len(compared_resumes) < 2:
            return []

        differences: list[str] = []
        strongest_structure = self._winner_for_area(compared_resumes, "structure_score")
        strongest_clarity = self._winner_for_area(compared_resumes, "clarity_score")
        strongest_projects = self._winner_for_area(compared_resumes, "project_score")
        strongest_market_fit = self._winner_for_area(compared_resumes, "market_fit_score")

        if strongest_structure is not None:
            differences.append(f"Best structure: {strongest_structure['label']}.")
        if strongest_clarity is not None:
            differences.append(f"Best clarity: {strongest_clarity['label']}.")
        if strongest_projects is not None:
            differences.append(f"Best project evidence: {strongest_projects['label']}.")
        if strongest_market_fit is not None:
            differences.append(f"Best market fit: {strongest_market_fit['label']}.")

        match_winner = self._winner_for_area(compared_resumes, "best_match_score")
        if match_winner is not None:
            differences.append(f"Strongest match history: {match_winner['label']}.")
        return differences[:5]

    def _build_stronger_areas(self, *, compared_resumes: list[dict[str, object]]) -> dict[str, object]:
        return {
            "structure": self._winner_for_area(compared_resumes, "structure_score"),
            "clarity": self._winner_for_area(compared_resumes, "clarity_score"),
            "projects": self._winner_for_area(compared_resumes, "project_score"),
            "market_fit": self._winner_for_area(compared_resumes, "market_fit_score"),
        }

    def _winner_for_area(self, compared_resumes: list[dict[str, object]], field_name: str):
        candidates = [resume for resume in compared_resumes if resume[field_name] is not None]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda item: (
                item[field_name],
                item["overall_score"] or 0,
                item["best_match_score"] or 0,
                int(bool(item["is_active"])),
            ),
        )
