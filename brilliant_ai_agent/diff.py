from .report import summarize, verdict

def diff_runs(a, b):
    """Compare two event lists. Returns dict + human text."""
    sa, sb = summarize(a), summarize(b)
    ta = [(e["tool"], e.get("ok")) for e in a if e["kind"] == "tool"]
    tb = [(e["tool"], e.get("ok")) for e in b if e["kind"] == "tool"]
    first = None
    for i in range(max(len(ta), len(tb))):
        x = ta[i] if i < len(ta) else None
        y = tb[i] if i < len(tb) else None
        if x != y:
            first = (i + 1, x, y); break
    d = {"verdict": (verdict(sa), verdict(sb)),
         "tool_calls": (sa["tool_calls"], sb["tool_calls"]),
         "failures": (sa["tool_failures"], sb["tool_failures"]),
         "cost": (sa["cost"], sb["cost"]), "first_divergence": first}
    L = ["Verdict:  %s  ->  %s" % d["verdict"],
         "Tools:    %d -> %d calls, failures %d -> %d" % (
             sa["tool_calls"], sb["tool_calls"], sa["tool_failures"], sb["tool_failures"]),
         "Cost:     $%.4f -> $%.4f" % d["cost"]]
    f = lambda t: "nothing" if t is None else "%s(%s)" % (t[0], "ok" if t[1] else "FAIL")
    L.append("Same tool path." if first is None else
             "First divergence at tool call %d: %s vs %s" % (first[0], f(first[1]), f(first[2])))
    return d, "\n".join(L)
