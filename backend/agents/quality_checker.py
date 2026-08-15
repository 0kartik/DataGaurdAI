"""
Data Quality Checker Agent.

Inspects the dataset for integrity issues: missing values per column,
duplicate rows (exact match), and outliers in numeric columns via the
IQR method. Produces a flat list of QualityIssue objects that later
agents turn into repair actions.
"""
from __future__ import annotations
import pandas as pd
from core.models import ColumnProfile, QualityIssue


class QualityCheckerAgent:
    def check(self, df: pd.DataFrame, profiles: list[ColumnProfile]) -> list[QualityIssue]:
        issues: list[QualityIssue] = []

        # --- missing values, per column ---
        for p in profiles:
            if p.missing_count > 0:
                issues.append(
                    QualityIssue(
                        issue_type="missing_values",
                        column=p.name,
                        count=p.missing_count,
                        detail=f"{p.name} has {p.missing_count} missing value(s).",
                    )
                )

        # --- duplicate rows, exact match across all columns ---
        dup_count = int(df.duplicated(keep="first").sum())
        if dup_count > 0:
            issues.append(
                QualityIssue(
                    issue_type="duplicates",
                    column=None,
                    count=dup_count,
                    detail=f"{dup_count} duplicate row(s) found.",
                )
            )

        # --- outliers via IQR, numeric columns only ---
        for p in profiles:
            if p.kind != "numeric":
                continue
            series = df[p.name].dropna()
            if len(series) < 4:
                continue  # not enough data for a meaningful IQR
            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outlier_count = int(((series < lower) | (series > upper)).sum())
            if outlier_count > 0:
                issues.append(
                    QualityIssue(
                        issue_type="outliers",
                        column=p.name,
                        count=outlier_count,
                        detail=f"{p.name} has {outlier_count} outlier(s) outside "
                               f"[{lower:.2f}, {upper:.2f}] (IQR method).",
                    )
                )

        return issues
