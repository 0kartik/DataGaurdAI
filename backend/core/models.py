"""
Shared data structures passed between agents in the pipeline.
Keeping these in one place avoids every agent inventing its own dict shape.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal
import time


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    kind: Literal["numeric", "categorical", "datetime", "other"]
    missing_count: int = 0
    unique_count: int = 0


@dataclass
class QualityIssue:
    """One detected problem, e.g. 'SalesAmount has 7 missing values'."""
    issue_type: Literal["missing_values", "duplicates", "outliers"]
    column: str | None       # None for dataset-wide issues like duplicates
    count: int
    detail: str = ""


@dataclass
class RepairRecommendation:
    column: str
    issue_type: str
    method: str               # e.g. "mode", "median", "drop_duplicates", "cap_iqr"
    severity: Literal["Low", "Medium", "High"]
    rationale: str = ""


@dataclass
class PlanStep:
    step_id: str               # e.g. "fill_missing", "remove_duplicates", "cap_outliers"
    targets: list[str] = field(default_factory=list)   # columns this step touches
    method_by_column: dict[str, str] = field(default_factory=dict)


@dataclass
class ExecutionLogEntry:
    step_id: str
    column: str
    action: str
    value_used: Any = None
    rows_affected: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class QualityScore:
    score: float               # 0-100
    missing_penalty: float
    duplicate_penalty: float
    outlier_penalty: float
    total_cells: int
    problem_cells: int


@dataclass
class MonitorEvent:
    api_key_detected: bool = False
    llm_calls: int = 0
    last_response_time_ms: float | None = None
    errors: list[str] = field(default_factory=list)
    used_fallback: bool = False
