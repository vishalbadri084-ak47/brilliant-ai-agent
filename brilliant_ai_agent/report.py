import html

def summarize(events):
    s = {"goal": None, "achieved": None, "error": None, "finished": False,
         "tool_calls": 0, "tool_failures": 0, "llm_calls": 0,
         "input_tokens": 0, "output_tokens": 0, "cost": 0.0, "cost_known": True,
         "duration": 0.0, "first_failure": None, "repeats": []}
    if not events:
        return s
    seen = {}
    for e in events:
        k = e.get("kind")
        if k == "run_start":
            s["goal"] = e.get("goal")
        elif k == "tool":
            s["tool_calls"] += 1
            key = (e.get("tool"), e.get("args"))
            seen[key] = seen.get(key, 0) + 1
            if not e.get("ok"):
                s["tool_failures"] += 1
                if s["first_failure"] is None:
                    s["first_failure"] = e
        elif k == "llm":
            s["llm_calls"] += 1
            s["input_tokens"] += e.get("input_tokens") or 0
            s["output_tokens"] += e.get("output_tokens") or 0
            if e.get("cost") is None:
                s["cost_known"] = False
            else:
                s["cost"] += e["cost"]
            if e.get("error") and s["first_failure"] is None:
                s["first_failure"] = e
        elif k == "run_end":
            s["finished"] = True
            s["achieved"] = e.get("achieved")
            s["error"] = e.get("error")
    s["duration"] = events[-1]["t"] - events[0]["t"]
    s["repeats"] = [(t, a, n) for (t, a), n in seen.items() if n >= 3]
    return s

def verdict(s):
    if not s["finished"]:
        return "INCOMPLETE (run never ended - crash or kill)"
    if s["achieved"] is True:
        return "GOAL MET"
    if s["achieved"] is False:
        return "GOAL NOT MET"
    return "GOAL UNKNOWN (no check supplied)"

def render_text(events):
    s = summarize(events)
    cost = "$%.4f" % s["cost"] + ("" if s["cost_known"] or not s["llm_calls"]
                                  else " (partial: some models had no price)")
    L = ["Goal:    %s" % s["goal"], "Verdict: %s" % verdict(s),
         "Tools:   %d calls, %d failed" % (s["tool_calls"], s["tool_failures"]),
         "LLM:     %d calls, %d in / %d out tokens, cost %s" % (
             s["llm_calls"], s["input_tokens"], s["output_tokens"], cost),
         "Time:    %.2fs" % s["duration"]]
    if s["error"]:
        L.append("Error:   %s" % s["error"])
    ff = s["first_failure"]
    if ff:
        L.append("First failure: step %d, %s - %s" % (
            ff["seq"], ff.get("tool") or ff.get("model"), ff.get("error")))
    for t, a, n in s["repeats"]:
        L.append("Loop warning: %s%s called %d times with identical args" % (t, a[:60], n))
    L.append("")
    L.append("Timeline:")
    for e in events:
        k = e["kind"]
        if k == "tool":
            mark = "ok  " if e.get("ok") else "FAIL"
            L.append("  %3d tool %s %s%s" % (e["seq"], mark, e["tool"],
                     "" if e.get("ok") else "  -> " + str(e.get("error"))))
        elif k == "llm":
            L.append("  %3d llm  %s %d/%d tok" % (e["seq"], e["model"],
                     e.get("input_tokens") or 0, e.get("output_tokens") or 0))
    return "\n".join(L)

def render_html(events):
    """One self-contained file: share it in an issue or chat, no server."""
    s = summarize(events)
    rows = []
    for e in events:
        if e["kind"] not in ("tool", "llm"):
            continue
        bad = (e["kind"] == "tool" and not e.get("ok")) or e.get("error")
        detail = e.get("error") or e.get("result") or e.get("note") or ""
        name = e.get("tool") or e.get("model")
        rows.append('<tr class="%s"><td>%d</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            "bad" if bad else "", e["seq"], e["kind"], html.escape(str(name)),
            html.escape(str(detail))[:300]))
    return ("<!doctype html><meta charset=utf-8><title>brilliant-ai-agent report</title>"
            "<style>body{font:15px system-ui;max-width:860px;margin:2em auto}"
            "td,th{padding:4px 8px;border-bottom:1px solid #ddd;text-align:left}"
            ".bad{background:#fde8e8}</style>"
            "<h1>%s</h1><p><b>Goal:</b> %s</p>"
            "<p>Tools %d (%d failed) &middot; LLM %d calls &middot; cost $%.4f &middot; %.2fs</p>"
            "<table><tr><th>#</th><th>type</th><th>name</th><th>detail</th></tr>%s</table>" % (
                html.escape(verdict(s)), html.escape(str(s["goal"])), s["tool_calls"],
                s["tool_failures"], s["llm_calls"], s["cost"], s["duration"], "".join(rows)))
