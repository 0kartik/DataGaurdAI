"""
Evaluation Agent (quality scorer).

Computes a single 0-100 quality score for a dataset based on the
proportion of "problem cells" — missing values, rows involved in
duplicates, and IQR outliers — relative to total cells. Called twice
by the pipeline: once before execution, once after, so the dashboard
can show a Before -> After improvement, exactly like the article.
"""
from __future__ import annotations
import pandas as pd
from core.models import QualityScore

# relative weights: missing data is worst, then duplicates, then outliers
WEIGHTS = {"missing": 1.0, "duplicate": 0.7, "outlier": 0.5}


class ScorerAgent:
    def score(self, df: pd.DataFrame) -> QualityScore:
        total_cells = df.shape[0] * df.shape[1]
        if total_cells == 0:
            return QualityScore(0, 0, 0, 0, 0, 0)

        missing = int(df.isna().sum().sum())
        dup_rows = int(df.duplicated(keep="first").sum())

        outlier_cells = 0
        for col in df.select_dtypes(include="number").columns:
            series = df[col].dropna()
            if len(series) < 4:
                continue
            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outlier_cells += int(((series < lower) | (series > upper)).sum())

        missing_penalty = (missing / total_cells) * WEIGHTS["missing"] * 100
        duplicate_penalty = (dup_rows / max(df.shape[0], 1)) * WEIGHTS["duplicate"] * 100
        outlier_penalty = (outlier_cells / total_cells) * WEIGHTS["outlier"] * 100

        problem_cells = missing + dup_rows + outlier_cells
        raw_score = 100 - (missing_penalty + duplicate_penalty + outlier_penalty)
        final_score = max(0.0, min(100.0, raw_score))

        return QualityScore(
            score=round(final_score, 2),
            missing_penalty=round(missing_penalty, 2),
            duplicate_penalty=round(duplicate_penalty, 2),
            outlier_penalty=round(outlier_penalty, 2),
            total_cells=total_cells,
            problem_cells=problem_cells,
        )
