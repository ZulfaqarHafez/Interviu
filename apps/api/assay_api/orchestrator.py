from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from statistics import mean
from typing import Any

from .adapters import CandidateAdapterError, adapter_for
from .database import (
    list_lessons_for_candidate,
    list_runs_for_candidate,
    save_event,
    save_lesson,
    save_run,
    save_scorecard,
)
from .exam_packs import get_exam_pack
from .models import (
    CandidateConfig,
    CandidateResponse,
    DiagnosticLesson,
    LessonOutcome,
    RunEvent,
    RunRecord,
    Scorecard,
    TraceAuditSummary,
    utc_now,
)
from .scoring import GradeResult, grade_response, panel_disagreement
from .trace_audit import TraceAuditService


def _flag_enabled(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def tailored_exams_enabled() -> bool:
    """Master switch for the role-qualification / tailored-exam stage."""
    return _flag_enabled("ASSAY_TAILORED_EXAMS_ENABLED")


def qualify_mode() -> str:
    mode = (os.environ.get("ASSAY_QUALIFY_MODE") or "fast").strip().lower()
    return mode if mode in ("fast", "deep") else "fast"


def _run_concurrency() -> int:
    """How many exam (item, trial) units to evaluate at once. Bounded so we don't
    hammer the model API; 1 restores fully-sequential behavior."""
    raw = os.environ.get("ASSAY_RUN_CONCURRENCY")
    try:
        value = int(raw) if raw else 5
    except ValueError:
        value = 5
    return max(1, min(16, value))


class RunOrchestrator:
    def __init__(self) -> None:
        self._sequence = 0
        self._trace_step_id = 0
        self._trace_steps: list[dict[str, Any]] = []
        # Memoizes LLM-judge verdicts within a run by (item_id, answer hash) so
        # the k re-trials of identical answers don't re-bill the judge.
        self._judge_cache: dict[Any, dict[str, Any]] = {}

    async def start(self, run: RunRecord, candidate: CandidateConfig) -> Scorecard:
        run.status = "running"
        # Capture the originally-requested pack before a tailored run repoints
        # exam_pack_id at its per-run gen-* id, so the learning loop keys off a
        # stable id and lessons carry across reruns in tailored mode too.
        if not run.source_pack_id:
            run.source_pack_id = run.exam_pack_id
        save_run(run)
        adapter = adapter_for(candidate)

        try:
            self._event(run.id, "system", "run_started", {"candidate": candidate.name, "exam_pack": run.exam_pack_id})
            # Qualify the judge: research what this agent should be, then build a
            # tailored exam from that brief. Both degrade to the static pack when
            # the stage is off or OpenAI is unavailable.
            role_brief = self._qualify(run, candidate)
            pack, qualification_status = self._resolve_pack(run, role_brief)
            # Closed learning loop: seed this run with diagnostics retained from the
            # candidate's prior runs on this pack, so prior lessons are applied from
            # the very first question. Within-run lessons still accumulate on top.
            lessons, prior_by_comp, prior_run_id = self._load_prior_diagnostics(run, candidate, pack)
            applied_lesson_ids = [lesson.id for group in prior_by_comp.values() for lesson in group]
            if applied_lesson_ids:
                self._event(
                    run.id,
                    "lesson_library",
                    "lesson_applied",
                    {
                        "count": len(applied_lesson_ids),
                        "prior_run_id": prior_run_id,
                        "lessons": [
                            {"id": lesson.id, "competency": lesson.competency, "text": lesson.text}
                            for group in prior_by_comp.values()
                            for lesson in group
                        ],
                    },
                )
            if run.job_scope is not None:
                from .role_intelligence import analyze_job_scope

                self._event(
                    run.id,
                    "system",
                    "role_scope_applied",
                    analyze_job_scope(run.job_scope).model_dump(mode="json"),
                )
            seen_scores, held_scores, panel_results, lesson_feedback, judge_results = await self._run_items(
                run,
                adapter,
                candidate,
                pack,
                lessons,
            )

            scorecard = self._assemble_scorecard(
                run,
                candidate,
                pack.simulator_model,
                seen_scores,
                held_scores,
                panel_results,
                judge_results,
            )
            scorecard.lessons_applied = applied_lesson_ids
            scorecard.prior_run_id = prior_run_id
            scorecard.qualification_status = qualification_status
            if role_brief is not None:
                scorecard.role_brief_summary = role_brief.role_summary or None
            # If the live key was rate-limited, the run answered deterministically;
            # mark the verdict as a demo so the UI can say so plainly.
            if getattr(adapter, "degraded", False):
                scorecard.degraded = True
                scorecard.degraded_reason = getattr(adapter, "degraded_reason", None)
                self._event(
                    run.id,
                    "system",
                    "degraded_to_demo",
                    {"reason": scorecard.degraded_reason or "OpenAI rate limit"},
                )
            self._record_lesson_outcomes(run, prior_by_comp, scorecard)
            self._persist_new_lessons(run, candidate, pack, scorecard, lesson_feedback)
            save_scorecard(scorecard)
            run.status = "completed"
            save_run(run)
            self._event(run.id, "system", "run_completed", {"certified": scorecard.certified})
            return scorecard
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            save_run(run)
            self._event(run.id, "system", "run_failed", {"error": str(exc)})
            raise
        finally:
            await adapter.aclose()

    # --- Judge qualification (research what the agent should be) ------------

    def _qualify(self, run: RunRecord, candidate: CandidateConfig) -> Any:
        """Research the role and record a brief, when the stage is enabled.

        Phase 1 surfaces the brief as a ``role_qualified`` event without changing
        the exam or grading. Returns the :class:`RoleBrief` (or ``None`` when the
        stage is off) so callers can denormalize its summary onto the scorecard.
        """
        if not tailored_exams_enabled():
            return None
        from .role_qualification import build_role_brief

        brief = build_role_brief(run, candidate, mode=qualify_mode())
        self._event(run.id, "system", "role_qualified", brief.model_dump(mode="json", by_alias=True))
        return brief

    def _resolve_pack(self, run: RunRecord, role_brief: Any) -> tuple[Any, str]:
        """Pick the exam pack for this run: a tailored pack synthesized from the
        brief, or the run's already-selected static pack.

        Returns ``(pack, qualification_status)``. When a tailored pack is built
        it is registered and ``run.exam_pack_id`` is repointed at it so the rest
        of the run (grading, lessons, ``get_exam_pack`` in ``_grade``) is
        consistent. Synthesis failures fall back to the static pack.
        """
        if role_brief is None:
            return get_exam_pack(run.exam_pack_id), "deterministic"
        from .exam_synthesis import synthesize_exam_pack

        pack, status = synthesize_exam_pack(role_brief, run)
        if status == "tailored":
            run.exam_pack_id = pack.id
            run.generated_pack_id = pack.id
            save_run(run)
            self._event(
                run.id,
                "examiner",
                "tailored_exam_generated",
                {
                    "pack_id": pack.id,
                    "item_count": len(pack.items),
                    "competencies": sorted({item.competency for item in pack.items}),
                },
            )
        return pack, status

    # --- Diagnostic library (closed learning loop) -------------------------

    def _load_prior_diagnostics(
        self,
        run: RunRecord,
        candidate: CandidateConfig,
        pack: Any,
    ) -> tuple[list[str], dict[str, list[DiagnosticLesson]], str | None]:
        """Seed the run with active lessons retained from this candidate's
        prior runs on the same pack, grouped by competency for outcome tracking.
        """
        competencies = sorted({item.competency for item in pack.items})
        lesson_key = run.source_pack_id or run.exam_pack_id
        prior = list_lessons_for_candidate(candidate.id, lesson_key, competencies, active_only=True)
        by_comp: dict[str, list[DiagnosticLesson]] = defaultdict(list)
        for lesson in prior:
            by_comp[lesson.competency].append(lesson)
        seed = [f"{lesson.competency}: {lesson.text}" for lesson in prior]
        return seed, by_comp, self._prior_run_id(run, candidate)

    @staticmethod
    def _prior_run_id(run: RunRecord, candidate: CandidateConfig) -> str | None:
        """Most recent prior completed run for this candidate on the same pack."""
        run_key = run.source_pack_id or run.exam_pack_id
        prior_runs = [
            record
            for record in list_runs_for_candidate(candidate.id)
            if record.id != run.id
            and (record.source_pack_id or record.exam_pack_id) == run_key
            and record.status == "completed"
        ]
        return prior_runs[-1].id if prior_runs else None

    def _record_lesson_outcomes(
        self,
        run: RunRecord,
        prior_by_comp: dict[str, list[DiagnosticLesson]],
        scorecard: Scorecard,
    ) -> None:
        """Record whether each applied lesson's competency improved this run."""
        for competency, lessons_list in prior_by_comp.items():
            score = scorecard.held_out_scores.get(competency)
            if score is None:
                continue
            passed = scorecard.pass_at_k.get(competency, False)
            for lesson in lessons_list:
                if run.id not in lesson.applied_run_ids:
                    lesson.applied_run_ids.append(run.id)
                lesson.last_applied_at = utc_now()
                lesson.latest_outcome_score = score
                lesson.latest_outcome = self._classify_outcome(passed, [lesson], score)
                if passed:
                    # Competency now clears the gate; retire the diagnostic.
                    lesson.active = False
                save_lesson(lesson)
                self._event(
                    run.id,
                    "lesson_library",
                    "lesson_outcome",
                    {
                        "lesson_id": lesson.id,
                        "competency": competency,
                        "outcome": lesson.latest_outcome,
                        "score": score,
                        "origin_score": lesson.origin_score,
                        "retired": not lesson.active,
                    },
                )

    @staticmethod
    def _classify_outcome(
        passed: bool,
        lessons_list: list[DiagnosticLesson],
        current_score: float,
    ) -> LessonOutcome:
        if not passed:
            return "still_failing"
        origin = max((lesson.origin_score for lesson in lessons_list), default=0.0)
        if current_score >= origin + 0.05:
            return "improved"
        if current_score <= origin - 0.05:
            return "regressed"
        return "unchanged"

    def _persist_new_lessons(
        self,
        run: RunRecord,
        candidate: CandidateConfig,
        pack: Any,
        scorecard: Scorecard,
        lesson_feedback: dict[str, str],
    ) -> None:
        """Persist one diagnostic per competency that failed this run, deduped by
        (competency, text) against the candidate's existing library so re-runs do
        not multiply rows."""
        lesson_key = run.source_pack_id or run.exam_pack_id
        existing = list_lessons_for_candidate(candidate.id, lesson_key, active_only=False)
        existing_keys = {(lesson.competency, lesson.text) for lesson in existing}
        for competency, passed in scorecard.pass_at_k.items():
            if passed:
                continue
            text = lesson_feedback.get(competency)
            if not text or (competency, text) in existing_keys:
                continue
            lesson = DiagnosticLesson(
                candidate_id=candidate.id,
                exam_pack_id=lesson_key,
                competency=competency,
                text=text,
                origin_run_id=run.id,
                origin_score=scorecard.held_out_scores.get(competency, 0.0),
                origin_variant="held_out",
            )
            save_lesson(lesson)
            existing_keys.add((competency, text))
            self._event(
                run.id,
                "lesson_library",
                "lesson_persisted",
                {"lesson_id": lesson.id, "competency": competency, "text": text},
            )

    async def _ask_candidate(
        self,
        run: RunRecord,
        adapter: Any,
        candidate: CandidateConfig,
        competency: str,
        question: str,
        trial: int,
        variant: str,
        lessons: list[str],
    ) -> CandidateResponse:
        context = self._context(candidate, lessons, run)
        self._event(
            run.id,
            "examiner",
            "question_asked",
            {"competency": competency, "trial": trial, "variant": variant, "question": question},
        )
        try:
            response = await adapter.ask(context=context, question=question)
        except CandidateAdapterError:
            raise

        reasoning_step_id = self._record_reasoning_step(candidate, response, question, competency, trial, variant)
        self._event(
            run.id,
            "candidate",
            "candidate_answered",
            {
                "candidate_id": candidate.id,
                "competency": competency,
                "trial": trial,
                "variant": variant,
                "answer": response.answer,
                "reasoning": response.reasoning,
                "latency_ms": response.latency_ms,
                "tokens": response.tokens.model_dump(),
            },
            tracerazor_step_id=reasoning_step_id,
        )
        for tool_call in response.tool_calls:
            tool_step_id = self._record_tool_step(tool_call.model_dump(), question)
            self._event(
                run.id,
                "candidate",
                "tool_called",
                {
                    "competency": competency,
                    "trial": trial,
                    "variant": variant,
                    "tool": tool_call.model_dump(),
                },
                tracerazor_step_id=tool_step_id,
            )
        return response

    async def _run_items(
        self,
        run: RunRecord,
        adapter: Any,
        candidate: CandidateConfig,
        pack: Any,
        lessons: list[str],
    ) -> tuple[
        dict[str, list[float]],
        dict[str, list[float]],
        list[dict[str, float]],
        dict[str, str],
        list[dict[str, Any]],
    ]:
        seen_scores: dict[str, list[float]] = defaultdict(list)
        held_scores: dict[str, list[float]] = defaultdict(list)
        panel_results: list[dict[str, float]] = []
        lesson_feedback: dict[str, str] = {}
        judge_results: list[dict[str, Any]] = []

        # Evaluate (item, trial) units concurrently with a bounded pool. Prior-run
        # lessons (the seed) apply to every unit; within-run lesson accumulation
        # across items is intentionally dropped here in favour of parallelism (the
        # closed learning loop persists cross-run, which is the load-bearing part).
        seed_lessons = list(lessons)
        semaphore = asyncio.Semaphore(_run_concurrency())

        async def evaluate(item: Any, trial: int) -> tuple[Any, int, GradeResult, GradeResult]:
            async with semaphore:
                seen_response = await self._ask_candidate(
                    run, adapter, candidate, item.competency, item.prompt, trial, "seen", seed_lessons
                )
                seen_grade = self._grade(
                    run, item.id, item.competency, "seen", trial, seen_response, run.competency_threshold
                )
                held_response = await self._ask_candidate(
                    run, adapter, candidate, item.competency, item.held_out_prompt, trial, "held_out", seed_lessons
                )
                held_grade = self._grade(
                    run, item.id, item.competency, "held_out", trial, held_response, run.competency_threshold
                )
                return item, trial, seen_grade, held_grade

        units = [(item, trial) for item in pack.items for trial in range(1, run.k + 1)]
        # gather preserves argument order, so aggregation below is deterministic
        # regardless of completion order.
        results = await asyncio.gather(*(evaluate(item, trial) for item, trial in units))

        for item, _trial, seen_grade, held_grade in results:
            seen_scores[item.competency].append(seen_grade.score)
            panel_results.append(seen_grade.panel_scores)
            if seen_grade.judge is not None:
                judge_results.append(seen_grade.judge)
            if not seen_grade.passed:
                lesson = f"{item.competency}: {seen_grade.feedback}"
                lessons.append(lesson)
                lesson_feedback.setdefault(item.competency, seen_grade.feedback)
                self._event(run.id, "lesson_library", "lesson_added",
                            {"competency": item.competency, "lesson": lesson})

            held_scores[item.competency].append(held_grade.score)
            panel_results.append(held_grade.panel_scores)
            if held_grade.judge is not None:
                judge_results.append(held_grade.judge)
            if not held_grade.passed:
                lesson = f"{item.competency}: {held_grade.feedback}"
                lessons.append(lesson)
                # Held-out feedback is the stronger signal; let it win.
                lesson_feedback[item.competency] = held_grade.feedback
                self._event(run.id, "lesson_library", "lesson_added",
                            {"competency": item.competency, "lesson": lesson})

        return seen_scores, held_scores, panel_results, lesson_feedback, judge_results

    def _grade(
        self,
        run: RunRecord,
        item_id: str,
        competency: str,
        variant: str,
        trial: int,
        response: CandidateResponse,
        threshold: float,
    ) -> GradeResult:
        pack = get_exam_pack(run.exam_pack_id)
        item = next(exam_item for exam_item in pack.items if exam_item.id == item_id)
        result = grade_response(item, response, threshold, judge_cache=self._judge_cache)
        self._event(
            run.id,
            "grader_panel",
            "response_graded",
            {
                "item_id": item_id,
                "competency": competency,
                "variant": variant,
                "trial": trial,
                "score": result.score,
                "passed": result.passed,
                "panel_scores": result.panel_scores,
                "matched_checks": result.matched_checks,
                "missed_checks": result.missed_checks,
                "forbidden_hits": result.forbidden_hits,
                "feedback": result.feedback,
                "judge": result.judge,
            },
        )
        return result

    def _assemble_scorecard(
        self,
        run: RunRecord,
        candidate: CandidateConfig,
        simulator_model: str,
        seen_scores: dict[str, list[float]],
        held_scores: dict[str, list[float]],
        panel_results: list[dict[str, float]],
        judge_results: list[dict[str, Any]] | None = None,
    ) -> Scorecard:
        seen_mean = {key: round(mean(values), 3) for key, values in seen_scores.items()}
        held_mean = {key: round(mean(values), 3) for key, values in held_scores.items()}
        transfer_gap = {
            key: round(max(0.0, seen_mean.get(key, 0.0) - held_mean.get(key, 0.0)), 3)
            for key in held_mean
        }
        pass_at_k = {
            key: all(score >= run.competency_threshold for score in values)
            for key, values in held_scores.items()
        }
        task_value_score = mean(held_mean.values()) if held_mean else 0.0
        trace_audit = TraceAuditService(threshold=run.tas_threshold).analyse(
            candidate=candidate,
            trace_steps=self._trace_steps,
            task_value_score=task_value_score,
        )
        self._event(
            run.id,
            "trace_auditor",
            "tracerazor_audited",
            trace_audit.model_dump(mode="json"),
        )

        failures: list[str] = []
        for competency, passed in pass_at_k.items():
            if not passed:
                failures.append(f"{competency} failed pass^{run.k} on held-out variants")
        for competency, gap in transfer_gap.items():
            if gap > run.max_transfer_gap:
                failures.append(f"{competency} transfer_gap {gap:.2f} exceeds {run.max_transfer_gap:.2f}")
        if trace_audit.status != "ok":
            failures.append(f"TraceRazor audit status is {trace_audit.status}")
        elif not trace_audit.passes:
            failures.append(f"TraceRazor TAS {trace_audit.tas_score:.1f} is below {run.tas_threshold:.1f}")

        certified = not failures
        judge_summary = self._judge_summary(judge_results or [])
        return Scorecard(
            run_id=run.id,
            certified=certified,
            k=run.k,
            thresholds={
                "competency": run.competency_threshold,
                "max_transfer_gap": run.max_transfer_gap,
                "tas": run.tas_threshold,
            },
            simulator_model=simulator_model,
            pass_at_k=pass_at_k,
            competency_scores=held_mean,
            seen_scores=seen_mean,
            held_out_scores=held_mean,
            transfer_gap=transfer_gap,
            grader_disagreement=panel_disagreement(panel_results),
            trace_audit=trace_audit,
            failure_reasons=failures,
            semantic_judge_used=judge_summary["used"] > 0,
            semantic_judge_summary=judge_summary,
        )

    @staticmethod
    def _judge_summary(judge_results: list[dict[str, Any]]) -> dict[str, Any]:
        used = [judge for judge in judge_results if judge.get("status") == "used"]
        rescued = sum(len(judge.get("rescued_check_ids") or []) for judge in used)
        models = sorted({str(judge.get("model")) for judge in judge_results if judge.get("model")})
        statuses: dict[str, int] = {}
        for judge in judge_results:
            status = str(judge.get("status") or "unknown")
            statuses[status] = statuses.get(status, 0) + 1
        return {
            "attempted": len(judge_results),
            "used": len(used),
            "rescued_checks": rescued,
            "models": models,
            "statuses": statuses,
        }

    def _event(
        self,
        run_id: str,
        actor: RunEvent.model_fields["actor"].annotation,
        event_type: str,
        payload: dict[str, Any],
        tracerazor_step_id: int | None = None,
    ) -> RunEvent:
        self._sequence += 1
        event = RunEvent(
            run_id=run_id,
            sequence=self._sequence,
            actor=actor,
            event_type=event_type,
            payload=payload,
            ended_at=None,
            tracerazor_step_id=tracerazor_step_id,
        )
        return save_event(event)

    # Cap recorded step content well above the prior 500-char limit so the
    # TraceRazor audit sees the candidate's real reasoning plus a substantive
    # slice of the answer instead of a truncated placeholder. Kept bounded so
    # very long answers do not bloat the trace payload sent to the auditor.
    _STEP_CONTENT_CAP = 1200

    def _record_reasoning_step(
        self,
        candidate: CandidateConfig,
        response: CandidateResponse,
        question: str,
        competency: str,
        trial: int,
        variant: str,
    ) -> int:
        self._trace_step_id += 1
        self._trace_steps.append(
            {
                "id": self._trace_step_id,
                "type": "reasoning",
                "content": self._reasoning_content(response),
                "tokens": self._step_tokens(response.tokens.total, response.answer, response.reasoning),
                "input_context": question,
                "output": response.answer,
                "agent_id": candidate.id,
                "metadata": {"competency": competency, "trial": trial, "variant": variant},
            }
        )
        return self._trace_step_id

    def _record_tool_step(self, tool: dict[str, Any], question: str) -> int:
        self._trace_step_id += 1
        name = tool.get("name", "tool")
        params = tool.get("params") or {}
        output = tool.get("output")
        self._trace_steps.append(
            {
                "id": self._trace_step_id,
                "type": "tool_call",
                "content": self._tool_content(name, params, output),
                "tokens": self._step_tokens(tool.get("tokens"), str(output or ""), str(params)),
                "tool_name": tool.get("name"),
                "tool_params": params,
                "tool_success": bool(tool.get("success", True)),
                "tool_error": tool.get("error"),
                "input_context": question,
                "output": output,
            }
        )
        return self._trace_step_id

    def _reasoning_content(self, response: CandidateResponse) -> str:
        """Build a faithful, information-rich step body.

        Combine the candidate's reasoning with a slice of the answer so the
        audit never sees an empty/placeholder step. Falls back gracefully when
        only one of the two is present.
        """
        reasoning = (response.reasoning or "").strip()
        answer = (response.answer or "").strip()
        parts: list[str] = []
        if reasoning:
            parts.append(f"Reasoning: {reasoning}")
        if answer:
            parts.append(f"Answer: {answer}")
        content = "\n".join(parts) if parts else "(no content reported)"
        return content[: self._STEP_CONTENT_CAP]

    def _tool_content(self, name: str, params: dict[str, Any], output: Any) -> str:
        content = f"Calling {name}"
        if params:
            content += f" with {params}"
        if output:
            content += f" -> {output}"
        return content[: self._STEP_CONTENT_CAP]

    @staticmethod
    def _step_tokens(reported: Any, *text_fields: str) -> int:
        """Return a faithful per-step token count.

        Prefer the real count an adapter reports (mock and HTTP candidates both
        emit genuine counts). Only fall back to a deterministic ~4-chars/token
        estimate over the step's own text when no real count exists, so a step
        is never collapsed to the misleading ``tokens=1`` placeholder.
        """
        try:
            real = int(reported) if reported is not None else 0
        except (TypeError, ValueError):
            real = 0
        if real > 0:
            return real
        estimate = sum(len(field or "") for field in text_fields) // 4
        return max(estimate, 1)

    @staticmethod
    def _context(candidate: CandidateConfig, lessons: list[str], run: RunRecord | None = None) -> str:
        lesson_block = "\n".join(f"- {lesson}" for lesson in lessons[-8:])
        role_lines: list[str] = []
        scope = run.job_scope if run is not None else None
        if scope is not None:
            descriptors = []
            if scope.title:
                descriptors.append(f"title: {scope.title}")
            if scope.seniority and scope.seniority != "unspecified":
                descriptors.append(f"seniority: {scope.seniority}")
            if scope.domain:
                descriptors.append(f"domain: {scope.domain}")
            if descriptors:
                role_lines.append("Role under evaluation - " + "; ".join(descriptors) + ".")
        role_block = ("\n" + "\n".join(role_lines)) if role_lines else ""
        return (
            f"Candidate {candidate.name} is being evaluated by Assay.\n"
            "Answer as the candidate agent under evaluation. Use retained lessons when relevant."
            f"{role_block}\n"
            f"Retained lessons:\n{lesson_block or '- none yet'}"
        )
