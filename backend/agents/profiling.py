"""
Data Profiling Agent.

Examines dtypes and basic structure of each column so downstream agents
know which cleaning strategy applies. Numeric columns -> median imputation
candidates. Categorical (object) columns -> mode imputation candidates.
This mirrors the article's distinction exactly.
"""
from __future__ import annotations
import pandas as pd
from core.models import ColumnProfile


class ProfilingAgent:
    def profile(self, df: pd.DataFrame) -> list[ColumnProfile]:
        profiles = []
        for col in df.columns:
            dtype = str(df[col].dtype)
            kind = self._classify(df[col])
            profiles.append(
                ColumnProfile(
                    name=col,
                    dtype=dtype,
                    kind=kind,
                    missing_count=int(df[col].isna().sum()),
                    unique_count=int(df[col].nunique(dropna=True)),
                )
            )
        return profiles

    @staticmethod
    def _classify(series: pd.Series) -> str:
        if pd.api.types.is_datetime64_any_dtype(series):
            return "datetime"
        if pd.api.types.is_numeric_dtype(series):
            return "numeric"
        if (
            pd.api.types.is_object_dtype(series)
            or pd.api.types.is_categorical_dtype(series)
            or pd.api.types.is_string_dtype(series)  # covers pandas' newer StringDtype/PyArrow-backed str columns
        ):
            return "categorical"
        return "other"
