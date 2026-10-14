"""Auto-capture for OpenAI- and Anthropic-style clients. Duck-typed: no SDK import,
so this module works with whatever version the user has installed."""
from .recorder import current_run

def _usage(resp, in_keys, out_keys):
    u = getattr(resp, "usage", None)
    if u is None and isinstance(resp, dict):
        u = resp.get("usage")
    def g(*keys):
        for k in keys:
            v = u.get(k) if isinstance(u, dict) else getattr(u, k, None)
            if v is not None:
                return v
        return 0
    return g(*in_keys) if u else 0, g(*out_keys) if u else 0

def _wrap(fn, in_keys, out_keys):
    def inner(*a, **kw):
        r = current_run()
        model = kw.get("model", "unknown")
        try:
            resp = fn(*a, **kw)
        except Exception as e:
            if r: r.llm(model, error="%s: %s" % (type(e).__name__, e))
            raise
        if r:
            i, o = _usage(resp, in_keys, out_keys)
            r.llm(getattr(resp, "model", None) or model, i, o)
        return resp
    return inner

def wrap_openai(client):
    """Patch client.chat.completions.create in place; returns the client."""
    c = client.chat.completions
    c.create = _wrap(c.create, ("prompt_tokens",), ("completion_tokens",))
    return client

def wrap_anthropic(client):
    """Patch client.messages.create in place; returns the client."""
    m = client.messages
    m.create = _wrap(m.create, ("input_tokens",), ("output_tokens",))
    return client
