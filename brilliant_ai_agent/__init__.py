"""Brilliant AI Agent: flight recorder and replay for AI agents."""
from .recorder import Run, record_llm, tool, current_run, ReplayError, ReplayedToolError
from .diff import diff_runs
from .adapters import wrap_openai, wrap_anthropic
from .report import summarize, render_text, render_html
from .store import load_run, list_runs

__all__ = ["ReplayError", "ReplayedToolError", "diff_runs", "wrap_openai", "wrap_anthropic", "Run", "record_llm", "tool", "current_run", "summarize",
           "render_text", "render_html", "load_run", "list_runs"]
__version__ = "0.2.0"
