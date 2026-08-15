"""
Monitoring & Debug Agent.

Tracks operational metadata about the run: whether an LLM API key was
detected, how many LLM calls were made, response time of the last call,
whether the system fell back to rule-based explanations, and any errors
encountered anywhere in the pipeline. This is intentionally a plain
mutable object passed by reference into agents that need to report to it,
rather than a return value, because monitoring is cross-cutting.
"""
from __future__ import annotations
import time
from core.models import MonitorEvent


class Monitor:
    def __init__(self, api_key_detected: bool):
        self.event = MonitorEvent(api_key_detected=api_key_detected)
        self._call_start: float | None = None

    def start_llm_call(self) -> None:
        self._call_start = time.time()

    def end_llm_call(self, success: bool) -> None:
        if self._call_start is not None:
            elapsed_ms = (time.time() - self._call_start) * 1000
            self.event.last_response_time_ms = round(elapsed_ms, 1)
            self._call_start = None
        if success:
            self.event.llm_calls += 1

    def mark_fallback_used(self) -> None:
        self.event.used_fallback = True

    def log_error(self, message: str) -> None:
        self.event.errors.append(message)

    def summary(self) -> dict:
        return {
            "API Key": "Detected" if self.event.api_key_detected else "Not found",
            "LLM Calls": self.event.llm_calls,
            "Last LLM Response Time (ms)": self.event.last_response_time_ms,
            "Used Fallback": self.event.used_fallback,
            "Errors": self.event.errors or "None recorded",
        }
