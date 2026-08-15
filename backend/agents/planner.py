"""
Planner Agent.

Turns repair recommendations into an ordered, deduplicated execution
plan. Only includes steps that are actually necessary — if there are
no duplicates, no 'remove_duplicates' step is created, matching the
article's behaviour exactly (single fill_missing step when that's the
only issue present).

Order matters: duplicates are removed first (so imputation statistics
aren't skewed by repeated rows), then outliers are capped, then missing
values are filled (median/mode computed on the now-cleaner data).
"""
from __future__ import annotations
from core.models import RepairRecommendation, PlanStep

STEP_ORDER = ["remove_duplicates", "cap_outliers", "fill_missing"]

METHOD_TO_STEP = {
    "drop_duplicates": "remove_duplicates",
    "cap_iqr": "cap_outliers",
    "mode": "fill_missing",
    "median": "fill_missing",
}


class PlannerAgent:
    def plan(self, recommendations: list[RepairRecommendation]) -> list[PlanStep]:
        steps_by_id: dict[str, PlanStep] = {}

        for rec in recommendations:
            step_id = METHOD_TO_STEP[rec.method]
            step = steps_by_id.setdefault(step_id, PlanStep(step_id=step_id))
            if rec.column not in step.targets:
                step.targets.append(rec.column)
            step.method_by_column[rec.column] = rec.method

        # emit in a fixed, sensible order; skip steps that weren't needed
        return [steps_by_id[s] for s in STEP_ORDER if s in steps_by_id]
