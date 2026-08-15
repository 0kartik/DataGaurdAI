"""
Data Ingestion Agent.

Responsible for loading the uploaded CSV into a validated DataFrame.
Deliberately narrow scope: it does not clean or interpret the data,
only ensures it can be read and reports basic shape/structure so
downstream agents start from a known-good state.
"""
from __future__ import annotations
import pandas as pd
from io import BytesIO


class IngestionError(Exception):
    pass


class IngestionAgent:
    def load(self, file_like) -> tuple[pd.DataFrame, dict]:
        """
        file_like: a file path, BytesIO, or Streamlit UploadedFile.
        Returns (dataframe, report) where report describes what happened.
        """
        try:
            df = pd.read_csv(file_like)
        except UnicodeDecodeError:
            # retry with a more permissive encoding rather than failing outright
            if hasattr(file_like, "seek"):
                file_like.seek(0)
            df = pd.read_csv(file_like, encoding="latin-1")
        except Exception as e:
            raise IngestionError(f"Could not parse CSV: {e}") from e

        if df.empty:
            raise IngestionError("Uploaded CSV contains no rows.")

        report = {
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": list(df.columns),
        }
        return df, report
