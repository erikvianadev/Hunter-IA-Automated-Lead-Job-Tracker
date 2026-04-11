from __future__ import annotations


class ResumeScoringService:
    def score(self, *, parsed_resume: dict[str, object], text: str) -> dict[str, object]:
        section_order = parsed_resume.get("section_order", [])
        word_count = int(parsed_resume.get("word_count", 0))
        links = parsed_resume.get("links", [])
        skills = parsed_resume.get("skills", [])
        projects = parsed_resume.get("projects", [])
        experience = parsed_resume.get("experience", [])
        summary = parsed_resume.get("summary", "")

        structure_score = min(
            100,
            25
            + len(section_order) * 10
            + (10 if parsed_resume.get("headline") else 0)
            + (10 if links else 0),
        )
        clarity_score = min(
            100,
            30
            + (20 if 80 <= word_count <= 900 else 10)
            + (15 if summary else 0)
            + (15 if skills else 0)
            + (10 if experience else 0),
        )
        market_fit_score = min(
            100,
            20
            + min(len(skills), 10) * 5
            + (15 if experience else 0)
            + (10 if links else 0)
            + (10 if parsed_resume.get("education") else 0),
        )
        project_score = min(
            100,
            10
            + min(len(projects), 5) * 15
            + (10 if any("github.com" in link.lower() for link in links) else 0),
        )
        overall_score = round(
            (structure_score + clarity_score + market_fit_score + project_score) / 4
        )

        return {
            "overall_score": overall_score,
            "structure_score": structure_score,
            "clarity_score": clarity_score,
            "market_fit_score": market_fit_score,
            "project_score": project_score,
            "score_factors": {
                "section_count": len(section_order),
                "word_count": word_count,
                "skills_count": len(skills),
                "projects_count": len(projects),
                "links_count": len(links),
                "experience_entries": len(experience),
            },
        }
