from __future__ import annotations

from collections import OrderedDict

from django.db.models import Avg, Max

from hunter.models.models import JobMatch, Resume


class ResumeReportService:
    def build(self, *, resume: Resume) -> dict[str, object]:
        analysis = resume.analysis if hasattr(resume, 'analysis') else None
        seniority = resume.seniority_assessment if hasattr(resume, 'seniority_assessment') else None
        match_summary = self._build_match_summary(resume=resume)
        strengths = self._build_strengths(analysis=analysis, seniority=seniority)
        top_gaps = self._build_top_gaps(resume=resume, analysis=analysis, seniority=seniority)
        priority_actions = self._build_priority_actions(
            analysis=analysis,
            seniority=seniority,
            top_gaps=top_gaps,
        )

        return {
            "resume_id": resume.id,
            "label": resume.label,
            "target_role": resume.target_role,
            "parse_status": resume.parse_status,
            "is_active": resume.is_active,
            "category_scores": {
                "overall": analysis.overall_score if analysis is not None else None,
                "structure": analysis.structure_score if analysis is not None else None,
                "clarity": analysis.clarity_score if analysis is not None else None,
                "market_fit": analysis.market_fit_score if analysis is not None else None,
                "projects": analysis.project_score if analysis is not None else None,
            },
            "recommended_track": (
                seniority.recommended_track if seniority is not None else None
            ),
            "strengths": strengths,
            "top_gaps": top_gaps,
            "priority_actions": priority_actions,
            "recent_match_summary": match_summary,
            "executive_summary": self._build_executive_summary(
                resume=resume,
                analysis=analysis,
                seniority=seniority,
                match_summary=match_summary,
            ),
            "profile_summary": self._build_profile_summary(
                resume=resume,
                analysis=analysis,
                seniority=seniority,
            ),
        }

    def _build_match_summary(self, *, resume: Resume) -> dict[str, object]:
        queryset = JobMatch.objects.filter(resume=resume).order_by('-match_score', '-created_at')
        aggregate = queryset.aggregate(
            average_match_score=Avg('match_score'),
            best_match_score=Max('match_score'),
        )
        top_match = queryset.first()
        average_match_score = aggregate["average_match_score"]
        return {
            "total_matches": queryset.count(),
            "average_match_score": (
                round(float(average_match_score), 2)
                if average_match_score is not None
                else None
            ),
            "best_match_score": aggregate["best_match_score"],
            "top_recommendation": top_match.recommendation if top_match is not None else None,
        }

    def _build_strengths(self, *, analysis, seniority) -> list[str]:
        strengths: list[str] = []
        if analysis is not None:
            strengths.extend(analysis.strengths[:3])
            if analysis.overall_score >= 75:
                strengths.append("Overall resume quality is already competitive for screening.")
            if analysis.market_fit_score >= 70:
                strengths.append("Market-fit signals are strong enough to support targeted applications.")
        if seniority is not None:
            strengths.append(
                f"Current evidence aligns best with {seniority.recommended_track} opportunities."
            )
        return self._deduplicate(strengths)[:5]

    def _build_top_gaps(self, *, resume: Resume, analysis, seniority) -> list[str]:
        gaps: list[str] = []
        if analysis is None:
            gaps.append("Resume analysis has not been generated yet.")
        else:
            score_map = {
                "structure": analysis.structure_score,
                "clarity": analysis.clarity_score,
                "market_fit": analysis.market_fit_score,
                "projects": analysis.project_score,
            }
            weakest_area = min(score_map, key=score_map.get)
            gaps.append(f"Lowest scoring area is {weakest_area.replace('_', ' ')}.")
            gaps.extend(analysis.weaknesses[:3])

        if seniority is None:
            gaps.append("Recommended track is not available yet.")

        match_gaps = list(
            JobMatch.objects.filter(resume=resume)
            .order_by('-created_at')
            .values_list('gaps', flat=True)[:3]
        )
        for gap_list in match_gaps:
            gaps.extend(gap_list[:2])
        return self._deduplicate(gaps)[:5]

    def _build_priority_actions(self, *, analysis, seniority, top_gaps: list[str]) -> list[str]:
        actions: list[str] = []
        if analysis is None:
            actions.append("Run resume analysis to unlock score-based recommendations.")
        else:
            actions.extend(analysis.recommendations[:3])
            if analysis.market_fit_score < 60:
                actions.append("Refine the resume toward a clearer target role and keyword coverage.")
            if analysis.project_score < 60:
                actions.append("Add stronger project outcomes with stack, scope, and measurable impact.")
        if seniority is None:
            actions.append("Run seniority assessment to focus applications at the right level.")
        else:
            actions.append(
                f"Prioritize {seniority.recommended_track} roles while strengthening weaker signals."
            )
        if not actions and top_gaps:
            actions.append(f"Address this first: {top_gaps[0]}")
        return self._deduplicate(actions)[:5]

    def _build_executive_summary(self, *, resume: Resume, analysis, seniority, match_summary) -> str:
        score = analysis.overall_score if analysis is not None else None
        score_text = (
            f"with an overall score of {score}/100"
            if score is not None
            else "without a completed analysis score yet"
        )
        target_text = resume.target_role or "the current target role"
        track_text = (
            f"best aligned to {seniority.recommended_track} opportunities"
            if seniority is not None
            else "pending seniority guidance"
        )
        match_text = (
            f"Recent matches average {match_summary['average_match_score']}/100 with a best score of {match_summary['best_match_score']}/100."
            if match_summary["total_matches"] > 0
            else "No job match history is available yet."
        )
        return (
            f"{resume.label or resume.original_filename} is positioned for {target_text} {score_text} and is {track_text}. "
            f"{match_text}"
        )

    def _build_profile_summary(self, *, resume: Resume, analysis, seniority) -> str:
        if analysis is None:
            return (
                f"{resume.label or resume.original_filename} has been uploaded and parsed, but still needs analysis "
                "before a profile summary can be fully scored."
            )

        strengths = []
        if analysis.structure_score >= 70:
            strengths.append("solid structure")
        if analysis.clarity_score >= 70:
            strengths.append("clear wording")
        if analysis.market_fit_score >= 70:
            strengths.append("strong market alignment")
        if analysis.project_score >= 70:
            strengths.append("credible project evidence")
        strengths_text = ", ".join(strengths) if strengths else "several foundational gaps"

        track_text = (
            f" The recommended track is {seniority.recommended_track}."
            if seniority is not None
            else ""
        )
        return (
            f"This resume currently shows {strengths_text}, with the strongest value coming from deterministic scoring of its existing sections and signals."
            f"{track_text}"
        )

    def _deduplicate(self, values: list[str]) -> list[str]:
        return list(OrderedDict.fromkeys(value for value in values if value))
