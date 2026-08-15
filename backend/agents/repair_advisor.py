"""
Column Quality Intelligence Agent.

Converts detected QualityIssues into concrete, actionable repair
recommendations: categorical missing -> mode, numeric missing -> median,
duplicates -> drop, outliers -> IQR capping. Also assigns a severity
level based on how much of the column is affected.
"""
from __future__ import annotations
import pandas as pd
from core.models import ColumnProfile, QualityIssue, RepairRecommendation


class RepairAdvisorAgent:
    def recommend(
        self,
        df: pd.DataFrame,
        profiles: list[ColumnProfile],
        issues: list[QualityIssue],
    ) -> list[RepairRecommendation]:
        profile_by_col = {p.name: p for p in profiles}
        recs: list[RepairRecommendation] = []

        for issue in issues:
            if issue.issue_type == "missing_values":
                col = issue.column
                kind = profile_by_col[col].kind
                method = "mode" if kind == "categorical" else "median"
                severity = self._severity(issue.count, len(df))
                recs.append(
                    RepairRecommendation(
                        column=col,
                        issue_type="missing_values",
                        method=method,
                        severity=severity,
                        rationale=(
                            f"{col} is {kind}; filling with {method} "
                            f"({'most frequent value' if method == 'mode' else 'robust to skew'})."
                        ),
                    )
                )

            elif issue.issue_type == "duplicates":
                severity = self._severity(issue.count, len(df))
                recs.append(
                    RepairRecommendation(
                        column="__dataset__",
                        issue_type="duplicates",
                        method="drop_duplicates",
                        severity=severity,
                        rationale="Exact-match duplicate rows should be removed to avoid double counting.",
                    )
                )

            elif issue.issue_type == "outliers":
                col = issue.column
                severity = self._severity(issue.count, len(df))
                recs.append(
                    RepairRecommendation(
                        column=col,
                        issue_type="outliers",
                        method="cap_iqr",
                        severity=severity,
                        rationale=f"{col} has values beyond the IQR fence; capping limits distortion "
                                  f"while preserving row count.",
                    )
                )

        return recs

    @staticmethod
    def _severity(count: int, total_rows: int) -> str:
        if total_rows == 0:
            return "Low"
        ratio = count / total_rows
        if ratio >= 0.15:
            return "High"
        if ratio >= 0.05:
            return "Medium"
        return "Low"
