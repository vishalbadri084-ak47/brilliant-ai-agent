import json, os, glob

def default_dir():
    return os.environ.get("BRILLIANT_AI_AGENT_DIR", ".brilliant-agent")

def load_run(path):
    """Read a run file (one JSON event per line). Skips a torn last line."""
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # crash mid-write: keep everything before it
    return events

def list_runs(directory=None):
    d = directory or default_dir()
    out = []
    for p in sorted(glob.glob(os.path.join(d, "*.jsonl"))):
        try:
            from .report import summarize
            s = summarize(load_run(p))
            out.append((p, s))
        except Exception:
            continue
    return out
