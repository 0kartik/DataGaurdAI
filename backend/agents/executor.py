"""
Execution Agent.

Applies the PlanSteps to the dataset in order, mutating a copy of the
DataFrame (never the original, so a rollback is always possible) and
recording every change to an execution log for transparency.
"""
from __future__ import annotations
import pandas as pd
from core.models import PlanStep, ExecutionLogEntry


class ExecutionAgent:
    def execute(self, df: pd.DataFrame, plan: list[PlanStep]) -> tuple[pd.DataFrame, list[ExecutionLogEntry]]:
        working = df.copy(deep=True)
        log: list[ExecutionLogEntry] = []

        for step in plan:
            if step.step_id == "remove_duplicates":
                before = len(working)
                working = working.drop_duplicates(keep="first").reset_index(drop=True)
                removed = before - len(working)
                log.append(
                    ExecutionLogEntry(
                        step_id=step.step_id,
                        column="__dataset__",
                        action="drop_duplicates",
                        rows_affected=removed,
                    )
                )

            elif step.step_id == "cap_outliers":
                for col in step.targets:
                    series = working[col]
                    q1, q3 = series.quantile(0.25), series.quantile(0.75)
                    iqr = q3 - q1
                    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                    affected = int(((series < lower) | (series > upper)).sum())
                    working[col] = series.clip(lower=lower, upper=upper)
                    log.append(
                        ExecutionLogEntry(
                            step_id=step.step_id,
                            column=col,
                            action="cap_iqr",
                            value_used=f"[{lower:.2f}, {upper:.2f}]",
                            rows_affected=affected,
                        )
                    )

            elif step.step_id == "fill_missing":
                for col in step.targets:
                    method = step.method_by_column[col]
                    missing_before = int(working[col].isna().sum())
                    if method == "mode":
                        fill_value = working[col].mode(dropna=True)
                        fill_value = fill_value.iloc[0] if not fill_value.empty else None
                    else:  # median
                        fill_value = working[col].median()
                    working[col] = working[col].fillna(fill_value)
                    log.append(
                        ExecutionLogEntry(
                            step_id=step.step_id,
                            column=col,
                            action=f"fill_{method}",
                            value_used=fill_value,
                            rows_affected=missing_before,
                        )
                    )

        return working, log
