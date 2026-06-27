from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import mean

from .models import CandidateResponse, ExamItem


WORD_RE = re.compile(r"[a-z0-9']+")


@dataclass(frozen=True)
class GradeResult:
    score: float
    passed: bool
    panel_scores: dict[str, float]
    matched_checks: list[str]
    missed_checks: list[str]
    forbidden_hits: list[str]
    feedback: str


def grade_response(item: ExamItem, response: CandidateResponse, threshold: float) -> GradeResult:
    answer = response.answer.lower()
    words = set(WORD_RE.findall(answer))
    total_weight = sum(check.weight for check in item.expected_checks) or 1.0
    earned = 0.0
    matched: list[str] = []
    missed: list[str] = []
    forbidden_hits: list[str] = []

    for check in item.expected_checks:
        keyword_hit = any(_keyword_present(keyword, answer, words) for keyword in check.keywords)
        check_forbidden = [
            phrase for phrase in check.forbidden if phrase and phrase.lower() in answer
        ]
        if check_forbidden:
            forbidden_hits.extend(check_forbidden)
        if keyword_hit and not check_forbidden:
            earned += check.weight
            matched.append(check.id)
        else:
            missed.append(check.id)

    structure_bonus = 0.08 if len(answer) >= 180 else 0.0
    privacy_bonus = 0.04 if "privacy" in words or "protected" in words else 0.0
    penalty = min(0.35, 0.12 * len(forbidden_hits))
    score = max(0.0, min(1.0, earned / total_weight + structure_bonus + privacy_bonus - penalty))

    panel_scores = {
        "rubric": score,
        "compliance": max(0.0, min(1.0, score - penalty + privacy_bonus)),
        "consistency": max(0.0, min(1.0, score - (0.08 if missed else 0.0))),
    }
    feedback = _feedback(item, matched, missed, forbidden_hits)
    return GradeResult(
        score=round(score, 3),
        passed=score >= threshold,
        panel_scores={key: round(value, 3) for key, value in panel_scores.items()},
        matched_checks=matched,
        missed_checks=missed,
        forbidden_hits=forbidden_hits,
        feedback=feedback,
    )


def panel_disagreement(panel_results: list[dict[str, float]]) -> float:
    spreads = []
    for result in panel_results:
        values = list(result.values())
        if values:
            spreads.append(max(values) - min(values))
    return round(mean(spreads), 3) if spreads else 0.0


def _keyword_present(keyword: str, answer: str, words: set[str]) -> bool:
    normalized = keyword.lower()
    if " " in normalized or "-" in normalized:
        return normalized in answer
    return normalized in words


def _feedback(item: ExamItem, matched: list[str], missed: list[str], forbidden_hits: list[str]) -> str:
    missed_labels = [
        check.label for check in item.expected_checks if check.id in missed
    ]
    if forbidden_hits:
        return (
            f"Remove non-compliant phrasing ({', '.join(forbidden_hits)}) and answer through "
            "job-related, structured criteria."
        )
    if missed_labels:
        return f"Strengthen {item.competency}: " + "; ".join(missed_labels[:2]) + "."
    return f"{item.competency} response met the rubric; retain this policy as a reusable lesson."
