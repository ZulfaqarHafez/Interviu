from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from .adapters import CandidateAdapterError, adapter_for
from .database import save_event, save_run, save_scorecard
from .exam_packs import get_exam_pack
from .models import CandidateConfig, CandidateResponse, RunEvent, RunRecord, Scorecard, TraceAuditSummary
from .scoring import GradeResult, grade_response, panel_disagreement
from .trace_audit import TraceAuditService


class RunOrchestrator:
    def __init__(self) -> None:
        self._sequence = 0
        self._trace_step_id = 0
        self._trace_steps: list[dict[str, Any]] = []

    async def start(self, run: RunRecord, candidate: CandidateConfig) -> Scorecard:
        run.status = "running"
        save_run(run)
        pack = get_exam_pack(run.exam_pack_id)
        adapter = adapter_for(candidate)
        lessons: list[str] = []
        seen_scores: dict[str, list[float]] = defaultdict(list)
        held_scores: dict[str, list[float]] = defaultdict(list)
        panel_results: list[dict[str, float]] = []

        try:
            self._event(run.id, "system", "run_started", {"candidate": candidate.name, "exam_pack": pack.id})
            if run.job_scope is not None:
                from .role_intelligence import analyze_job_scope

                self._event(
                    run.id,
                    "system",
                    "role_scope_applied",
                    analyze_job_scope(run.job_scope).model_dump(mode="json"),
                )
            for item in pack.items:
                for trial in range(1, run.k + 1):
                    seen_response = await self._ask_candidate(
                        run,
                        adapter,
                        candidate,
                        item.competency,
                        item.prompt,
                        trial,
                        "seen",
                        lessons,
                    )
                    seen_grade = self._grade(run, item.id, item.competency, "seen", trial, seen_response, run.competency_threshold)
                    seen_scores[item.competency].append(seen_grade.score)
                    panel_results.append(seen_grade.panel_scores)
                    if not seen_grade.passed:
                        lesson = f"{item.competency}: {seen_grade.feedback}"
                        lessons.append(lesson)
                        self._event(run.id, "lesson_library", "lesson_added", {"competency": item.competency, "lesson": lesson})

                    held_response = await self._ask_candidate(
                        run,
                        adapter,
                        candidate,
                        item.competency,
                        item.held_out_prompt,
                        trial,
                        "held_out",
                        lessons,
                    )
                    held_grade = self._grade(run, item.id, item.competency, "held_out", trial, held_response, run.competency_threshold)
                    held_scores[item.competency].append(held_grade.score)
                    panel_results.append(held_grade.panel_scores)
                    if not held_grade.passed:
                        lesson = f"{item.competency}: {held_grade.feedback}"
                        lessons.append(lesson)
                        self._event(run.id, "lesson_library", "lesson_added", {"competency": item.competency, "lesson": lesson})

            scorecard = self._scorecard(run, candidate, pack.simulator_model, seen_scores, held_scores, panel_results)
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
        result = grade_response(item, response, threshold)
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
            },
        )
        return result

    def _scorecard(
        self,
        run: RunRecord,
        candidate: CandidateConfig,
        simulator_model: str,
        seen_scores: dict[str, list[float]],
        held_scores: dict[str, list[float]],
        panel_results: list[dict[str, float]],
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
        )

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
                "content": response.reasoning[:500] or response.answer[:500],
                "tokens": max(response.tokens.total, 1),
                "input_context": question,
                "output": response.answer,
                "agent_id": candidate.id,
                "metadata": {"competency": competency, "trial": trial, "variant": variant},
            }
        )
        return self._trace_step_id

    def _record_tool_step(self, tool: dict[str, Any], question: str) -> int:
        self._trace_step_id += 1
        self._trace_steps.append(
            {
                "id": self._trace_step_id,
                "type": "tool_call",
                "content": f"Calling {tool.get('name', 'tool')}",
                "tokens": max(int(tool.get("tokens") or 1), 1),
                "tool_name": tool.get("name"),
                "tool_params": tool.get("params") or {},
                "tool_success": bool(tool.get("success", True)),
                "tool_error": tool.get("error"),
                "input_context": question,
                "output": tool.get("output"),
            }
        )
        return self._trace_step_id

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
                role_lines.append("Role under evaluation — " + "; ".join(descriptors) + ".")
        role_block = ("\n" + "\n".join(role_lines)) if role_lines else ""
        return (
            f"Candidate {candidate.name} is being evaluated by Interviu.\n"
            "Answer as an HR screening agent. Use retained lessons when relevant."
            f"{role_block}\n"
            f"Retained lessons:\n{lesson_block or '- none yet'}"
        )
