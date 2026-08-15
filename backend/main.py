"""
Data Guard AI — FastAPI backend.

Single responsibility: accept a CSV upload, run it through the agent
pipeline, and return a JSON-serializable result for the frontend to render.
CORS is open for local development (frontend served separately/statically).
"""
from __future__ import annotations
import io
import os
import math
import dataclasses
from typing import Optional

from dotenv import load_dotenv
load_dotenv()  # picks up backend/.env if present, so FEATHERLESS_API_KEY/MODEL
                # can be set once instead of typed into the UI every time

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from core.pipeline import DataGuardPipeline

app = FastAPI(title="Data Guard AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Kept in memory for the demo so "download cleaned CSV" can re-serve the
# last result without re-uploading. Fine for a single-user local app;
# would move to a session/store for multi-user deployment.
_last_cleaned_csv: Optional[bytes] = None


def _to_jsonable(obj):
    """Recursively convert dataclasses / pandas / numpy values into plain,
    JSON-safe types. NaN/Inf are not valid JSON, so they become None."""
    if dataclasses.is_dataclass(obj):
        return {k: _to_jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if hasattr(obj, "item"):  # numpy scalar
        try:
            obj = obj.item()
        except Exception:
            return str(obj)
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    featherless_api_key: str = Form(default=""),
    featherless_model: str = Form(default=""),
):
    global _last_cleaned_csv

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # UI field wins if the user typed something; otherwise fall back to
    # whatever is configured server-side via backend/.env. This means the
    # key/model only need to be set in one place (the .env file) and the
    # UI fields become optional overrides, not a requirement.
    resolved_key = featherless_api_key.strip() or os.environ.get("FEATHERLESS_API_KEY") or None
    resolved_model = featherless_model.strip() or os.environ.get("FEATHERLESS_MODEL") or None

    pipeline = DataGuardPipeline(
        featherless_api_key=resolved_key,
        featherless_model=resolved_model,
    )

    try:
        result = pipeline.run(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    _last_cleaned_csv = result.df_after.to_csv(index=False).encode("utf-8")

    return {
        "ingestion_report": result.ingestion_report,
        "profiles": _to_jsonable(result.profiles),
        "issues": _to_jsonable(result.issues),
        "recommendations": _to_jsonable(result.recommendations),
        "plan": _to_jsonable(result.plan),
        "execution_log": _to_jsonable(result.execution_log),
        "score_before": _to_jsonable(result.score_before),
        "score_after": _to_jsonable(result.score_after),
        "explanation": result.explanation,
        "monitor_summary": _to_jsonable(result.monitor_summary),
        "preview_before": _to_jsonable(result.df_before.head(10).to_dict(orient="records")),
        "preview_after": _to_jsonable(result.df_after.head(10).to_dict(orient="records")),
        "columns": list(result.df_after.columns),
    }


@app.get("/api/download-cleaned")
def download_cleaned():
    if _last_cleaned_csv is None:
        raise HTTPException(status_code=404, detail="No cleaned dataset available yet. Run /api/analyze first.")
    return StreamingResponse(
        io.BytesIO(_last_cleaned_csv),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cleaned_dataset.csv"},
    )
