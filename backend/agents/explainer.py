"""
Explanation Agent.

Generates a human-readable summary of dataset health that explains,
per column: what was wrong, why that repair method was chosen, and
what value was actually used. Tries an LLM call via Featherless AI
(OpenAI-compatible /v1/chat/completions) first; if the API key is
missing, the request fails, or times out, falls back to a deterministic
rule-based narrative so the pipeline never breaks just because a
network call failed.
"""
from __future__ import annotations
import os
import requests
from core.models import QualityIssue, QualityScore, RepairRecommendation, ExecutionLogEntry
from core.monitor import Monitor

FEATHERLESS_URL = "https://api.featherless.ai/v1/chat/completions"
DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct"  # override via FEATHERLESS_MODEL env var
REQUEST_TIMEOUT_S = 45


def _fmt_value(v) -> str:
    """Render a fill/cap value for prose without numpy repr noise."""
    if hasattr(v, "item"):
        try:
            v = v.item()
        except Exception:
            pass
    if isinstance(v, float):
        return f"{v:.2f}"
    return repr(v)


class ExplanationAgent:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.environ.get("FEATHERLESS_API_KEY")
        self.model = model or os.environ.get("FEATHERLESS_MODEL", DEFAULT_MODEL)

    def explain(
        self,
        issues: list[QualityIssue],
        recommendations: list[RepairRecommendation],
        execution_log: list[ExecutionLogEntry],
        before: QualityScore,
        after: QualityScore,
        monitor: Monitor,
    ) -> str:
        monitor.event.api_key_detected = bool(self.api_key)

        if self.api_key:
            try:
                return self._explain_via_llm(issues, recommendations, execution_log, before, after, monitor)
            except Exception as e:
                monitor.log_error(f"LLM explanation failed, using fallback: {e}")

        monitor.mark_fallback_used()
        return self._explain_via_rules(issues, recommendations, execution_log, before, after)

    # ---------- LLM path ----------
    def _explain_via_llm(
        self,
        issues: list[QualityIssue],
        recommendations: list[RepairRecommendation],
        execution_log: list[ExecutionLogEntry],
        before: QualityScore,
        after: QualityScore,
        monitor: Monitor,
    ) -> str:
        prompt = self._build_prompt(issues, recommendations, execution_log, before, after)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a data quality analyst reporting to a business audience. "
                        "For every column that had an issue, explain: what was wrong (what/where), "
                        "why that repair method was chosen for that column's data type (why), "
                        "and what value was actually filled in or how the value was corrected (what happened). "
                        "Go column by column — do not summarize vaguely. Be specific and concrete, "
                        "using the exact values and counts given. End with the overall before/after "
                        "score and a one-line recommendation. "
                        "Formatting: write ONE SHORT PARAGRAPH PER COLUMN/ISSUE, separated by a blank line "
                        "(double newline). Start each paragraph with the column name followed by a colon, "
                        "e.g. 'CustomerName: ...'. Put the overall score summary in its own final paragraph. "
                        "Do not run everything into a single block of text. Plain language, no markdown "
                        "headers, no bullet symbols. do not use AI em dashes. Avoid repeating the same phrases. no AI sounding disclaimers."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 700,
            "temperature": 0.3,
        }

        monitor.start_llm_call()
        try:
            resp = requests.post(headers=headers, json=payload, url=FEATHERLESS_URL, timeout=REQUEST_TIMEOUT_S)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            if not text:
                monitor.end_llm_call(success=False)
                monitor.log_error(f"LLM returned empty content. Raw response: {data}")
                raise ValueError("LLM returned an empty completion.")
            monitor.end_llm_call(success=True)
            return text
        except Exception:
            monitor.end_llm_call(success=False)
            raise

    @staticmethod
    def _build_prompt(
        issues: list[QualityIssue],
        recommendations: list[RepairRecommendation],
        execution_log: list[ExecutionLogEntry],
        before: QualityScore,
        after: QualityScore,
    ) -> str:
        if not issues:
            return (
                f"No data quality issues were detected. Score: {after.score}/100. "
                "Write a short confirmation that the dataset is clean."
            )

        rec_by_key = {(r.column, r.issue_type): r for r in recommendations}
        log_by_col = {}
        for entry in execution_log:
            log_by_col.setdefault(entry.column, []).append(entry)

        lines = []
        for issue in issues:
            col = issue.column or "(dataset-wide)"
            rec = rec_by_key.get((issue.column, issue.issue_type)) or rec_by_key.get(("__dataset__", issue.issue_type))
            entries = log_by_col.get(issue.column, []) + log_by_col.get("__dataset__", [])
            value_note = ""
            for e in entries:
                if issue.issue_type == "missing_values" and e.action.startswith("fill_"):
                    value_note = f" Filled value used: {_fmt_value(e.value_used)} ({e.rows_affected} rows)."
                elif issue.issue_type == "duplicates" and e.action == "drop_duplicates":
                    value_note = f" {e.rows_affected} duplicate row(s) removed."
                elif issue.issue_type == "outliers" and e.action == "cap_iqr":
                    value_note = f" Values capped to range {e.value_used}, affecting {e.rows_affected} row(s)."

            method_note = f" Chosen method: {rec.method} — {rec.rationale}" if rec else ""
            lines.append(f"- Column '{col}': {issue.detail}{method_note}{value_note}")

        return (
            f"Dataset quality score before cleaning: {before.score}/100\n"
            f"Dataset quality score after cleaning: {after.score}/100\n\n"
            f"Per-column issues and repairs:\n" + "\n".join(lines) + "\n\n"
            "Write the full column-by-column explanation as instructed."
        )

    # ---------- rule-based fallback ----------
    @staticmethod
    def _explain_via_rules(
        issues: list[QualityIssue],
        recommendations: list[RepairRecommendation],
        execution_log: list[ExecutionLogEntry],
        before: QualityScore,
        after: QualityScore,
    ) -> str:
        if not issues:
            return (
                f"No data quality issues were detected. The dataset scored "
                f"{after.score}/100 and required no repairs."
            )

        rec_by_key = {(r.column, r.issue_type): r for r in recommendations}
        log_by_col: dict[str, list[ExecutionLogEntry]] = {}
        for entry in execution_log:
            log_by_col.setdefault(entry.column, []).append(entry)

        paragraphs = []
        for issue in issues:
            col = issue.column or "(dataset-wide)"
            rec = rec_by_key.get((issue.column, issue.issue_type)) or rec_by_key.get(("__dataset__", issue.issue_type))
            entries = log_by_col.get(issue.column, []) + log_by_col.get("__dataset__", [])

            if issue.issue_type == "missing_values":
                fill_entry = next((e for e in entries if e.action.startswith("fill_")), None)
                if rec and fill_entry:
                    kind_word = "categorical" if rec.method == "mode" else "numeric"
                    stat_word = "most frequent value (mode)" if rec.method == "mode" else "median"
                    paragraphs.append(
                        f"{col}: {issue.count} missing value(s) were found. Since {col} is a {kind_word} "
                        f"column, missing entries were filled using the {stat_word} of the existing data — "
                        f"the value used was {_fmt_value(fill_entry.value_used)}, applied to {fill_entry.rows_affected} row(s)."
                    )
                else:
                    paragraphs.append(f"{col}: {issue.count} missing value(s) were found.")

            elif issue.issue_type == "duplicates":
                drop_entry = next((e for e in entries if e.action == "drop_duplicates"), None)
                rows_removed = drop_entry.rows_affected if drop_entry else issue.count
                paragraphs.append(
                    f"Duplicate rows: {issue.count} exact-match duplicate row(s) were detected across the "
                    f"entire dataset (all columns identical to an earlier row). These add no new information "
                    f"and would double-count in any aggregation, so {rows_removed} duplicate row(s) were removed, "
                    "keeping the first occurrence of each."
                )

            elif issue.issue_type == "outliers":
                cap_entry = next((e for e in entries if e.action == "cap_iqr"), None)
                if cap_entry:
                    paragraphs.append(
                        f"{col}: {issue.count} outlier(s) were found using the IQR method — values statistically "
                        f"far outside the normal spread of {col}. Rather than deleting these rows and losing other "
                        f"data in them, the extreme values were capped to the range {cap_entry.value_used}, "
                        f"affecting {cap_entry.rows_affected} row(s)."
                    )
                else:
                    paragraphs.append(f"{col}: {issue.count} outlier(s) were found via the IQR method.")

        improvement = round(after.score - before.score, 2)
        paragraphs.append(
            f"Overall, the dataset's quality score improved from {before.score}/100 to {after.score}/100 "
            f"(+{improvement}) after these repairs. It's worth reviewing data entry or collection processes "
            "for the columns above to reduce how often this recurs."
        )
        return "\n\n".join(paragraphs)