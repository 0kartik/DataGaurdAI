"""
Debug script — run this from inside the backend/ folder to see exactly
what the explanation agent produces, without going through the browser.

Usage:
    cd backend
    python debug_explain.py
"""
from core.pipeline import DataGuardPipeline

pipeline = DataGuardPipeline()
print("API key detected:", bool(pipeline.explainer.api_key))
print("Model:", pipeline.explainer.model)
print()

result = pipeline.run("../test_sales.csv")

print("=== EXPLANATION ===")
print(repr(result.explanation))
print()
print("=== MONITOR SUMMARY ===")
print(result.monitor_summary)
