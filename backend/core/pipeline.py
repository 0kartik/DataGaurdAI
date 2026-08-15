"""
Pipeline orchestrator.

Runs the full agent lifecycle in order:
Ingestion -> Profiling -> Quality Check -> Repair Advice -> Planning
-> Execution -> Evaluation -> Explanation, with Monitoring wrapping
the whole thing. Returns a single PipelineResult bundling everything
the dashboard needs to render.
"""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd

from agents.ingestion import IngestionAgent
from agents.profiling import ProfilingAgent
from agents.quality_checker import QualityCheckerAgent
from agents.repair_advisor import RepairAdvisorAgent
from agents.planner import PlannerAgent
from agents.executor import ExecutionAgent
from agents.scorer import ScorerAgent
from agents.explainer import ExplanationAgent
from core.monitor import Monitor
from core.models import (
    ColumnProfile, QualityIssue, RepairRecommendation, PlanStep,
    ExecutionLogEntry, QualityScore,
)


@dataclass
class PipelineResult:
    ingestion_report: dict
    profiles: list[ColumnProfile]
    issues: list[QualityIssue]
    recommendations: list[RepairRecommendation]
    plan: list[PlanStep]
    execution_log: list[ExecutionLogEntry]
    df_before: pd.DataFrame
    df_after: pd.DataFrame
    score_before: QualityScore
    score_after: QualityScore
    explanation: str
    monitor_summary: dict


class DataGuardPipeline:
    def __init__(self, featherless_api_key: str | None = None, featherless_model: str | None = None):
        self.ingestion = IngestionAgent()
        self.profiling = ProfilingAgent()
        self.checker = QualityCheckerAgent()
        self.advisor = RepairAdvisorAgent()
        self.planner = PlannerAgent()
        self.executor = ExecutionAgent()
        self.scorer = ScorerAgent()
        self.explainer = ExplanationAgent(api_key=featherless_api_key, model=featherless_model)

    def run(self, file_like) -> PipelineResult:
        monitor = Monitor(api_key_detected=bool(self.explainer.api_key))

        # 1. Ingestion
        df, ingestion_report = self.ingestion.load(file_like)

        # 2. Profiling
        profiles = self.profiling.profile(df)

        # 3. Quality Check
        issues = self.checker.check(df, profiles)

        # 4. Column Quality Intelligence (repair recommendations)
        recommendations = self.advisor.recommend(df, profiles, issues)

        # 5. Planning
        plan = self.planner.plan(recommendations)

        # 6. Execution
        df_after, execution_log = self.executor.execute(df, plan)

        # 7. Evaluation (before/after)
        score_before = self.scorer.score(df)
        score_after = self.scorer.score(df_after)

        # 8. Explanation
        explanation = self.explainer.explain(
            issues, recommendations, execution_log, score_before, score_after, monitor
        )

        return PipelineResult(
            ingestion_report=ingestion_report,
            profiles=profiles,
            issues=issues,
            recommendations=recommendations,
            plan=plan,
            execution_log=execution_log,
            df_before=df,
            df_after=df_after,
            score_before=score_before,
            score_after=score_after,
            explanation=explanation,
            monitor_summary=monitor.summary(),
        )
